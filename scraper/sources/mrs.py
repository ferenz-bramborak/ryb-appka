"""Moravský rybářský svaz – revíry z veřejného API webu mrsbrno.cz
(stejné API používá jejich web, klíč publikuje v /appsettings.json)
a geometrie revírů z veřejné mapy MRS (Google My Maps, KML).
"""
from __future__ import annotations

import html
import logging
import re
from concurrent.futures import ThreadPoolExecutor

from lxml import etree
from shapely.geometry import LineString, MultiLineString, MultiPolygon, Point, Polygon
from shapely.ops import unary_union

from ..geo import tok_z_nazvu, wgs_to_desc
from ..http import get, get_json
from .crs import gps_z_popisu

NAZEV = "MRS"
DRUH = "reviry"

WEB = "https://mrsbrno.cz"
log = logging.getLogger(__name__)
KML_NS = {"k": "http://www.opengis.net/kml/2.2"}


def _html_to_text(s: str | None) -> str | None:
    if not s:
        return None
    s = re.sub(r"<br\s*/?>|</p>|</li>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s).replace("\xa0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n", s)
    s = re.sub(r"^\s*Popis revíru:\s*\n", "", s.strip())
    return s.strip() or None


def _coords(text: str) -> list[tuple[float, float]]:
    out = []
    for p in (text or "").split():
        parts = p.split(",")
        if len(parts) >= 2:
            out.append((float(parts[0]), float(parts[1])))
    return out


def _kml_geometries(kml_url: str) -> dict[str, object]:
    """Číslo revíru → shapely geometrie (polygony a linie, body ignoruje)."""
    root = etree.fromstring(get(kml_url, timeout=120).content)
    geoms: dict[str, list] = {}
    for pm in root.iterfind(".//k:Placemark", KML_NS):
        name = pm.findtext("k:name", namespaces=KML_NS) or ""
        m = re.match(r"\s*(\d{3})\s?(\d{3})", name)
        if not m:
            continue
        code = m.group(1) + m.group(2)
        for poly in pm.iterfind(".//k:Polygon", KML_NS):
            ring = _coords(poly.findtext(".//k:outerBoundaryIs//k:coordinates", namespaces=KML_NS))
            if len(ring) >= 3:
                geoms.setdefault(code, []).append(Polygon(ring))
        for line in pm.iterfind(".//k:LineString", KML_NS):
            pts = _coords(line.findtext("k:coordinates", namespaces=KML_NS))
            if len(pts) >= 2:
                geoms.setdefault(code, []).append(LineString(pts))
    out = {}
    for code, parts in geoms.items():
        polys = [p.buffer(0) for p in parts if isinstance(p, Polygon)]
        lines = [p for p in parts if isinstance(p, LineString)]
        if polys:
            u = unary_union(polys)
            out[code] = u if isinstance(u, (Polygon, MultiPolygon)) else MultiPolygon([g for g in getattr(u, "geoms", []) if isinstance(g, Polygon)])
        elif lines:
            out[code] = MultiLineString(lines) if len(lines) > 1 else lines[0]
    return out


def fetch():
    settings = get_json(f"{WEB}/appsettings.json")
    headers = {"WebApiKey": settings["api"]["apiKey"]}
    api = WEB + settings["api"]["baseUrl"]

    try:
        geoms = _kml_geometries(settings["googleMaps"]["kmzUrl"] + "&forcekml=1")
    except Exception as e:  # noqa: BLE001 – bez geometrie se dá žít (zůstanou body Z/K)
        log.warning("KML MRS: %s", e)
        geoms = {}

    items = get_json(f"{api}/public-district", headers=headers)["items"]
    log.info("MRS: %d revírů, %d geometrií", len(items), len(geoms))

    def detail(it):
        try:
            d = get_json(f"{api}/public-district/{it['id']}", headers=headers)
        except Exception as e:  # noqa: BLE001
            log.warning("MRS revír %s: %s", it.get("code"), e)
            d = it
        code = (d.get("code") or "").replace(" ", "")
        popis = _html_to_text(d.get("note"))
        gps = [{"lat": round(l["latitude"], 5), "lon": round(l["longitude"], 5)}
               for l in d.get("locations") or [] if l.get("latitude") and l.get("longitude")]
        if not gps:
            gps = gps_z_popisu(popis or "")
        g = geoms.get(code)
        if g is None and gps:
            g = Point(gps[0]["lon"], gps[0]["lat"]) if len(gps) == 1 else LineString([(p["lon"], p["lat"]) for p in gps])
        group = d.get("belongsToGroup") or {}
        addr = group.get("officeAddress") or {}
        return {
            "id": code,
            "cislo": f"{code[:3]} {code[3:]}" if len(code) == 6 else code,
            "nazev": d.get("name", "").strip(),
            "svaz": "MRS",
            "typ": "pstruhovy" if d.get("isTroutType") else "mimopstruhovy",
            "mo": group.get("name"),
            "tok": tok_z_nazvu(d.get("name", "")),
            "rmv": bool(d.get("isLocalMrsDistrict")),
            "delka_km": d.get("length"),
            "vymera_ha": d.get("acreage"),
            "popis": popis,
            "url": f"{WEB}/reviry/{d.get('id', it['id'])}",
            "kontakty": {"mo": {k: v for k, v in {
                "nazev": group.get("name"),
                "email": group.get("email"),
                "web": group.get("webLink"),
                "adresa": ", ".join(x for x in (addr.get("street"), addr.get("number"), addr.get("city")) if x) or None,
            }.items() if v}},
            "gps": gps,
            "geom": wgs_to_desc(g) if g is not None else None,
            "muskareni": bool(d.get("flyFishing")),
        }

    with ThreadPoolExecutor(max_workers=6) as pool:
        return [r for r in pool.map(detail, items) if r["id"]]
