"""Stáhne nabídky ze všech zdrojů, sloučí duplicity, ohodnotí okolí a připraví export.

Stav (všechny kdy viděné inzeráty, historie cen) je v domy/data/stav.json – commituje se,
takže každé další spuštění pozná, co je nové a co zlevnilo.

Export pro aplikaci (sdílená databáze artefaktu) jde do domy/data/export/:
  nabidky/meta.json, nabidky/cast-N.json   – data domů (bez fotek)
  foto/<dum_id>.webp                       – malý náhled jen u domů, které ho v aplikaci ještě nemají

Spuštění:   python -m domy.run                 (vše)
            python -m domy.run --bez-stahovani (jen přepočet a export ze stavu)
            python -m domy.run --potvrd-foto nove.json  (po nahrání náhledů jako assets je zapíše
                                                         do data/foto_v_db.json = obsah DB dokumentu foto/mapa)
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import logging
import shutil
import traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path

from . import config as C
from .geo import priroda, dojezdy
from .spolecne import haversine_km, get, zkrat, duvod_vyrazeni, DETAIL_VERZE
from .zdroje import VSECHNY

DATA = Path(__file__).resolve().parent / "data"
STAV = DATA / "stav.json"
EXPORT = DATA / "export"
FOTO_HOTOVO = DATA / "foto_v_db.json"
log = logging.getLogger("domy")

POLOZEK_NA_CAST = 70
DOJEZD_VERZE = 2
DNY_NEAKTIVNI = 45          # jak dlouho po stažení inzerátu ho ještě ukazovat


def ted() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def dnes() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def nacti(p: Path, default):
    try:
        return json.loads(p.read_text("utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def zapis(p: Path, data, kompaktne=True):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":") if kompaktne else None,
                              indent=None if kompaktne else 1), "utf-8")
    tmp.replace(p)


# ---------------------------------------------------------------- filtry



# ---------------------------------------------------------------- duplicity

def _podobne(a: dict, b: dict) -> bool:
    if a["zdroj"] == b["zdroj"]:
        return False
    def blizko(x, y, tol):
        return x and y and abs(x - y) <= tol * max(x, y)
    stejna_obec = a.get("obec") and b.get("obec") and a["obec"].split(" - ")[0].lower() == b["obec"].split(" - ")[0].lower()
    vzd = haversine_km(a["lat"], a["lon"], b["lat"], b["lon"]) if a.get("lat") and b.get("lat") else 99
    if not (stejna_obec or vzd < 1.0):
        return False
    shody = sum([bool(blizko(a.get("pozemek"), b.get("pozemek"), 0.02)),
                 bool(blizko(a.get("uzitna"), b.get("uzitna"), 0.05)),
                 bool(blizko(a.get("cena"), b.get("cena"), 0.03))])
    return shody >= 2 and (vzd < 0.4 or shody == 3)


def sluc(zaznamy: dict[str, dict]) -> dict[str, list[str]]:
    """Seskupí inzeráty stejného domu z různých webů. Id domu zůstává stabilní."""
    ids = sorted(zaznamy, key=lambda i: zaznamy[i]["prvni"])
    skupiny: dict[str, list[str]] = {}
    for i in ids:
        r = zaznamy[i]
        cil = r.get("dum") if r.get("dum") in skupiny else None
        if cil is None:
            for did, cleni in skupiny.items():
                if any(_podobne(r, zaznamy[j]) for j in cleni):
                    cil = did
                    break
        if cil is None:
            cil = r.get("dum") or i
        skupiny.setdefault(cil, []).append(i)
        r["dum"] = cil
    return skupiny


# ---------------------------------------------------------------- stahování

def stahni(stav: dict) -> dict:
    zaznamy = stav["inzeraty"]
    zdroje = stav.setdefault("zdroje", {})
    for z in VSECHNY:
        log.info("Zdroj %s …", z.NAZEV)
        znam = {k: v for k, v in zaznamy.items() if v["zdroj"] == z.NAZEV}
        try:
            nove = z.stahni(znam)
            if not nove:
                raise RuntimeError("zdroj nevrátil žádné inzeráty")
        except Exception as ex:
            log.error("  %s selhal: %s", z.NAZEV, ex)
            traceback.print_exc()
            zdroje[z.NAZEV] = {**zdroje.get(z.NAZEV, {}), "ok": False, "chyba": str(ex)[:200], "cas": ted()}
            continue
        videne = set()
        for ins in nove:
            d = ins.dict()
            cerstvy = d.pop("cerstvy", False)
            videne.add(d["id"])
            prev = zaznamy.get(d["id"])
            if prev:
                if d["cena"] and prev.get("cena") and d["cena"] != prev["cena"]:
                    prev.setdefault("historie", []).append({"d": dnes(), "cena": d["cena"]})
                prev.update({k: v for k, v in d.items() if v not in (None, "", [])})
                prev["posledni"] = dnes()
                prev["aktivni"] = True
                prev["_detail"] = True
                if cerstvy:
                    prev["_dv"] = DETAIL_VERZE
                    for k in ("voda", "kanalizace", "garaz", "sklep"):
                        prev[k] = d[k]
            else:
                zaznamy[d["id"]] = {**d, "prvni": dnes(), "posledni": dnes(), "aktivni": True, "_detail": True,
                                    "_dv": DETAIL_VERZE,
                                    "historie": [{"d": dnes(), "cena": d["cena"]}] if d["cena"] else []}
        for k, v in zaznamy.items():
            if v["zdroj"] == z.NAZEV and k not in videne:
                v["aktivni"] = False
        zdroje[z.NAZEV] = {"ok": True, "pocet": len(nove), "cas": ted()}
        log.info("  %d inzerátů", len(nove))
    return stav


def obohat(stav: dict):
    """Příroda a dojezdy – počítá se jen pro nové souřadnice."""
    chybi = []
    for k, r in stav["inzeraty"].items():
        if not r.get("lat"):
            continue
        klic = f"{r['lat']:.4f},{r['lon']:.4f}"
        if r.get("_geo") != klic:
            r["priroda"] = priroda(r["lat"], r["lon"])
            r["_geo"] = klic
            r.pop("dojezd", None)
        r["vzdusne"] = {key: round(haversine_km(r["lat"], r["lon"], la, lo), 1) for key, _, la, lo in C.RODINA}
        if (r.get("dojezd") or {}).get("_v") != DOJEZD_VERZE:
            r.pop("dojezd", None)
        if not r.get("dojezd") and not duvod_vyrazeni(r) and r.get("aktivni"):
            chybi.append((k, r["lat"], r["lon"]))
    if chybi:
        log.info("Dojezdy autem pro %d domů …", len(chybi))
        for k, v in dojezdy(chybi).items():
            stav["inzeraty"][k]["dojezd"] = {**v, "_v": DOJEZD_VERZE}
    # občanská vybavenost: kde inzerát nemá vlastní (Sreality ano), vezmi nejbližší známý inzerát do 700 m
    se_poi = [r for r in stav["inzeraty"].values() if r.get("poi") and r.get("lat") and not r.get("poi_odhad")]
    for r in stav["inzeraty"].values():
        if r.get("lat") and (not r.get("poi") or r.get("poi_odhad")):
            best = min(se_poi, key=lambda x: haversine_km(r["lat"], r["lon"], x["lat"], x["lon"]), default=None)
            if best and haversine_km(r["lat"], r["lon"], best["lat"], best["lon"]) <= 0.7:
                r["poi"], r["poi_odhad"] = best["poi"], True


# ---------------------------------------------------------------- export

def _nahled(urls: list[str]) -> bytes | None:
    from PIL import Image
    for u in urls:
        if "sdn.cz" in u and "?" not in u:
            u += "?fl=res,400,300,3|shr,,20|jpg,90"
        try:
            r = get(u, pauza=0.2, pokusy=2)
            if r.status_code != 200:
                log.warning("  náhled %s: HTTP %s", u[:80], r.status_code)
                continue
            im = Image.open(io.BytesIO(r.content)).convert("RGB")
            im.thumbnail((320, 220))
            b = io.BytesIO()
            im.save(b, "WEBP", quality=55, method=6)
            return b.getvalue()
        except Exception as ex:
            log.warning("  náhled %s: %s", u, ex)
    return None


def dum_z_inzeratu(cleni: list[dict]) -> dict:
    # hlavní inzerát: nejbohatší data (Sreality > iDNES > Bezrealitky > Reas), aktivní
    poradi = {"Sreality": 0, "iDNES Reality": 1, "Bezrealitky": 2, "Reas": 3}
    cleni = sorted(cleni, key=lambda r: (not r.get("aktivni"), poradi.get(r["zdroj"], 9)))
    h = cleni[0]
    def prvni(pole):
        for r in cleni:
            if r.get(pole) not in (None, "", []):
                return r[pole]
        return None
    ceny = [r["cena"] for r in cleni if r.get("aktivni") and r.get("cena")]
    pokoje, disp = prvni("pokoje"), prvni("dispozice") or ""
    if disp and pokoje and int(disp.split("+")[0]) != pokoje:
        disp = ""   # dispozice z popisu patří k části domu (např. byt v patře)
    hist = sorted({(x["d"], x["cena"]) for r in cleni for x in r.get("historie", [])})
    return {
        "id": h["dum"],
        "nazev": h["nazev"],
        "cena": min(ceny) if ceny else h.get("cena"),
        "obec": prvni("obec") or "",
        "adresa": prvni("adresa") or "",
        "lat": prvni("lat"), "lon": prvni("lon"), "presnost": h.get("presnost") or "",
        "pokoje": pokoje, "dispozice": disp,
        "uzitna": prvni("uzitna"), "pozemek": prvni("pozemek"),
        "typ": prvni("typ") or "", "poloha": prvni("poloha") or "", "stavba": prvni("stavba") or "",
        "stav": prvni("stav") or "", "penb": next((r["penb"] for r in cleni if (r.get("penb") or "") in list("ABCDEFG")), ""),
        "vlastnosti": sorted({v for r in cleni for v in r.get("vlastnosti", [])}),
        "voda": prvni("voda") or "", "kanalizace": prvni("kanalizace") or "",
        "garaz": next((r["garaz"] for r in cleni if r.get("garaz") is not None), None),
        "sklep": next((r["sklep"] for r in cleni if r.get("sklep") is not None), None),
        "poi": prvni("poi") or {}, "poi_odhad": not any(r.get("poi") and not r.get("poi_odhad") for r in cleni),
        "popis": zkrat(h.get("popis") or prvni("popis") or "", 700),
        "priroda": prvni("priroda"), "dojezd": prvni("dojezd"), "vzdusne": prvni("vzdusne"),
        "odkazy": [{"zdroj": r["zdroj"], "url": r["url"], "rk": r.get("rk", ""), "aktivni": r.get("aktivni", False)} for r in cleni],
        "prvni": min(r["prvni"] for r in cleni),
        "aktivni": any(r.get("aktivni") for r in cleni),
        "posledni": max(r["posledni"] for r in cleni),
        "historie": [{"d": d, "cena": c} for d, c in hist][-8:],
    }


def exportuj(stav: dict, s_fotkami=True):
    zaznamy = stav["inzeraty"]
    skupiny = sluc(zaznamy)
    hranice = (datetime.now(timezone.utc).date() - timedelta(days=DNY_NEAKTIVNI)).isoformat()
    domy = []
    for did, ids in skupiny.items():
        cleni = [zaznamy[i] for i in ids]
        d = dum_z_inzeratu(cleni)
        if duvod_vyrazeni(d) or not d["lat"]:
            continue
        if not d["aktivni"] and d["posledni"] < hranice:
            continue
        domy.append((d, cleni))
    domy.sort(key=lambda x: x[0]["prvni"], reverse=True)

    shutil.rmtree(EXPORT, ignore_errors=True)
    casti = []
    for i in range(0, len(domy), POLOZEK_NA_CAST):
        cid = f"cast-{i // POLOZEK_NA_CAST}"
        zapis(EXPORT / "nabidky" / f"{cid}.json", {"polozky": [d for d, _ in domy[i:i + POLOZEK_NA_CAST]]})
        casti.append(cid)
    meta = {"aktualizovano": ted(), "prvni_beh": stav.setdefault("prvni_beh", dnes()), "pocet": len(domy), "aktivnich": sum(d["aktivni"] for d, _ in domy),
            "casti": casti, "zdroje": stav.get("zdroje", {}),
            "kriteria": {"max_cena": C.MAX_CENA, "min_pokoje": C.MIN_POKOJE, "min_pozemek": C.MIN_POZEMEK,
                         "max_km": C.MAX_VZDUSNE_KM, "bez_radovek": C.VYRADIT_RADOVE},
            "rodina": [{"klic": k, "nazev": n, "lat": la, "lon": lo} for k, n, la, lo in C.RODINA]}
    zapis(EXPORT / "nabidky" / "meta.json", meta)
    zapis(EXPORT / "nabidky" / "mapa.json", mapa_lesu())

    if s_fotkami:
        hotovo = set(nacti(FOTO_HOTOVO, {}))
        n = 0
        for d, cleni in domy:
            if d["id"] in hotovo or not d["aktivni"]:
                continue
            obr = _nahled([u for r in cleni for u in r.get("fotky", [])[:2]])
            if obr:
                (EXPORT / "foto").mkdir(parents=True, exist_ok=True)
                (EXPORT / "foto" / f"{d['id']}.webp").write_bytes(obr)
                n += 1
        log.info("Nových náhledů: %d", n)
    log.info("Export: %d domů (%d aktivních) v %d částech", meta["pocet"], meta["aktivnich"], len(casti))
    return domy


def mapa_lesu() -> dict:
    """Podkladová mapka lesů pro aplikaci (PNG s průhledností, ~100 kB)."""
    import numpy as np
    from PIL import Image
    from .geo import _m
    les, _, bbox, _ = _m()
    a = les[: les.shape[0] // 3 * 3, : les.shape[1] // 3 * 3].astype(np.float32)
    a = a.reshape(a.shape[0] // 3, 3, a.shape[1] // 3, 3).mean(axis=(1, 3))
    rgba = np.zeros(a.shape + (4,), dtype=np.uint8)
    rgba[..., 0], rgba[..., 1], rgba[..., 2] = 52, 125, 82
    rgba[..., 3] = np.clip((a - 25) * 2.6, 0, 200).astype(np.uint8)
    b = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(b, "PNG", optimize=True)
    return {"png": "data:image/png;base64," + base64.b64encode(b.getvalue()).decode(), "bbox": [float(x) for x in bbox]}


def potvrd_foto(soubor: str):
    """Přidá nahrané náhledy ({id_domu: "/_blob/…"}) do domy/data/foto_v_db.json."""
    hotovo = nacti(FOTO_HOTOVO, {})
    nove = json.loads(Path(soubor).read_text("utf-8"))
    hotovo.update(nove)
    zapis(FOTO_HOTOVO, dict(sorted(hotovo.items())), kompaktne=False)
    log.info("Fotky v aplikaci: %d (+%d)", len(hotovo), len(nove))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bez-stahovani", action="store_true")
    ap.add_argument("--bez-fotek", action="store_true")
    ap.add_argument("--potvrd-foto", metavar="JSON", help="soubor {id_domu: url} s nově nahranými náhledy")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if a.potvrd_foto:
        potvrd_foto(a.potvrd_foto)
        return 0
    stav = nacti(STAV, {"inzeraty": {}, "zdroje": {}})
    if not a.bez_stahovani:
        stahni(stav)
        stav["aktualizovano"] = ted()
    obohat(stav)
    sluc(stav["inzeraty"])
    for r in stav["inzeraty"].values():   # vyřazené inzeráty: stačí vědět, že je známe
        if duvod_vyrazeni(r) and len(r.get("popis") or "") > 300:
            r["popis"] = zkrat(r["popis"], 300)
    zapis(STAV, stav, kompaktne=False)
    exportuj(stav, s_fotkami=not a.bez_fotek)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
