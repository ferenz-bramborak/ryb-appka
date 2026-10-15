"""Novinky z revírů pro záložku „Novinky“ v aplikaci.

  mrk.cz Bleskovky            – rybářské zpravodajství (úhyny, zákazy, vysazení…)
  ČRS – novinky MO (API)      – zprávy místních organizací zveřejněné přes rybsvaz.cz
  weby MO a spolků MRS        – seznam v scraper/mo_weby.json; čte RSS, jinak stránku
                                aktualit a z ní články o vysazování/zákazech
Výstup: seznam zpráv {datum, titulek, text, typ, zdroj, url, svaz?, mo?, vysazeni?[]}.
Přiřazení k revírům dělá build.
"""
from __future__ import annotations

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse

from lxml import etree

from ..http import get_json, get_text
from ..text import dates_in_text, html_text, iso, parse_date, typ_zpravy, vysazeni_z_textu

NAZEV = "Novinky"
log = logging.getLogger(__name__)

DNU = 31           # jak staré zprávy brát
MO_WEBY = Path(__file__).resolve().parents[1] / "mo_weby.json"
KLICOVA = re.compile(r"vysaz|zarybn|násad|nasaz|vypuštěn|zákaz|uzavř|úhyn|revír|výlov|aktualit|novink|zpráv", re.I)


def _zprava(**kw) -> dict:
    text = kw.get("text") or ""
    kw["typ"] = typ_zpravy(f"{kw.get('titulek', '')} {text}")
    if kw["typ"] == "vysazeni":
        v = vysazeni_z_textu(f"{kw.get('titulek', '')}. {text}")
        if v:
            kw["vysazeni"] = v
    kw["text"] = text[:600]
    return {k: v for k, v in kw.items() if v not in (None, "", [])}


# ---------------- mrk.cz Bleskovky ----------------
MRK = "https://www.mrk.cz/"


def _mrk_get(url: str) -> str:
    for pokus in range(3):
        t = get_text(url, encoding="iso-8859-2", delay=1.5 + 3 * pokus)
        if "System je pretizen" not in t:
            return t
    raise RuntimeError("mrk.cz je přetížené")


def _mrk_bleskovky(od: date) -> list[dict]:
    seznam = _mrk_get(MRK + "bleskovky.php")
    out = []
    today = date.today()
    for den, mes, bid, titulek in re.findall(
            r'<span class="dat">(\d{1,2})\.(\d{1,2})\.</span>.*?<a href="bleskovky\.php\?id=(\d+)"[^>]*><strong>(.*?)</strong>',
            seznam, re.S):
        d = date(today.year, int(mes), int(den))
        if d > today:
            d = date(today.year - 1, int(mes), int(den))
        if d < od:
            break
        url = f"{MRK}bleskovky.php?id={bid}"
        try:
            h = _mrk_get(url)
            m = re.search(r'<div class="article-body"[^>]*>(.*?)<div style="padding-top:20px', h, re.S)
            text = html_text(m.group(1)) if m else ""
        except Exception as e:  # noqa: BLE001
            log.warning("bleskovka %s: %s", bid, e)
            text = ""
        out.append(_zprava(datum=iso(d), titulek=html_text(titulek), text=text, url=url, zdroj="mrk.cz – Bleskovky"))
    log.info("mrk.cz Bleskovky: %d zpráv", len(out))
    return out


# ---------------- ČRS – novinky MO přes API ----------------
API = "https://www.rybsvaz.cz/proxy/api/public"


def _svaz(us: dict | None) -> str:
    return "ČRS – " + (((us or {}).get("nazev") or "").replace(" územní svaz", " ÚS") or "Republiková rada")


def _crs_mo(od: date) -> list[dict]:
    mos = get_json(f"{API}/mistni-organizace?from=0&size=1000")["items"]

    def jedna(o):
        try:
            items = get_json(f"{API}/mistni-organizace/by-sid/{o['sid']}/novinky?from=0&size=10")["items"]
        except Exception:  # noqa: BLE001
            return []
        res = []
        for n in items:
            d = parse_date(n.get("datum"))
            if not d or d < od:
                continue
            res.append(_zprava(datum=iso(d), titulek=n.get("nazev"), text=html_text(n.get("popis") or ""),
                               url=o.get("webUrl"), zdroj=f"MO {o['nazev']} (rybsvaz.cz)",
                               svaz=_svaz(o.get("uzemniSvaz")), mo=o["nazev"]))
        return res

    with ThreadPoolExecutor(max_workers=6) as pool:
        out = [z for res in pool.map(jedna, mos) for z in res]
    log.info("ČRS novinky MO: %d zpráv", len(out))
    return out


# ---------------- weby MO ----------------

def _rss(url: str, od: date, org: dict) -> list[dict]:
    root = etree.fromstring(get_text(url, timeout=30).encode("utf-8", "replace"), etree.XMLParser(recover=True))
    out = []
    for it in root.iter("item", "{http://www.w3.org/2005/Atom}entry"):
        g = lambda tag: (it.findtext(tag) or it.findtext("{http://www.w3.org/2005/Atom}" + tag) or "").strip()
        link = g("link") or (it.find("{http://www.w3.org/2005/Atom}link").get("href") if it.find("{http://www.w3.org/2005/Atom}link") is not None else "")
        d = parse_date(g("pubDate") or g("published") or g("updated") or g("{http://purl.org/dc/elements/1.1/}date"))
        if not d or d < od:
            continue
        text = html_text(g("{http://purl.org/rss/1.0/modules/content/}encoded") or g("description") or g("summary") or g("content"))
        out.append(_zprava(datum=iso(d), titulek=html_text(g("title")), text=text, url=link or org["web"],
                           zdroj=f"web {org['nazev']}", svaz=org.get("svaz"), mo=org["nazev"]))
    return out


def _clanek(url: str) -> tuple[str, str, date | None]:
    h = get_text(url, timeout=30)
    m = re.search(r'<meta[^>]+(?:article:published_time|datePublished)[^>]+content="([^"]+)"', h)
    d = parse_date(m.group(1)) if m else None
    titul = re.search(r"<h1[^>]*>(.*?)</h1>", h, re.S) or re.search(r"<title>(.*?)</title>", h, re.S)
    body = re.search(r"<(article|main)\b.*?</\1>", h, re.S)
    text = html_text(body.group(0) if body else h)
    if not d:
        ds = [x for x in dates_in_text(text[:3000]) if x <= date.today()]
        d = max(ds) if ds else None
    return html_text(titul.group(1)) if titul else "", text, d


def _html(org: dict, od: date) -> list[dict]:
    start = org.get("aktuality") or org["web"]
    h = get_text(start, timeout=30)
    host = urlparse(start).netloc
    odkazy = []
    for href, anchor in re.findall(r'<a\b[^>]*href="([^"#]+)"[^>]*>(.*?)</a>', h, re.S):
        u = urljoin(start, href)
        a = html_text(anchor)
        if urlparse(u).netloc != host or u in odkazy or len(a) < 6:
            continue
        if re.search(r"vysaz|zarybn|násad|zákaz|uzavř|úhyn|výlov", a + " " + u, re.I):
            odkazy.append(u)
    out = []
    for u in odkazy[:8]:
        try:
            titul, text, d = _clanek(u)
        except Exception as e:  # noqa: BLE001
            log.debug("%s: %s", u, e)
            continue
        if not d or d < od:
            continue
        out.append(_zprava(datum=iso(d), titulek=titul, text=text, url=u, zdroj=f"web {org['nazev']}",
                           svaz=org.get("svaz"), mo=org["nazev"]))
    return out


def _weby_mo(od: date) -> list[dict]:
    if not MO_WEBY.exists():
        return []
    orgs = [o for o in json.loads(MO_WEBY.read_text("utf-8")).get("organizace", []) if o.get("web")]

    def jedna(o):
        try:
            if o.get("rss"):
                return [z for z in _rss(o["rss"], od, o) if z["typ"] != "info" or KLICOVA.search(z.get("titulek", ""))]
            return _html(o, od)
        except Exception as e:  # noqa: BLE001
            log.debug("web %s: %s", o.get("web"), e)
            return []

    with ThreadPoolExecutor(max_workers=8) as pool:
        out = [z for res in pool.map(jedna, orgs) for z in res]
    log.info("Weby MO: %d zpráv z %d webů", len(out), len(orgs))
    return out


def fetch() -> list[dict]:
    od = date.today() - timedelta(days=DNU)
    out = []
    for f in (_mrk_bleskovky, _crs_mo, _weby_mo):
        try:
            out += f(od)
        except Exception as e:  # noqa: BLE001
            log.warning("%s: %s", f.__name__, e)
    seen, uniq = set(), []
    for z in sorted(out, key=lambda z: z["datum"], reverse=True):
        key = (z.get("url"), z.get("titulek"))
        if key not in seen:
            seen.add(key)
            uniq.append(z)
    if not uniq:
        raise RuntimeError("žádné novinky")
    return uniq
