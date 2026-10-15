"""(Vyžaduje navíc: pip install rasterio)

Jednorázově sestaví mřížku lesů a nadmořské výšky pro okolí Brna.

Lesy:   ESA WorldCover 2021 (10 m, třída 10 = stromy), agregováno na ~90×60 m buňky.
Reliéf: Copernicus DEM GLO-30, převzorkováno na stejnou mřížku.

Výsledek: domy/data/geo_mrizka.npz (commitnutý, stahování trvá pár minut).
Spuštění: python -m domy.geo_sestav
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.windows import from_bounds

from .config import GEO_BBOX

OUT = Path(__file__).resolve().parent / "data" / "geo_mrizka.npz"
KROK = 10 * 8.333333333333333e-05   # stupně; 10 pixelů WorldCoveru
WC = "/vsicurl/https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_N48E015_Map.tif"
DEM = "/vsicurl/https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N{lat:02d}_00_E{lon:03d}_00_DEM/Copernicus_DSM_COG_10_N{lat:02d}_00_E{lon:03d}_00_DEM.tif"


def main():
    lat0, lon0, lat1, lon1 = GEO_BBOX
    ny = round((lat1 - lat0) / KROK)
    nx = round((lon1 - lon0) / KROK)
    print(f"mřížka {ny}×{nx}")
    with rasterio.open(WC) as src:
        w = from_bounds(lon0, lat0, lon1, lat1, src.transform).round_offsets().round_lengths()
        a = src.read(1, window=w)
    a = a[: ny * 10, : nx * 10]
    les = (a == 10).reshape(ny, 10, nx, 10).mean(axis=(1, 3))
    les = (les * 100).round().astype(np.uint8)          # % lesa v buňce, řádek 0 = sever

    vys = np.zeros((ny, nx), dtype=np.float32)
    for tlat in range(int(lat0), int(np.ceil(lat1))):
        for tlon in range(int(lon0), int(np.ceil(lon1))):
            b_lat0, b_lat1 = max(lat0, tlat), min(lat1, tlat + 1)
            b_lon0, b_lon1 = max(lon0, tlon), min(lon1, tlon + 1)
            if b_lat0 >= b_lat1 or b_lon0 >= b_lon1:
                continue
            r0 = round((lat1 - b_lat1) / KROK); r1 = round((lat1 - b_lat0) / KROK)
            c0 = round((b_lon0 - lon0) / KROK); c1 = round((b_lon1 - lon0) / KROK)
            with rasterio.open(DEM.format(lat=tlat, lon=tlon)) as src:
                w = from_bounds(b_lon0, b_lat0, b_lon1, b_lat1, src.transform)
                vys[r0:r1, c0:c1] = src.read(1, window=w, out_shape=(r1 - r0, c1 - c0), resampling=Resampling.average)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(OUT, les=les, vyska=vys.round().astype(np.int16),
                        bbox=np.array(GEO_BBOX), krok=np.array(KROK))
    print(f"zapsáno {OUT} ({OUT.stat().st_size // 1024} kB), les průměr {les.mean():.1f} %")


if __name__ == "__main__":
    main()
