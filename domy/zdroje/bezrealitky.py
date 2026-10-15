"""Bezrealitky.cz – přímo od majitelů. Data z Next.js (apolloCache) výpisu a detailu."""
from __future__ import annotations

import json
import logging
import re

from ..config import MAX_CENA
from ..spolecne import (z_predchoziho, voda_z_textu, kanalizace_z_textu, Inzerat, get, typ_z_textu, poloha_z_textu, stavba_z_textu, vlastnosti_z_textu,
                        dispozice_z_textu)

NAZEV = "Bezrealitky"
log = logging.getLogger("domy")

OKRESY = ["okres-brno-venkov", "okres-brno-mesto"]
MAX_STRAN = 20

STAV = {"NEW": "novostavba", "VERY_GOOD": "velmi dobrý", "GOOD": "dobrý", "BAD": "špatný",
        "BEFORE_RECONSTRUCTION": "před rekonstrukcí", "AFTER_RECONSTRUCTION": "po rekonstrukci",
        "UNDER_CONSTRUCTION": "ve výstavbě", "CONSTRUCTION": "ve výstavbě", "PROJECT": "projekt",
        "IN_RECONSTRUCTION": "v rekonstrukci"}
STAVBA = {"BRICK": "cihla", "WOOD": "dřevostavba", "WOODEN": "dřevostavba", "MIXED": "smíšená",
          "PANEL": "panel", "STONE": "kámen", "PREFAB": "montovaná", "MONTOVANA": "montovaná", "SKELET": "montovaná"}
POLOHA = {"CORNER": "řadový", "TERRACED": "řadový", "MIDDLE": "řadový", "DETACHED": "samostatný", "SEMI_DETACHED": "dvojdům"}

_ND = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


def _next(html: str) -> dict:
    m = _ND.search(html)
    return json.loads(m.group(1))["props"]["pageProps"] if m else {}


def _pokoje(disp: str) -> tuple[str, int | None]:
    m = re.match(r"DISP_(\d+)_(KK|\d+)", disp or "")
    if not m:
        return "", None
    return f"{m.group(1)}+{m.group(2).lower()}", int(m.group(1))


def _seznam():
    for okres in OKRESY:
        videno = set()
        for strana in range(1, MAX_STRAN + 1):
            url = f"https://www.bezrealitky.cz/vypis/nabidka-prodej/dum/{okres}?priceTo={MAX_CENA}&page={strana}"
            pp = _next(get(url).text)
            cache = pp.get("apolloCache") or {}
            ads = [v for k, v in cache.items() if k.startswith("Advert:") and v.get("offerType") == "PRODEJ"]
            nove = [a for a in ads if a["id"] not in videno]
            if not nove:
                break
            for a in nove:
                videno.add(a["id"])
                yield a, cache


def stahni(znam: dict) -> list[Inzerat]:
    out = []
    for a, cache in _seznam():
        iid = f"br-{a['id']}"
        cena = a.get("price") or None
        if cena and cena > MAX_CENA:
            continue
        ins = z_predchoziho(znam.get(iid))
        if ins:
            ins.cena = cena
            out.append(ins)
            continue
        url = f"https://www.bezrealitky.cz/nemovitosti-byty-domy/{a['uri']}"
        try:
            d = _next(get(url).text).get("origAdvert") or {}
        except Exception as ex:
            log.warning("  bezrealitky detail %s: %s", url, ex)
            continue
        popis = d.get("descriptionByLocale") or d.get("description") or ""
        nazev = d.get("imageAltText") or a.get('imageAltText({"locale":"CS"})') or "Prodej domu"
        text = f"{nazev} {popis}"
        disp, n = _pokoje(d.get("disposition") or a.get("disposition"))
        if n is None:
            disp, n = dispozice_z_textu(text)
        gps = d.get("gps") or a.get("gps") or {}
        fotky = []
        for im in (d.get("publicImages") or [])[:3]:
            if isinstance(im, dict) and im.get("url"):
                fotky.append(im["url"])
        if not fotky:
            ref = (a.get("mainImage") or {}).get("__ref")
            if ref and cache.get(ref, {}).get("url"):
                fotky.append(cache[ref]["url"])
        ins = Inzerat(
            id=iid, zdroj=NAZEV, url=url, nazev=nazev, cena=cena,
            obec=d.get("city") or "", adresa=d.get("address") or a.get('address({"locale":"CS"})', ""),
            lat=gps.get("lat"), lon=gps.get("lng"), presnost="ulice" if d.get("street") else "obec",
            pokoje=n, dispozice=disp, uzitna=d.get("surface") or a.get("surface"),
            pozemek=d.get("surfaceLand") or a.get("surfaceLand"),
            typ=typ_z_textu(text), poloha=POLOHA.get(d.get("position") or "", "") or poloha_z_textu(nazev + " " + popis[:400]),
            stavba=STAVBA.get(d.get("construction") or "", "") or stavba_z_textu(text),
            stav=STAV.get(d.get("condition") or "", ""), penb=(d.get("penb") or "")[:1],
            rk="přímo od majitele", popis=popis, fotky=fotky, vlastnosti=vlastnosti_z_textu(text),
        )
        if d.get("garage") and "garáž" not in ins.vlastnosti:
            ins.vlastnosti.append("garáž")
        if d.get("cellar") and "sklep" not in ins.vlastnosti:
            ins.vlastnosti.append("sklep")
        w, sw = str(d.get("water") or "").upper(), str(d.get("sewage") or "").upper()
        ins.voda = ("vodovod" if "PUBLIC" in w or "MAINS" in w else "studna" if "WELL" in w else "") or voda_z_textu(popis)
        ins.kanalizace = ("veřejná kanalizace" if "PUBLIC" in sw or "SEWER" in sw else "septik/jímka" if "SEPTIC" in sw or "CESSPOOL" in sw
                          else "domácí ČOV" if "TREATMENT" in sw else "") or kanalizace_z_textu(popis)
        ins.garaz = True if d.get("garage") or "garáž" in ins.vlastnosti else None
        ins.sklep = True if d.get("cellar") or "sklep" in ins.vlastnosti else None
        ins.cerstvy = True
        out.append(ins)
    return out
