"""ČHMÚ – aktuální vodní stavy, průtoky, teplota vody a stupně povodňové
aktivity z otevřených dat (opendata.chmi.cz/hydrology/now/).

metadata/meta1.json  – seznam stanic s polohou, tokem a limity SPA
data/<objID>.json    – časové řady za poslední hodiny (H, Q, TH, …)
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from ..http import get_json

NAZEV = "ČHMÚ"
DRUH = "voda"

BASE = "https://opendata.chmi.cz/hydrology/now"
log = logging.getLogger(__name__)


def _rows(doc: dict) -> list[dict]:
    coll = doc["data"]["data"]
    header = coll["header"].split(",")
    return [dict(zip(header, v)) for v in coll["values"]]


def _series(doc: dict) -> dict[str, list[tuple[datetime, float]]]:
    out = {}
    for obj in doc.get("objList", []):
        for ts in obj.get("tsList", []):
            pts = [
                (datetime.fromisoformat(p["dt"].replace("Z", "+00:00")), float(p["value"]))
                for p in ts.get("tsData", [])
                if p.get("value") is not None
            ]
            if pts:
                out[ts["tsConID"]] = sorted(pts)
    return out


def _trend(pts: list[tuple[datetime, float]], tolerance: float) -> str | None:
    """Porovná poslední hodnotu s hodnotou zhruba před 3 hodinami."""
    if len(pts) < 2:
        return None
    last_t, last_v = pts[-1]
    older = [v for t, v in pts if t <= last_t - timedelta(hours=3)]
    ref = older[-1] if older else pts[0][1]
    if last_v - ref > tolerance:
        return "roste"
    if ref - last_v > tolerance:
        return "klesá"
    return "stálý"


def _spa(meta: dict, h: float | None, q: float | None) -> int:
    typ = meta.get("SPA_TYP")
    value, prefix = (h, "SPA{}H") if typ == "H" else (q, "SPA{}Q") if typ == "Q" else (None, "")
    if value is None:
        return 0
    level = 0
    for i in (1, 2, 3):
        limit = meta.get(prefix.format(i))
        if limit is not None and value >= float(limit):
            level = i
    return level


def _station(meta: dict) -> dict:
    obj_id = meta["objID"]
    try:
        series = _series(get_json(f"{BASE}/data/{obj_id}.json"))
    except Exception as e:  # noqa: BLE001 – chybějící soubor jedné stanice nevadí
        log.debug("stanice %s: %s", obj_id, e)
        series = {}
    h = series.get("H")
    q = series.get("Q")
    th = series.get("TH")
    last = max((s[-1][0] for s in (h, q, th) if s), default=None)
    rec = {
        "id": obj_id,
        "nazev": meta["STATION_NAME"],
        "tok": meta.get("STREAM_NAME"),
        "lat": round(float(meta["GEOGR1"]), 5),
        "lon": round(float(meta["GEOGR2"]), 5),
        "cas": last.isoformat() if last else None,
        "stav_cm": h[-1][1] if h else None,
        "prutok_m3s": q[-1][1] if q else None,
        "teplota_vody": th[-1][1] if th else None,
        "trend": _trend(h, 2) if h else None,
        "spa": _spa(meta, h[-1][1] if h else None, q[-1][1] if q else None),
        "url": meta.get("WWW_CHMI"),
    }
    return {k: v for k, v in rec.items() if v is not None}


def fetch() -> list[dict]:
    metas = [m for m in _rows(get_json(f"{BASE}/metadata/meta1.json")) if m.get("GEOGR1") and m.get("GEOGR2")]
    try:  # meta3 obsahuje mimo jiné odkaz na stránku stanice na webu ČHMÚ
        www = {m["objID"]: m.get("WWW_CHMI") for m in _rows(get_json(f"{BASE}/metadata/meta3.json"))}
        for m in metas:
            m["WWW_CHMI"] = www.get(m["objID"])
    except Exception as e:  # noqa: BLE001
        log.debug("meta3: %s", e)
    with ThreadPoolExecutor(max_workers=8) as pool:
        stations = [s for s in pool.map(_station, metas) if s]
    return [s for s in stations if "stav_cm" in s or "prutok_m3s" in s]
