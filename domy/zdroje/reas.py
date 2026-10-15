"""Reas.cz – Next.js data z výpisu (stránkování ?listPage=N) a detailu."""
from __future__ import annotations

import json
import logging
import re

from ..config import MAX_CENA
from ..spolecne import (z_predchoziho, voda_z_textu, kanalizace_z_textu, Inzerat, get, typ_z_textu, poloha_z_textu, stavba_z_textu, vlastnosti_z_textu,
                        dispozice_z_textu, pokoje_z_textu)

NAZEV = "Reas"
log = logging.getLogger("domy")

OKRESY = ["okres-brno-venkov", "okres-brno-mesto"]
MAX_STRAN = 40
STAVBA = {"brick": "cihla", "wooden": "dřevostavba", "wood": "dřevostavba", "mixed": "smíšená",
          "panel": "panel", "stone": "kámen", "prefabricated": "montovaná", "skeleton": "montovaná"}
POLOHA = {"terraced": "řadový", "corner": "řadový", "detached": "samostatný", "semi_detached": "dvojdům", "semiDetached": "dvojdům"}

_ND = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


def _next(html: str) -> dict:
    m = _ND.search(html)
    return json.loads(m.group(1))["props"]["pageProps"] if m else {}


def _seznam():
    for okres in OKRESY:
        videno = set()
        for strana in range(1, MAX_STRAN + 1):
            url = f"https://www.reas.cz/prodej/domy/{okres}" + (f"?listPage={strana}" if strana > 1 else "")
            r = _next(get(url).text).get("adsListResult") or {}
            nove = [a for a in r.get("data") or [] if a["_id"] not in videno]
            if not nove:
                break
            for a in nove:
                videno.add(a["_id"])
                yield a
            if not r.get("nextPage"):
                break


def stahni(znam: dict) -> list[Inzerat]:
    out = []
    for a in _seznam():
        cena = a.get("price") or None
        if cena and cena > MAX_CENA:
            continue
        if a.get("subType") not in (None, "family_house", "villa", "cottage", "farm_house"):
            continue
        iid = f"re-{a['_id']}"
        ins = z_predchoziho(znam.get(iid))
        if ins:
            ins.cena = cena
            out.append(ins)
            continue
        try:
            d = _next(get(a["link"]).text).get("adEstateDetail") or {}
            d = d.get("data", d)
        except Exception as ex:
            log.warning("  reas detail %s: %s", a.get("link"), ex)
            continue
        p = d.get("property") or {}
        popis = d.get("description") or ""
        plocha = a.get("displayArea") or p.get("utilityArea")
        poz = a.get("landArea") or p.get("landArea")
        nazev = "Prodej domu" + (f" {plocha} m²" if plocha else "") + (f", pozemek {poz} m²" if poz else "")
        text = f"{nazev} {popis}"
        disp, n = dispozice_z_textu(popis)
        coords = (a.get("point") or {}).get("coordinates") or [None, None]
        typ = typ_z_textu(text) or ("bungalov" if p.get("floorsCount") == 1 else "")
        fotky = [im.get("preview") or im.get("original") for im in (a.get("imagesWithMetadata") or [])[:3]]
        loc = d.get("localityInfo") or {}
        ins = Inzerat(
            id=iid, zdroj=NAZEV, url=a["link"], nazev=nazev, cena=cena,
            obec=loc.get("municipality") or a.get("formattedLocation", "").split(",")[-1].strip(),
            adresa=a.get("formattedAddress") or "",
            lat=coords[1], lon=coords[0], presnost="adresa" if d.get("cuzkAddressId") else "obec",
            pokoje=n or pokoje_z_textu(popis), dispozice=disp,
            uzitna=plocha, pozemek=a.get("landArea") or p.get("landArea"),
            typ=typ, poloha=POLOHA.get(p.get("separation") or "", "") or poloha_z_textu(nazev + " " + popis[:400]),
            stavba=STAVBA.get(p.get("constructionType") or "", "") or stavba_z_textu(text),
            stav="", penb=(p.get("energyClass") or "")[:1],
            rk=((a.get("companyDetails") or {}).get("name") or (a.get("sellerDetails") or {}).get("name") or ""),
            popis=popis, fotky=[f for f in fotky if f], vlastnosti=vlastnosti_z_textu(text),
        )
        ins.voda = voda_z_textu(popis)
        ins.kanalizace = ("veřejná kanalizace" if p.get("sewerageConnection") else "") or kanalizace_z_textu(popis)
        ins.garaz = True if "garáž" in ins.vlastnosti else None
        ins.sklep = True if p.get("cellar") or "sklep" in ins.vlastnosti else None
        ins.cerstvy = True
        out.append(ins)
    return out
