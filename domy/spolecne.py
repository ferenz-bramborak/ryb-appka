"""Sdílené pomůcky: HTTP, převody dispozic, rozpoznání typu domu z textu."""
from __future__ import annotations

import logging
import math
import re
import time
from dataclasses import dataclass, field, asdict

import requests

from .config import USER_AGENT

log = logging.getLogger("domy")

_session = None


def http() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "cs,en;q=0.8"})
    return _session


def get(url: str, *, pauza: float = 0.6, pokusy: int = 3, **kw) -> requests.Response:
    """GET se slušnou pauzou a pár pokusy při výpadku."""
    for i in range(pokusy):
        try:
            r = http().get(url, timeout=30, **kw)
            if r.status_code in (429, 502, 503, 504):
                raise requests.HTTPError(f"{r.status_code}")
            time.sleep(pauza)
            return r
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as e:
            if i == pokusy - 1:
                raise
            log.warning("  %s – zkouším znovu (%s)", url, e)
            time.sleep(3 * (i + 1))
    raise AssertionError


@dataclass
class Inzerat:
    """Jeden inzerát z jednoho zdroje, převedený na společný tvar."""
    id: str                      # "sr-123", "id-abc", "br-123", "re-abc"
    zdroj: str                   # Sreality, iDNES Reality, Bezrealitky, Reas
    url: str
    nazev: str
    cena: int | None
    obec: str
    adresa: str
    lat: float | None = None
    lon: float | None = None
    presnost: str = ""           # "adresa", "ulice", "obec" …
    pokoje: int | None = None
    dispozice: str = ""
    uzitna: int | None = None    # m²
    pozemek: int | None = None   # m²
    typ: str = ""                # "bungalov", "patrový", ""
    poloha: str = ""             # "samostatný", "řadový", "dvojdům", ""
    stavba: str = ""             # "cihla", "dřevostavba", "smíšená", "kámen", "panel", "montovaná", ""
    stav: str = ""               # "novostavba", "po rekonstrukci", "velmi dobrý", "dobrý", "před rekonstrukcí", "špatný", "ve výstavbě", "projekt", ""
    penb: str = ""
    rk: str = ""                 # realitka / makléř
    popis: str = ""
    fotky: list[str] = field(default_factory=list)
    vlastnosti: list[str] = field(default_factory=list)
    voda: str = ""               # "vodovod", "studna", "vodovod + studna", ""
    kanalizace: str = ""         # "veřejná kanalizace", "septik/jímka", "domácí ČOV", ""
    garaz: bool | None = None
    sklep: bool | None = None
    poi: dict = field(default_factory=dict)   # m: skolka, skola, obchod, lekar, bus, vlak
    cerstvy: bool = False        # detail stažen v tomto běhu (interní)

    def dict(self) -> dict:
        return asdict(self)


def cislo(text) -> int | None:
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return int(text) if text > 0 else None
    m = re.search(r"\d[\d\s\u00a0\u200d]*(?:[.,]\d+)?", str(text))
    if not m:
        return None
    v = float(re.sub(r"[\s\u00a0\u200d]", "", m.group(0)).replace(",", "."))
    return int(round(v)) if v > 0 else None


_DISP = re.compile(r"\b([1-9])\s*\+\s*(kk|1|\d)\b", re.I)


def dispozice_z_textu(text: str) -> tuple[str, int | None]:
    """Najde nejvyšší dispozici typu 4+kk / 5+1 v textu."""
    best = None
    for m in _DISP.finditer(text or ""):
        n = int(m.group(1))
        if best is None or n > best[1]:
            best = (f"{n}+{m.group(2).lower()}", n)
    return best if best else ("", None)


def pokoje_z_textu(text: str) -> int | None:
    m = re.search(r"\b(\d{1,2})\s*(?:obytn[ýéých]+\s+)?(?:pokoj|ložnic)", text or "", re.I)
    return int(m.group(1)) if m and 1 <= int(m.group(1)) <= 12 else None


def typ_z_textu(text: str) -> str:
    t = (text or "").lower()
    if re.search(r"bungalov|přízemní (rodinný )?d[ůo]m|jednopodlažní|nepodsklepený přízemní", t):
        return "bungalov"
    return ""


def poloha_z_textu(text: str) -> str:
    t = (text or "").lower()
    if re.search(r"polořadov|dvojd[ůo]m|dvojdom", t):
        return "dvojdům"
    if re.search(r"řadov|řadovk", t):
        return "řadový"
    if False:
        return "dvojdům"
    return ""


def stavba_z_textu(text: str) -> str:
    t = (text or "").lower()
    if re.search(r"dřevostavb|srubov|roubenk|dřevěn[ýé] d[ůo]m", t):
        return "dřevostavba"
    if re.search(r"cihl|zděn|porotherm|heluz|ytong|keramick[ýé]ch? tvár", t):
        return "cihla"
    return ""


VLASTNOSTI = [
    ("garáž", r"garáž"),
    ("sklep", r"sklep|podsklep"),
    ("studna", r"studn"),
    ("bazén", r"bazén"),
    ("tepelné čerpadlo", r"tepeln\w+ čerpadl"),
    ("fotovoltaika", r"fotovolt|FVE"),
    ("krb", r"\bkrb"),
    ("u lesa", r"u lesa|okraj\w* lesa|blízkost\w* lesa|les(?:em)? za (?:domem|zahradou)|kousek od lesa|přímo u lesa|lesy v okolí|obklopen\w* les"),
    ("klidná lokalita", r"klidn\w+ (?:část|lokalit|ulic)|slepé ulic|konec ulice"),
    ("výhled", r"výhled"),
    ("k rekonstrukci", r"k (?:celkové |částečné )?rekonstrukci|před rekonstrukcí"),
]


def vlastnosti_z_textu(text: str) -> list[str]:
    t = text or ""
    return [n for n, rx in VLASTNOSTI if re.search(rx, t, re.I)]


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def zkrat(text: str, n: int) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text if len(text) <= n else text[: n - 1].rsplit(" ", 1)[0] + "…"


DETAIL_VERZE = 2   # zvýšit, když se z detailu začne číst něco nového → stáhne se znovu


def voda_z_textu(text: str) -> str:
    t = (text or "").lower()
    v = re.search(r"vodovod|vodovodní řad|obecní vod|veřejn\w+ vod", t)
    s = re.search(r"studn|vrt\b|vrtan", t)
    return "vodovod + studna" if v and s else "vodovod" if v else "studna" if s else ""


def kanalizace_z_textu(text: str) -> str:
    t = (text or "").lower()
    if re.search(r"čov\b|čistírn|domovní čistír", t):
        return "domácí ČOV"
    if re.search(r"septik|jímk|žump", t):
        return "septik/jímka"
    if re.search(r"(?<!bez )(veřejn\w+ |obecní |splaškov\w+ )?kanalizac", t) and not re.search(r"bez kanalizac|kanalizace není|není kanalizac", t):
        return "veřejná kanalizace"
    return ""


def z_predchoziho(prev: dict | None):
    """Znovu použije známý inzerát bez stahování detailu, pokud je aktuální nebo vyřazený."""
    if not prev or not prev.get("_detail"):
        return None
    if prev.get("_dv") != DETAIL_VERZE and not duvod_vyrazeni(prev):
        return None
    return Inzerat(**{k: v for k, v in prev.items() if not k.startswith("_") and k in Inzerat.__dataclass_fields__ and k != "cerstvy"})


def duvod_vyrazeni(r: dict) -> str | None:
    from . import config as C
    if r.get("cena") and r["cena"] > C.MAX_CENA:
        return "cena"
    if r.get("pokoje") is not None and r["pokoje"] < C.MIN_POKOJE:
        return "pokoje"
    if r.get("pozemek") and r["pozemek"] < C.MIN_POZEMEK:
        return "pozemek"
    if C.VYRADIT_RADOVE and r.get("poloha") == "řadový":
        return "řadový"
    if r.get("lat"):
        tlat = sum(x[2] for x in C.RODINA) / len(C.RODINA)
        tlon = sum(x[3] for x in C.RODINA) / len(C.RODINA)
        if haversine_km(r["lat"], r["lon"], tlat, tlon) > C.MAX_VZDUSNE_KM:
            return "daleko"
    if r.get("uzitna") and r["uzitna"] < 70:
        return "malý"
    return None
