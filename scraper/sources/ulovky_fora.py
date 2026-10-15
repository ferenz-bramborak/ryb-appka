"""Úlovky z rybářských webů za poslední 3 měsíce.

  mrk.cz „Můj lov“         – deník úlovků: datum, revír (volný text), popis,
                             často i způsob lovu a nástraha
  chytej.cz Trofejní úlovky – strukturované: datum, revír s číslem, způsob, nástraha

Vrací surové úlovky s textem revíru; k revírům je přiřazuje build
(podle čísla revíru, jinak podle názvu).
"""
from __future__ import annotations

import html
import logging
import re
from datetime import date, datetime, timedelta

from ..geo import norm
from ..http import get_text

NAZEV = "Úlovky z fór"
DRUH = "ulovky"

log = logging.getLogger(__name__)
MESICU = 3

# (kmen slova bez diakritiky, kanonický druh); pořadí rozhoduje – specifičtější dřív.
DRUHY = [
    ("kaprar", None), ("sumecek", "sumeček americký"), ("cejnek", "cejn"),
    ("kapr", "kapr"), ("kapor", "kapr"), ("amur", "amur"), ("stik", "štika"), ("stuk", "štika"),
    ("candat", "candát"), ("zubac", "candát"), ("okoun", "okoun"), ("ostriez", "okoun"),
    ("sumc", "sumec"), ("sumec", "sumec"), ("bolen", "bolen"), ("bolin", "bolen"),
    ("tloust", "jelec tloušť"), ("jelec", "jelec tloušť"), ("jalec", "jelec tloušť"),
    ("duhak", "pstruh duhový"), ("pstruh", "pstruh obecný"), ("lipan", "lipan"), ("lipn", "lipan"),
    ("parm", "parma"), ("mren", "parma"), ("plotic", "plotice"), ("cejn", "cejn"), ("uhor", "úhoř"),
    ("mnik", "mník jednovousý"), ("podoust", "podoustev"), ("podust", "podoustev"),
    ("ostrorek", "ostroretka"), ("karas", "karas"), ("siven", "siven"), ("sivn", "siven"),
    ("hlavatk", "hlavatka"), ("perlin", "perlín"), ("oukle", "ouklej"), ("jeseter", "jeseter"), ("jesete", "jeseter"),
]
LIN = re.compile(r"\blin(a|y|u|e|i|em|ove|ik|ika|iky)?\b")

POLE = ["způsob", "teplota vody", "teplota vzduchu", "kmenový vlasec", "návazec", "délka návazce",
        "velikost háčku", "hloubka", "nej. nástraha", "nástraha", "návnada", "nej. návnada"]
_POLE_RE = re.compile(r"(" + "|".join(re.escape(p) for p in sorted(POLE, key=len, reverse=True)) + r"):\s*", re.I)


def druhy_v_textu(text: str) -> list[str]:
    found = []
    words = norm(text).split()
    for i, word in enumerate(words):
        nxt = words[i + 1] if i + 1 < len(words) else ""
        for stem, druh in DRUHY:
            if word.startswith(stem):
                if druh == "pstruh obecný" and (nxt.startswith("duh") or nxt.startswith("americ")):
                    druh = "pstruh duhový"
                if druh and druh not in found:
                    found.append(druh)
                break
    if LIN.search(norm(text)) and "lín" not in found:
        found.append("lín")
    return found


def pole_z_textu(text: str) -> tuple[str, dict]:
    parts = _POLE_RE.split(text)
    volny = parts[0].strip()
    pole = {}
    for i in range(1, len(parts) - 1, 2):
        pole[parts[i].lower()] = parts[i + 1].strip(" ,.;")
    return volny, pole


def _cislo_reviru(text: str) -> str | None:
    m = re.search(r"\b(4\d{2})\s?(\d{3})\b", text or "")
    return m.group(1) + m.group(2) if m else None


def _ulovky_ze_zapisu(datum: str, revir: str, text: str, url: str, zdroj: str) -> list[dict]:
    volny, pole = pole_z_textu(text)
    druhy = druhy_v_textu(volny)
    if not druhy:
        return []
    delky = [int(x) for x in re.findall(r"(\d{2,3})\s*cm", volny) if 10 <= int(x) <= 250]
    vahy = [float(x.replace(",", ".")) for x in re.findall(r"(\d{1,2}(?:[,.]\d{1,2})?)\s*kg", volny)]
    nastraha = pole.get("nej. nástraha") or pole.get("nástraha") or pole.get("nej. návnada") or pole.get("návnada")
    out = []
    for d in druhy:
        u = {"datum": datum, "druh": d, "revir_text": revir, "zdroj": zdroj, "url": url,
             "text": volny[:280]}
        if len(druhy) == 1 and delky:
            u["delka_cm"] = max(delky)
        if len(druhy) == 1 and vahy:
            u["hmotnost_kg"] = max(vahy)
        if nastraha:
            u["nastraha"] = nastraha[:60].lower()
        if pole.get("způsob"):
            u["metoda"] = pole["způsob"][:40].lower()
        if pole.get("teplota vody"):
            u["teplota_vody"] = pole["teplota vody"][:20]
        c = _cislo_reviru(revir)
        if c:
            u["revir_id"] = c
        out.append(u)
    return out


# ---------------- mrk.cz „Můj lov“ ----------------
MRK = "https://www.mrk.cz/mujlov"
_ZAPIS = re.compile(
    r'<a href="/clen\.php3\?id=(\d+)"[^>]*>Profil</a>.*?'
    r'<div\s+id="zprava(\d+)" class="zapistelo"><i>([\d.]+) - <b>(.*?)</b></i>(.*?)<ul class="rating"',
    re.S)


def _clean(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def _mrk(cutoff: date) -> list[dict]:
    first = get_text(MRK + "?id=7", encoding="iso-8859-2")
    m = re.search(r'href="\?id=7&page=(\d+)"[^>]*>\s*<span aria-hidden="true">&gt;</span>', first)
    page = int(m.group(1)) + 1 if m else None
    out, html_page, guard = [], first, 0
    while html_page and guard < 60:
        guard += 1
        oldest = None
        for user, zid, d, revir, body in _ZAPIS.findall(html_page):
            try:
                dt = datetime.strptime(d, "%d.%m.%Y").date()
            except ValueError:
                continue
            oldest = dt if oldest is None or dt < oldest else oldest
            if dt < cutoff or dt > date.today():
                continue
            out += _ulovky_ze_zapisu(dt.isoformat(), _clean(revir), _clean(body),
                                     f"{MRK}?users[]={user}#zapis{zid}", "mrk.cz – Můj lov")
        if oldest is None or oldest < cutoff or not page or page <= 1:
            break
        page -= 1
        html_page = get_text(f"{MRK}?id=7&page={page}", encoding="iso-8859-2", delay=1.0)
    log.info("mrk.cz: %d úlovků (%d stránek)", len(out), guard)
    return out


# ---------------- chytej.cz Trofejní úlovky ----------------
CHYTEJ = "https://www.chytej.cz/"


def _chytej(cutoff: date) -> list[dict]:
    out = []
    for rok in sorted({cutoff.year, date.today().year}):
        listing = get_text(f"{CHYTEJ}trofejni_ulovky/{rok}/")
        druh_pages = set(re.findall(rf'href="(trofejni_ulovky/[a-z-]+/{rok}/)"', listing))
        details = set(re.findall(rf'href="(trofejni_ulovky/[a-z-]+/{rok}/\d+/)"', listing))
        for p in druh_pages:
            details |= set(re.findall(rf'href="(trofejni_ulovky/[a-z-]+/{rok}/\d+/)"', get_text(CHYTEJ + p, delay=0.5)))
        for p in sorted(details):
            t = _clean(get_text(CHYTEJ + p, delay=0.5))
            m = re.search(r"Délka: ([\d.]+) cm Hmotnost: ([\d.]+) kg .*?Datum: (\d+)\.(\d+)\.(\d{4})"
                          r"(?:.*?Revír: (.*?)(?: – svazová voda| Způsob:| Nástraha:| Další úlovky))?"
                          r"(?:.*?Způsob: (.*?)(?= Nástraha:| Další úlovky))?(?:.*?Nástraha: (.*?)(?= Další úlovky| [A-ZÁ-Ž]))?", t)
            if not m:
                continue
            dt = date(int(m.group(5)), int(m.group(4)), int(m.group(3)))
            if dt < cutoff:
                continue
            druh = re.search(r"trofejni_ulovky/([a-z-]+)/", p).group(1).replace("-", " ")
            u = {"datum": dt.isoformat(), "druh": (druhy_v_textu(druh) or [druh])[0],
                 "delka_cm": float(m.group(1)) or None, "hmotnost_kg": float(m.group(2)) or None,
                 "revir_text": (m.group(6) or "").strip(), "zdroj": "chytej.cz – Trofejní úlovky",
                 "url": CHYTEJ + p}
            if m.group(7):
                u["metoda"] = m.group(7).strip().lower()
            if m.group(8):
                u["nastraha"] = m.group(8).strip().lower()
            c = _cislo_reviru(u["revir_text"])
            if c:
                u["revir_id"] = c
            out.append({k: v for k, v in u.items() if v not in (None, "")})
    log.info("chytej.cz: %d trofejních úlovků", len(out))
    return out


def fetch() -> list[dict]:
    cutoff = date.today() - timedelta(days=round(MESICU * 30.5))
    out = []
    for f in (_mrk, _chytej):
        try:
            out += f(cutoff)
        except Exception as e:  # noqa: BLE001 – jeden web nesmí shodit druhý
            log.warning("%s: %s", f.__name__, e)
    if not out:
        raise RuntimeError("žádný zdroj úlovků nic nevrátil")
    return out
