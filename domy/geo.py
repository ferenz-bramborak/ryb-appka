"""Lesy, reliéf a dojezdy autem pro jednotlivé domy."""
from __future__ import annotations

import logging
import math
from functools import lru_cache
from pathlib import Path

import numpy as np

from .config import RODINA, BRNO_CENTRUM, D1_EXITY, HRANICE
from .spolecne import get

log = logging.getLogger("domy")
MRIZKA = Path(__file__).resolve().parent / "data" / "geo_mrizka.npz"
OSRM = "https://router.project-osrm.org/table/v1/driving/"


@lru_cache(maxsize=1)
def _m():
    z = np.load(MRIZKA)
    return z["les"], z["vyska"], tuple(z["bbox"]), float(z["krok"])


def _bunka(lat, lon):
    les, _, (lat0, lon0, lat1, lon1), k = _m()
    r = int((lat1 - lat) / k)
    c = int((lon - lon0) / k)
    if 0 <= r < les.shape[0] and 0 <= c < les.shape[1]:
        return r, c
    return None


def priroda(lat: float, lon: float) -> dict | None:
    """Vzdálenost k lesu, podíl lesa v okolí a členitost terénu."""
    b = _bunka(lat, lon)
    if b is None:
        return None
    les, vys, _, k = _m()
    r, c = b
    dy = k * 111_320                       # m na buňku (sever–jih)
    dx = k * 111_320 * math.cos(math.radians(lat))
    R = 3000
    ry, rx = int(R / dy) + 1, int(R / dx) + 1
    r0, r1, c0, c1 = max(0, r - ry), min(les.shape[0], r + ry + 1), max(0, c - rx), min(les.shape[1], c + rx + 1)
    L = les[r0:r1, c0:c1].astype(np.float32)
    V = vys[r0:r1, c0:c1].astype(np.float32)
    yy, xx = np.mgrid[r0:r1, c0:c1]
    d = np.hypot((yy - r) * dy, (xx - c) * dx)
    # „les“ = buňka s aspoň 60 % stromů, ignorují se osamělé stromy/zahrady:
    # buňka musí mít i v okolí 3×3 průměr ≥ 50 %
    pad = np.pad(L, 1, mode="edge")
    okoli = sum(pad[i:i + L.shape[0], j:j + L.shape[1]] for i in range(3) for j in range(3)) / 9
    lesni = (L >= 60) & (okoli >= 50)
    les_m = int(d[lesni].min()) if lesni.any() else None
    v1k = d <= 1000
    v2k = d <= 2000
    v15 = d <= 1500
    return {
        "les_m": les_m if les_m is None or les_m <= R else None,
        "les_1km": int(round(L[v1k].mean())),
        "les_2km": int(round(L[v2k].mean())),
        "vyska": int(vys[r, c]),
        "prevyseni": int(V[v15].max() - V[v15].min()),
        "clenitost": int(round(V[v15].std())),
    }


def _cil():
    cile = [(k, la, lo) for k, _, la, lo in RODINA] + [(x[0], x[2], x[3]) for x in (BRNO_CENTRUM, HRANICE)]
    cile += [(f"d1:{n}", la, lo) for n, la, lo in D1_EXITY]
    return cile


def dojezdy(body: list[tuple[str, float, float]]) -> dict[str, dict]:
    """Dojezd autem (minuty) z každého domu k rodině, do Brna a k nejbližšímu exitu D1.

    Používá veřejný OSRM server (OpenStreetMap). Při výpadku vrací prázdno
    a aplikace ukáže jen vzdušné vzdálenosti.
    """
    cile = _cil()
    out: dict[str, dict] = {}
    for i in range(0, len(body), 35):
        davka = body[i:i + 35]
        coords = ";".join(f"{lo:.5f},{la:.5f}" for _, la, lo in davka) + ";" + ";".join(f"{lo:.5f},{la:.5f}" for _, la, lo in cile)
        src = ";".join(str(j) for j in range(len(davka)))
        dst = ";".join(str(len(davka) + j) for j in range(len(cile)))
        try:
            d = get(f"{OSRM}{coords}?sources={src}&destinations={dst}&annotations=duration", pauza=1.0).json()
            if d.get("code") != "Ok":
                raise RuntimeError(d.get("message") or d.get("code"))
        except Exception as ex:
            log.warning("  OSRM: %s", ex)
            continue
        for (iid, _, _), row in zip(davka, d["durations"]):
            res, d1 = {}, None
            for (k, _, _), sec in zip(cile, row):
                if sec is None:
                    continue
                mins = round(sec / 60)
                if k.startswith("d1:"):
                    if d1 is None or mins < d1[1]:
                        d1 = (k[3:], mins)
                else:
                    res[k] = mins
            if d1:
                res["d1"], res["d1_exit"] = d1[1], d1[0]
            out[iid] = res
    return out
