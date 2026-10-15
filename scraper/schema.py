"""Datový formát, který čte mobilní aplikace (web/js/data.js).

reviry.json   {"reviry": [Revir, ...]}
vysazeni.json {"vysazeni": {revir_id: [Vysazeni, ...]}}
ulovky.json   {"ulovky": {revir_id: [Ulovek, ...]}}
voda.json     {"stanice": [Stanice, ...]}
meta.json     {"generated": iso, "zdroje": {nazev: {"ok": bool, "pocet": int, "chyba": str|None, "cas": iso}}}
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal, Optional


@dataclass
class Bod:
    lat: float
    lon: float


@dataclass
class Revir:
    id: str                      # evidenční číslo bez mezer, např. "421056"
    nazev: str                   # "Otava 4"
    svaz: str                    # "ČRS – Jihočeský ÚS", "MRS", ...
    typ: Literal["pstruhovy", "mimopstruhovy", "neuveden"]
    cislo: Optional[str] = None  # zobrazované číslo, např. "421 056"
    uzivatel: Optional[str] = None
    mo: Optional[str] = None     # hospodařící místní organizace
    tok: Optional[str] = None    # název toku/nádrže pro párování se stanicí ČHMÚ
    popis: Optional[str] = None
    omezeni: Optional[str] = None
    delka_km: Optional[float] = None
    vymera_ha: Optional[float] = None
    rmv: bool = False            # revír místního významu
    gps: list[Bod] = field(default_factory=list)
    url: Optional[str] = None


@dataclass
class Vysazeni:
    druh: str
    datum: Optional[str] = None       # ISO datum, je-li známé
    datum_text: Optional[str] = None  # např. "jaro 2026", když přesné datum chybí
    mnozstvi: Optional[float] = None
    jednotka: Optional[str] = None    # "ks", "kg"
    vek: Optional[str] = None         # "K2", "Pd1" ...
    zdroj: Optional[str] = None


@dataclass
class Ulovek:
    datum: str                        # ISO datum
    druh: str
    delka_cm: Optional[float] = None
    hmotnost_kg: Optional[float] = None
    nastraha: Optional[str] = None
    metoda: Optional[str] = None
    zdroj: Optional[str] = None       # název fóra
    url: Optional[str] = None


@dataclass
class Stanice:
    id: str
    nazev: str
    lat: float
    lon: float
    tok: Optional[str] = None
    cas: Optional[str] = None
    stav_cm: Optional[float] = None
    prutok_m3s: Optional[float] = None
    teplota_vody: Optional[float] = None
    trend: Optional[Literal["roste", "klesá", "stálý"]] = None
    spa: int = 0


def to_json(obj):
    if isinstance(obj, list):
        return [to_json(o) for o in obj]
    if isinstance(obj, dict):
        return {k: to_json(v) for k, v in obj.items()}
    if hasattr(obj, "__dataclass_fields__"):
        return {k: v for k, v in asdict(obj).items() if v not in (None, [], "")}
    return obj
