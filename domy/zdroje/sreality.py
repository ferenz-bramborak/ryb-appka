"""Sreality.cz – veřejné JSON API (stejné, jaké volá jejich web).

Sreality pokrývá i většinu brněnských realitek (RE/MAX, M&M, Bidli, Century 21,
lokální kanceláře), protože ty inzerují hlavně tady.
"""
from __future__ import annotations

import logging

from ..config import MAX_CENA
from ..spolecne import z_predchoziho, voda_z_textu, kanalizace_z_textu, Inzerat, get, dispozice_z_textu, typ_z_textu, poloha_z_textu, stavba_z_textu, vlastnosti_z_textu

NAZEV = "Sreality"
log = logging.getLogger("domy")

API = "https://www.sreality.cz/api/v1/estates"
OKRESY = "72,73"            # Brno-město, Brno-venkov
VYNECHAT_PODKATEGORIE = {33}  # chaty

POKOJE = {"1 pokoj": 1, "2 pokoje": 2, "3 pokoje": 3, "4 pokoje": 4, "5 a více pokojů": 5}
STAV = {
    "Novostavba": "novostavba", "Po rekonstrukci": "po rekonstrukci", "Velmi dobrý": "velmi dobrý",
    "Dobrý": "dobrý", "Před rekonstrukcí": "před rekonstrukcí", "Špatný": "špatný",
    "Ve výstavbě": "ve výstavbě", "Projekt": "projekt", "K demolici": "špatný", "V rekonstrukci": "v rekonstrukci",
}
STAVBA = {"Cihlová": "cihla", "Dřevostavba": "dřevostavba", "Smíšená": "smíšená", "Kamenná": "kámen",
          "Panelová": "panel", "Montovaná": "montovaná", "Skeletová": "montovaná", "Nízkoenergetická": ""}


def _seznam():
    off = 0
    while True:
        url = (f"{API}/search?category_main_cb=2&category_type_cb=1&locality_district_id={OKRESY}"
               f"&price_to={MAX_CENA}&limit=100&offset={off}&sort=-date")
        d = get(url).json()
        res = d.get("results") or []
        yield from res
        off += len(res)
        if not res or off >= d.get("pagination", {}).get("total", 0):
            break


def _poi(e) -> dict:
    def m(*keys):
        v = [e.get(f"poi_{k}_distance") for k in keys]
        v = [x for x in v if isinstance(x, (int, float)) and x < 50000]
        return int(min(v)) if v else None
    out = {"skolka": m("kindergarten"), "skola": m("school"), "obchod": m("small_shop", "shop"),
           "lekar": m("medic"), "bus": m("bus_public_transport", "tram"), "vlak": m("train")}
    return {k: v for k, v in out.items() if v is not None}


def _names(x) -> str:
    return ", ".join(i.get("name", "") for i in (x or []) if isinstance(i, dict))


def _nm(x):
    return (x or {}).get("name") or ""


def stahni(znam: dict) -> list[Inzerat]:
    out = []
    for e in _seznam():
        if (e.get("category_sub_cb") or {}).get("value") in VYNECHAT_PODKATEGORIE:
            continue
        hid = e["hash_id"]
        iid = f"sr-{hid}"
        loc = e.get("locality") or {}
        cena = int(e.get("price_czk") or 0) or None
        if cena is not None and cena <= 1:
            cena = None
        ins = z_predchoziho(znam.get(iid))
        if ins:
            ins.cena = cena
            ins.poi = _poi(e)
            out.append(ins)
            continue
        try:
            r = get(f"{API}/{hid}").json()["result"]
        except Exception as ex:  # detail selhal – přeskočit, zkusí se příště
            log.warning("  sreality detail %s: %s", hid, ex)
            continue
        text = f"{r.get('advert_name','')} {r.get('advert_description','')}"
        disp, n = dispozice_z_textu(text)
        pokoje = POKOJE.get(_nm(r.get("room_count_cb")))
        if pokoje == 5 and n and n > 5:
            pokoje = n
        if pokoje is None:
            pokoje = n
        typ = "bungalov" if _nm(r.get("object_type")) == "Přízemní" else ("patrový" if _nm(r.get("object_type")) == "Patrový" else "")
        typ = typ_z_textu(text) or typ
        kind = _nm(r.get("object_kind"))
        poloha = {"Řadový": "řadový", "Rohový": "řadový", "V bloku": "řadový", "Samostatný": "samostatný"}.get(kind, "") or poloha_z_textu(r.get("advert_name", ""))
        stavba = STAVBA.get(_nm(r.get("building_type")), "") or stavba_z_textu(text)
        stav = STAV.get(_nm(r.get("building_condition")), "")
        u = r.get("user") or {}
        prem = (r.get("premise") or {})
        rk = u.get("user_name") or ""
        seo = (prem.get("company") or {})
        fotky = []
        for im in (r.get("advert_images") or [])[:3]:
            src = im if isinstance(im, str) else (im.get("advert_image_sdn_url") or im.get("url") or "")
            if src:
                fotky.append(("https:" + src) if src.startswith("//") else src)
        if not fotky:
            fotky = [("https:" + s) if s.startswith("//") else s for s in (e.get("advert_images") or [])[:3]]
        rl = r.get("locality") or loc
        ins = Inzerat(
            id=iid, zdroj=NAZEV,
            url=f"https://www.sreality.cz/detail/prodej/dum/rodinny/{loc.get('city_seo_name') or 'x'}/{hid}",
            nazev=r.get("advert_name") or e.get("advert_name", ""),
            cena=cena,
            obec=rl.get("city") or loc.get("city") or "",
            adresa=", ".join(x for x in [rl.get("street"), rl.get("citypart") or rl.get("city")] if x),
            lat=rl.get("gps_lat") or loc.get("gps_lat"), lon=rl.get("gps_lon") or loc.get("gps_lon"),
            presnost={"address": "adresa", "street": "ulice", "ward": "obec"}.get(loc.get("inaccuracy_type") or "", "adresa"),
            pokoje=pokoje, dispozice=disp,
            uzitna=r.get("usable_area") or r.get("floor_area"),
            pozemek=r.get("estate_area"),
            typ=typ, poloha=poloha, stavba=stavba, stav=stav,
            penb=(_nm(r.get("energy_efficiency_rating_cb")) or "")[:1],
            rk=rk, popis=r.get("advert_description") or "", fotky=fotky,
            vlastnosti=vlastnosti_z_textu(text),
        )
        voda = _names(r.get("water_set")).lower()
        ins.voda = ("vodovod + studna" if "dálkový" in voda and "místní" in voda else "vodovod" if "dálkový" in voda
                    else "studna" if "místní" in voda or "studna" in voda else "") or voda_z_textu(text)
        odp = _names(r.get("gully_set")).lower()
        ins.kanalizace = ("veřejná kanalizace" if "veřejná" in odp else "domácí ČOV" if "čov" in odp
                          else "septik/jímka" if "septik" in odp or "jímka" in odp else "") or kanalizace_z_textu(text)
        ins.garaz = True if r.get("garage") or "garáž" in ins.vlastnosti else None
        ins.sklep = True if r.get("cellar") or "sklep" in ins.vlastnosti else None
        ins.poi = _poi(e)
        ins.cerstvy = True
        if ins.garaz and "garáž" not in ins.vlastnosti:
            ins.vlastnosti.append("garáž")
        out.append(ins)
    return out
