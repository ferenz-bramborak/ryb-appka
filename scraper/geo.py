"""Geometrie revírů: převod S-JTSK → WGS84, zjednodušení a pomocné výpočty."""
from __future__ import annotations

import re
import unicodedata

from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform

_sjtsk = Transformer.from_crs(5514, 4326, always_xy=True)

# Tolerance zjednodušení v metrech (S-JTSK je v metrech) a ve stupních pro WGS84.
SIMPLIFY_M = 25
SIMPLIFY_DEG = 0.0002


def _rings(geom) -> list[list[list[float]]]:
    """Vrátí seznam linií/obrysů jako [[lat, lon], ...] se 5 desetinnými místy."""
    out = []
    parts = getattr(geom, "geoms", [geom])
    for g in parts:
        if g.geom_type == "Polygon":
            coords = list(g.exterior.coords)
        elif g.geom_type in ("LineString", "LinearRing"):
            coords = list(g.coords)
        elif g.geom_type == "Point":
            coords = [g.coords[0]]
        else:
            out += _rings(g)
            continue
        out.append([[round(y, 5), round(x, 5)] for x, y in coords])
    return out


def sjtsk_geojson_to_wgs(gj: dict) -> dict | None:
    """GeoJSON v S-JTSK (EPSG:5514) → {"typ": "polygon"|"linie", "casti": [...], "stred": {...}, "bbox": [...]}."""
    if not gj or not gj.get("coordinates"):
        return None
    g = shape(gj)
    if g.is_empty:
        return None
    g = g.simplify(SIMPLIFY_M, preserve_topology=True)
    wgs = transform(_sjtsk.transform, g)
    return _describe(wgs)


def wgs_to_desc(g) -> dict | None:
    if g is None or g.is_empty:
        return None
    return _describe(g.simplify(SIMPLIFY_DEG, preserve_topology=True))


def _describe(wgs) -> dict:
    minx, miny, maxx, maxy = wgs.bounds
    c = wgs.representative_point()
    typ = "polygon" if "Polygon" in wgs.geom_type else "linie" if "Line" in wgs.geom_type else "bod"
    return {
        "typ": typ,
        "casti": _rings(wgs),
        "stred": {"lat": round(c.y, 5), "lon": round(c.x, 5)},
        "bbox": [round(miny, 5), round(minx, 5), round(maxy, 5), round(maxx, 5)],
    }


def strip_accents(s: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", s) if unicodedata.category(ch) != "Mn")


def norm(s: str | None) -> str:
    s = strip_accents((s or "").lower())
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", s)).strip()


_SUFFIX = re.compile(r"(\s+(\d+[a-z]?|[a-z]|p|mp|mrs|horní|dolní|i+))+$", re.I)


def tok_z_nazvu(nazev: str) -> str | None:
    """'BEČVA 2 A' → 'Bečva', 'LABE 9' → 'Labe'. U nádrží a rybníků vrací celé jméno."""
    n = re.split(r"\s+[-–]\s+", nazev)[0].strip()
    n = _SUFFIX.sub("", n).strip()
    return n.title() if n else None
