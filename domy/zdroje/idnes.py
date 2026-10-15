"""iDNES Reality – HTML výpis + detail (souřadnice z mapy na detailu)."""
from __future__ import annotations

import json
import logging
import re

from bs4 import BeautifulSoup

from ..config import MAX_CENA
from ..spolecne import (z_predchoziho, voda_z_textu, kanalizace_z_textu, Inzerat, get, cislo, dispozice_z_textu, typ_z_textu, poloha_z_textu,
                        stavba_z_textu, vlastnosti_z_textu)

NAZEV = "iDNES Reality"
log = logging.getLogger("domy")

OKRESY = ["brno-venkov", "brno-mesto"]
MAX_STRAN = 30

STAV = {"novostavba": "novostavba", "po rekonstrukci": "po rekonstrukci", "velmi dobrý": "velmi dobrý",
        "dobrý": "dobrý", "před rekonstrukcí": "před rekonstrukcí", "špatný": "špatný",
        "ve výstavbě": "ve výstavbě", "projekt": "projekt", "k demolici": "špatný", "v rekonstrukci": "v rekonstrukci"}


def _seznam():
    for okres in OKRESY:
        for strana in range(1, MAX_STRAN + 1):
            url = f"https://reality.idnes.cz/s/prodej/domy/cena-do-{MAX_CENA}/{okres}/"
            if strana > 1:
                url += f"?page={strana}"
            s = BeautifulSoup(get(url).text, "lxml")
            items = s.select(".c-products__item")
            nove = 0
            for it in items:
                a = it.select_one("a.c-products__link")
                if not a or "/detail/" not in (a.get("href") or ""):
                    continue
                nove += 1
                yield it, a
            nxt = s.select_one(".paginator a.next, .paging__item--next, a[rel=next]")
            if not nove or (not nxt and "Další" not in (s.select_one(".paginator") or s).get_text()):
                break


def _detail(url: str) -> dict:
    s = BeautifulSoup(get(url).text, "lxml")
    par = {}
    for dl in s.select("dl"):
        for dt, dd in zip(dl.select("dt"), dl.select("dd")):
            par[dt.get_text(" ", strip=True)] = dd.get_text(" ", strip=True).replace("‍", "")
    lat = lon = None
    js = s.select_one("script[data-maptiler-json]")
    if js and js.string:
        try:
            c = json.loads(js.string)["mtMapOptions"]["center"]
            lon, lat = float(c[0]), float(c[1])
        except Exception:
            pass
    desc = s.select_one(".b-desc")
    fot = [im.get("data-lazy") or im.get("src") for im in s.select(".b-gallery img")][:3]
    return {"par": par, "lat": lat, "lon": lon, "popis": desc.get_text("\n", strip=True) if desc else "",
            "fotky": [f for f in fot if f and f.startswith("http") and "/ui/image/" not in f],
            "rk": (s.select_one(".b-author__title, .b-broker__name") or s.new_tag("x")).get_text(" ", strip=True)}


def stahni(znam: dict) -> list[Inzerat]:
    out = []
    for it, a in _seznam():
        href = a["href"].split("?")[0]
        m = re.search(r"/([0-9a-f]{20,})/?$", href)
        if not m:
            continue
        iid = f"id-{m.group(1)}"
        nazev = " ".join((it.select_one(".c-products__title") or a).get_text(" ", strip=True).split())
        nazev = nazev[:1].upper() + nazev[1:]
        info = (it.select_one(".c-products__info") or a).get_text(" ", strip=True)
        cena = cislo((it.select_one(".c-products__price") or a).get_text(" ", strip=True))
        if cena is not None and cena < 100_000:
            cena = None
        ins = z_predchoziho(znam.get(iid))
        if ins:
            ins.cena = cena
            out.append(ins)
            continue
        try:
            d = _detail(href)
        except Exception as ex:
            log.warning("  idnes detail %s: %s", href, ex)
            continue
        p = d["par"]
        text = f"{nazev} {d['popis']}"
        disp, n = dispozice_z_textu(text)
        mistnosti = cislo(p.get("Počet místností"))
        pokoje = n or mistnosti
        typ = typ_z_textu(text)
        if not typ and (cislo(p.get("Počet podlaží")) == 1):
            typ = "bungalov"
        poloha_raw = (p.get("Poloha domu") or "").lower()
        poloha = "řadový" if "řadov" in poloha_raw else ("samostatný" if "samostat" in poloha_raw else poloha_z_textu(nazev))
        kon = (p.get("Konstrukce budovy") or "").lower()
        stavba = ("cihla" if "cihl" in kon else "dřevostavba" if "dřev" in kon else "smíšená" if "smíš" in kon
                  else "kámen" if "kamen" in kon else "panel" if "panel" in kon else "montovaná" if "mont" in kon else "") or stavba_z_textu(text)
        img = it.select_one("img")
        thumb = img.get("data-src") if img else None
        title_m = re.search(r"(\d[\d\s]*)\s*m²(?:.*?pozemkem\s*(\d[\d\s]*)\s*m²)?", nazev)
        ins = Inzerat(
            id=iid, zdroj=NAZEV, url=href, nazev=nazev, cena=cena,
            obec=re.sub(r",?\s*okres.*$", "", info).split(",")[-1].strip() or info,
            adresa=re.sub(r",?\s*okres.*$", "", info),
            lat=d["lat"], lon=d["lon"], presnost="adresa" if d["lat"] else "",
            pokoje=pokoje, dispozice=disp,
            uzitna=cislo(p.get("Užitná plocha", "").replace("m 2", "")) or (cislo(title_m.group(1)) if title_m else None),
            pozemek=cislo(p.get("Plocha pozemku", "").replace("m 2", "")) or (cislo(title_m.group(2)) if title_m and title_m.group(2) else None),
            typ=typ, poloha=poloha, stavba=stavba,
            stav=STAV.get((p.get("Stav budovy") or "").lower(), ""),
            penb=(p.get("PENB") or "")[:1],
            rk=a.get("data-brand") or d["rk"],
            popis=d["popis"], fotky=([thumb] if thumb else []) + d["fotky"][:2],
            vlastnosti=vlastnosti_z_textu(text),
        )
        voda = (p.get("Voda") or "").lower()
        ins.voda = ("vodovod + studna" if "veřejn" in voda and "studn" in voda else "vodovod" if "veřejn" in voda or "vodovod" in voda
                    else "studna" if "studn" in voda or "vlastní" in voda else "") or voda_z_textu(text)
        odp = (p.get("Odpad") or "").lower()
        ins.kanalizace = ("veřejná kanalizace" if "kanaliz" in odp else "domácí ČOV" if "čov" in odp or "čistír" in odp
                          else "septik/jímka" if "septik" in odp or "jímk" in odp else "") or kanalizace_z_textu(text)
        ins.sklep = True if "Sklep" in p or "sklep" in ins.vlastnosti else None
        ins.garaz = True if ("Garáž" in p or "garáž" in ins.vlastnosti or "garáž" in (p.get("Parkování") or "").lower()) else None
        ins.cerstvy = True
        out.append(ins)
    return out
