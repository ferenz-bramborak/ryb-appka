"""Spojí stažená data (data-cache/*.json) do souborů, které čte aplikace:

  web/data/reviry.json   lehký index všech revírů (mapa, hledání, „kde jsem“)
  web/data/r/<id>.json   detail revíru: popis, pravidla, tvar, statistika,
                         vysazení a úlovky
  web/data/voda.json     stanice ČHMÚ
  web/data/meta.json     čas a stav zdrojů
"""
from __future__ import annotations

import json
import logging
import re
import shutil
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from .geo import norm

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data-cache"
OUT = ROOT / "web" / "data"
log = logging.getLogger("build")

ULOVKY_DNU = 92
# Obecná slova, která rybáři píšou místo názvu revíru – nesmí se spárovat s revírem stejného jména.
OBECNE = {"rybnicek", "rybnik", "piskovna", "sterkovna", "potok", "reka", "revir", "nadrz", "tune", "slepe rameno"}


def _load(name: str, default):
    p = CACHE / name
    return json.loads(p.read_text("utf-8")) if p.exists() else default


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), "utf-8")


# ---------- párování textu na revír ----------

def _aliasy(r: dict) -> set[str]:
    n = norm(r["nazev"])
    out = {n, re.sub(r" (p|mp)$", "", n)}
    for m in re.finditer(r"(?:udolni nadrz|un|vn|nadrz|rybnik|piskovna|sterkovna) ([a-z]+(?: [a-z]+)?)", n):
        out.add(m.group(1))
        out.add("un " + m.group(1))
    for part in re.split(r" - ", r["nazev"]):
        out.add(norm(part))
    return {a for a in out if len(a) >= 4}


class Parovac:
    def __init__(self, reviry: list[dict]):
        self.by_id = {r["id"]: r for r in reviry}
        self.alias: dict[str, list[str]] = defaultdict(list)
        for r in reviry:
            for a in _aliasy(r):
                self.alias[a].append(r["id"])
        self.mo: dict[tuple[str, str], list[str]] = defaultdict(list)
        for r in reviry:
            if r.get("mo"):
                self.mo[(r["svaz"], norm(r["mo"]))].append(r["id"])

    def podle_textu(self, text: str, svaz: str | None = None, cely_text: bool = False) -> list[str]:
        """Přesná shoda názvu (u úlovků), nebo hledání názvů revírů v delším textu (u zpráv)."""
        t = norm(text)
        if not t:
            return []
        if not cely_text:
            if t in OBECNE:
                return []
            ids = self.alias.get(t) or self.alias.get(re.sub(r" (p|mp)$", "", t)) or []
            return ids if len(ids) == 1 else []
        found = set()
        for a, ids in self.alias.items():
            if " " not in a and len(a) < 6:
                continue
            if re.search(rf"\b{re.escape(a)}\b", t):
                kand = [i for i in ids if not svaz or self.by_id[i]["svaz"] == svaz] or ids
                if len(kand) == 1:
                    found.add(kand[0])
        # delší název vyhrává nad kratším (Trnávka 1 vs. Trnávka)
        return sorted(found)

    def podle_mo(self, svaz: str, mo: str) -> list[str]:
        return self.mo.get((svaz, norm(mo)), [])


# ---------- build ----------

def build(meta: dict) -> dict:
    crs = _load("crs.json", [])
    mrs = _load("mrs.json", [])
    stat = _load("statistika.json", {})
    vys_raw = _load("vysazeni.json", [])
    ul_raw = _load("ulovky.json", [])
    voda = _load("voda.json", [])

    reviry = {}
    for r in crs + mrs:
        if r.get("id") and r["id"] not in reviry:
            reviry[r["id"]] = r
    par = Parovac(list(reviry.values()))

    vysazeni = defaultdict(list)
    for v in vys_raw:
        if v.get("mo") and v.get("svaz"):
            ids = par.podle_mo(v["svaz"], v["mo"])
            pres_mo = True
        else:
            ids = par.podle_textu(v.get("revir_text", ""), v.get("svaz") or "ČRS – Republiková rada", cely_text=True)
            # Článek bez rozpisu: druhy nejde rozdělit mezi víc revírů – přiřadit jen jednoznačný.
            ids = ids if len(ids) == 1 else []
            pres_mo = False
        for i in ids[:40]:
            vysazeni[i].append({k: val for k, val in {
                "datum": v["datum"], "druh": v["druh"], "kategorie": v.get("kategorie"),
                "mnozstvi": v.get("mnozstvi"), "jednotka": v.get("jednotka"),
                "mo": v.get("mo") if pres_mo else None, "popis": v.get("popis"),
                "url": v.get("url"), "clanek": v.get("clanek"),
            }.items() if val not in (None, "")})

    od = (date.today() - timedelta(days=ULOVKY_DNU)).isoformat()
    ulovky = defaultdict(list)
    ulovky_tok = defaultdict(list)  # úlovky, u kterých rybář uvedl jen řeku (bez čísla revíru)
    toky = {norm(r.get("tok")) for r in reviry.values() if r.get("tok")}
    neprirazene = 0
    for u in ul_raw:
        if u["datum"] < od:
            continue
        rid = u.get("revir_id") if u.get("revir_id") in reviry else None
        if not rid:
            ids = par.podle_textu(u.get("revir_text", ""))
            rid = ids[0] if ids else None
        if not rid:
            t = norm(u.get("revir_text"))
            if t in toky and t not in OBECNE:
                ulovky_tok[t].append(u)
            else:
                neprirazene += 1
            continue
        ulovky[rid].append({k: v for k, v in u.items() if k not in ("revir_id",)})
    log.info("Úlovky: %d přiřazeno, %d bez rozpoznaného revíru", sum(map(len, ulovky.values())), neprirazene)

    if (OUT / "r").exists():
        shutil.rmtree(OUT / "r")
    index = []
    for rid, r in sorted(reviry.items(), key=lambda kv: (kv[1]["nazev"], kv[0])):
        geom = r.get("geom")
        gps = r.get("gps") or ([geom["stred"]] if geom else [])
        idx = {k: v for k, v in {
            "id": rid, "cislo": r.get("cislo"), "nazev": r["nazev"], "svaz": r["svaz"], "typ": r["typ"],
            "mo": r.get("mo"), "tok": r.get("tok"), "rmv": r.get("rmv") or None,
            "gps": gps[:4], "stred": (geom or {}).get("stred") or (gps[0] if gps else None),
            "bbox": (geom or {}).get("bbox"), "geom": (geom or {}).get("typ"),
            "delka_km": r.get("delka_km"), "vymera_ha": r.get("vymera_ha"),
            "lodi": r.get("lov_z_lodi") or None, "nonstop": r.get("lov_nonstop") or None,
            "handicap": r.get("handicap") or None,
            "u": len(ulovky.get(rid, [])) or None,
        }.items() if v not in (None, "", [])}
        index.append(idx)
        detail = {k: v for k, v in {
            "id": rid, "popis": r.get("popis"), "url": r.get("url"), "kontakty": r.get("kontakty"),
            "pravidla": r.get("pravidla"), "casti": (geom or {}).get("casti"),
            "statistika": stat.get(rid),
            "vysazeni": sorted(vysazeni.get(rid, []), key=lambda x: x["datum"], reverse=True)[:60],
            "ulovky": sorted(ulovky.get(rid, []), key=lambda x: x["datum"], reverse=True),
            "ulovky_tok": sorted(ulovky_tok.get(norm(r.get("tok")), []), key=lambda x: x["datum"], reverse=True)[:30],
        }.items() if v not in (None, "", [])}
        _write(OUT / "r" / f"{rid}.json", detail)

    _write(OUT / "reviry.json", {"reviry": index})
    _write(OUT / "voda.json", {"stanice": voda})
    meta["pocty"] = {
        "reviry": len(index),
        "s_tvarem": sum(1 for i in index if i.get("geom")),
        "s_vysazenim": len(vysazeni),
        "ulovky_prirazene": sum(map(len, ulovky.values())),
        "ulovky_jen_tok": sum(map(len, ulovky_tok.values())),
        "ulovky_neprirazene": neprirazene,
        "stanice": len(voda),
        "statistika": len(stat),
    }
    _write(OUT / "meta.json", meta)
    log.info("Build: %s", meta["pocty"])
    return meta
