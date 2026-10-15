"""Český rybářský svaz – všechny revíry všech 7 územních svazů (Čechy + ČRS
na severní Moravě a ve Slezsku) z veřejného API webu rybsvaz.cz.

  /reviry?from&size                  seznam (typ P/MP, MO, ÚS)
  /reviry/by-friendly-url/<url>      detail: popis, délka, rozloha, GPS, polygon (S-JTSK)
  /reviry/by-sid/<sid>/podminky      pravidla lovu platná k datu (?datum=YYYY-MM-DD)
"""
from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date

from ..geo import sjtsk_geojson_to_wgs, tok_z_nazvu
from ..http import get_json

NAZEV = "ČRS"
DRUH = "reviry"

API = "https://www.rybsvaz.cz/proxy/api/public"
WEB = "https://www.rybsvaz.cz/karta-reviru/-/"
log = logging.getLogger(__name__)

TYP = {"PSTRUHOVY": "pstruhovy", "MIMOPSTRUHOVY": "mimopstruhovy"}


def _cislo(c: str) -> str:
    return f"{c[:3]} {c[3:]}" if len(c) == 6 else c


def _kontakt(o: dict | None) -> dict | None:
    if not o:
        return None
    return {k: v for k, v in {
        "nazev": o.get("nazev"),
        "email": o.get("email"),
        "tel": o.get("telefon"),
        "web": o.get("webUrl"),
        "adresa": (o.get("adresa") or {}).get("uplnaAdresa"),
    }.items() if v}


def _list() -> list[dict]:
    items, start, size = [], 0, 200
    while True:
        page = get_json(f"{API}/reviry?from={start}&size={size}")["items"]
        items += page
        if len(page) < size:
            return items
        start += size


def _valid(entries: list[dict], today: str) -> list[dict]:
    return [e for e in entries or [] if e.get("platny", True)
            and (e.get("datumOd") or "0000") <= today <= (e.get("datumDo") or "9999")]


def _pravidla(sid: str, today: str) -> dict | None:
    try:
        p = get_json(f"{API}/reviry/by-sid/{sid}/podminky?datum={today}")
    except Exception as e:  # noqa: BLE001
        log.warning("podmínky %s: %s", sid, e)
        return None
    doba = _valid(p.get("denniDobaLovu"), today)
    out = {"platne_k": today}
    if doba:
        d = doba[0]
        out["doba_lovu"] = "zakázáno" if d.get("jeZakazano") else f"{d.get('hodOd')}–{d.get('hodDo')}"
    out["limity"] = [e["popis"].strip() for e in _valid(p.get("limitPonechanychRyb"), today) if e.get("popis")]
    out["zpusoby"] = [{"nazev": e["druhRybolovneTech"]["popis"].strip(), "povoleno": not e.get("jeZakazano")}
                      for e in _valid(p.get("rybolovnaTechnika"), today) if e.get("druhRybolovneTech")]
    out["podminky"] = [{"nazev": e["druhPodminkyLovu"]["popis"].strip(), "povoleno": not e.get("jeZakazano")}
                       for e in _valid(p.get("podminkaLovu"), today) if e.get("druhPodminkyLovu")]
    out["vybava"] = [e["predmet"]["popis"].strip() for e in _valid(p.get("povinnaVybava"), today)
                     if e.get("predmet") and e.get("jePovinne")]
    druhy = {}
    for e in _valid(p.get("miryAHajeni"), today):
        if not e.get("druhRyby"):
            continue
        druhy[e["druhRyby"]["popis"]] = {
            "druh": e["druhRyby"]["popis"],
            "hajen": bool(e.get("jeHajen")),
            "mira": e.get("dolniMira"),
            "horni_mira": e.get("horniMira"),
        }
    out["druhy"] = sorted(druhy.values(), key=lambda d: (d["hajen"], d["druh"]))
    return out


_GPS = re.compile(r"(\d{1,2})°\s*(\d{1,2})['‘’´]\s*([\d.,]+)[\"“”″']*\s*N[,\s]+(\d{1,2})°\s*(\d{1,2})['‘’´]\s*([\d.,]+)[\"“”″']*\s*E")


def gps_z_popisu(text: str) -> list[dict]:
    pts = []
    for m in _GPS.finditer(text or ""):
        d1, m1, s1, d2, m2, s2 = m.groups()
        lat = int(d1) + int(m1) / 60 + float(s1.replace(",", ".")) / 3600
        lon = int(d2) + int(m2) / 60 + float(s2.replace(",", ".")) / 3600
        if 48 < lat < 51.2 and 12 < lon < 19:
            pts.append({"lat": round(lat, 5), "lon": round(lon, 5)})
    return pts


def _detail(item: dict, today: str) -> dict | None:
    try:
        d = get_json(f"{API}/reviry/by-friendly-url/{item['friendlyUrl']}")
    except Exception as e:  # noqa: BLE001
        log.warning("revír %s: %s", item.get("cislo"), e)
        d = item
    popis = (d.get("popis") or "").strip()
    geom = None
    try:
        geom = sjtsk_geojson_to_wgs(d.get("uzemniVymezeni"))
    except Exception as e:  # noqa: BLE001
        log.debug("geometrie %s: %s", item.get("cislo"), e)
    gps = gps_z_popisu(popis)
    if d.get("gpsSouradniceSirka") and d.get("gpsSouradniceDelka"):
        gps.append({"lat": round(float(d["gpsSouradniceSirka"]), 5), "lon": round(float(d["gpsSouradniceDelka"]), 5)})
    if not gps and geom:
        gps = [geom["stred"]]
    us = (d.get("uzemniSvaz") or item.get("uzemniSvaz") or {})
    org = d.get("organizace") or item.get("organizace") or {}
    rec = {
        "id": item["cislo"],
        "cislo": _cislo(item["cislo"]),
        "nazev": item["oficialniNazev"].strip(),
        "svaz": "ČRS – " + ((us.get("nazev") or "").replace(" územní svaz", " ÚS") or "Republiková rada"),
        "typ": TYP.get((item.get("typReviru") or {}).get("kod"), "neuveden"),
        "mo": org.get("nazev"),
        "tok": tok_z_nazvu(item["oficialniNazev"]),
        "rmv": bool(item.get("mistniVyznam")),
        "lov_z_lodi": bool(item.get("lovZLodky")),
        "lov_nonstop": bool(item.get("lovNonstop")),
        "handicap": bool(item.get("vhodneHandicap")),
        "delka_km": d.get("delka"),
        "vymera_ha": d.get("rozloha"),
        "popis": popis or None,
        "url": WEB + item["friendlyUrl"],
        "kontakty": {k: v for k, v in {"uzivatel": _kontakt(us), "mo": _kontakt(org)}.items() if v},
        "gps": gps,
        "geom": geom,
        "pravidla": _pravidla(item["sid"], today),
        "_sid": item["sid"],
    }
    return rec


def fetch(limit: int | None = None):
    today = date.today().isoformat()
    items = [i for i in _list() if i.get("cislo")]
    if limit:
        items = items[:limit]
    log.info("ČRS: %d revírů v seznamu", len(items))
    with ThreadPoolExecutor(max_workers=6) as pool:
        reviry = [r for r in pool.map(lambda i: _detail(i, today), items) if r]
    return reviry
