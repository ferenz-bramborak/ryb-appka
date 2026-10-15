"""Oficiální statistika úlovků ČRS po revírech a druzích (z povolenek, roční).

API vrací pro revír a druh ryby počty kusů a kg po letech. Dotaz je potřeba
poslat pro každý druh zvlášť, proto se statistika stahuje jen jednou měsíčně
(roční data se během roku nemění).
"""
from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ..http import get_json

NAZEV = "Statistika ČRS"
DRUH = "statistika"

API = "https://www.rybsvaz.cz/proxy/api/public"
log = logging.getLogger(__name__)
CRS_CACHE = Path(__file__).resolve().parents[2] / "data-cache" / "crs.json"

# id druhu v API → název v aplikaci
DRUHY = {
    9: "kapr", 22: "štika", 4: "candát", 14: "okoun", 23: "sumec", 1: "amur", 11: "lín",
    5: "cejn", 3: "bolen", 8: "jelec tloušť", 16: "parma", 25: "úhoř", 13: "mník jednovousý",
    18: "pstruh duhový", 19: "pstruh obecný", 12: "lipan", 21: "siven", 6: "hlavatka",
    10: "karas", 15: "ostroretka", 17: "podoustev", 2: "bílá ryba",
}
ROKU = 3


def _rok_data(sid: str, druh_id: int) -> dict[int, dict]:
    items = get_json(f"{API}/statistika/{sid}/ulovky?idRyby={druh_id}")["items"]
    return {i["rok"]: i["statistikaUlovku"] for i in items}


def _revir(rec: dict) -> tuple[str, dict] | None:
    sid = rec["_sid"]
    try:
        celkem = _rok_data(sid, 0)
    except Exception as e:  # noqa: BLE001
        log.debug("statistika %s: %s", rec["id"], e)
        return None
    roky = sorted(celkem, reverse=True)[:ROKU]
    if not roky:
        return rec["id"], {"roky": []}
    out = {"roky": [{"rok": r, "ks": celkem[r]["ks"], "kg": round(celkem[r]["kg"], 1)} for r in roky], "druhy": []}
    for druh_id, nazev in DRUHY.items():
        try:
            d = _rok_data(sid, druh_id)
        except Exception:  # noqa: BLE001
            continue
        rows = [{"rok": r, "ks": d[r]["ks"], "kg": round(d[r]["kg"], 1)} for r in roky if r in d and d[r]["ks"]]
        if rows:
            out["druhy"].append({"druh": nazev, "roky": rows})
    last = roky[0]
    out["druhy"].sort(key=lambda x: -next((r["ks"] for r in x["roky"] if r["rok"] == last), 0))
    return rec["id"], out


def fetch(limit: int | None = None) -> dict[str, dict]:
    reviry = json.loads(CRS_CACHE.read_text("utf-8"))
    if limit:
        reviry = reviry[:limit]
    with ThreadPoolExecutor(max_workers=8) as pool:
        res = dict(r for r in pool.map(_revir, reviry) if r)
    if not res:
        raise RuntimeError("statistika nevrátila nic")
    log.info("Statistika ČRS: %d revírů", len(res))
    return res
