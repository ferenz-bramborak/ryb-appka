"""Vysazování ryb z aktualit ČRS (CMS API webu rybsvaz.cz).

- Východočeský ÚS vydává týdenní hlášení „Vysazování ryb NN. týden“ ve tvaru
  „<b>Kapr tržní 7800 kg …</b> - MO Přelouč <b>3600 kg</b>, MO Smiřice …“.
  Vysazení se rozpadne na jednotlivé MO (a pojmenované nádrže, např. „ÚN Rozkoš“).
- Celosvazový web ČRS publikuje zprávy typu „Na Trnávku vysazeni pstruzi duhoví“;
  z nich se vezme datum, druhy a jména revírů zmíněná v textu.

Přiřazení k revírům dělá build: podle MO (všechny revíry dané MO v daném ÚS)
nebo podle jména revíru v textu.
"""
from __future__ import annotations

import html
import logging
import re
from datetime import date, timedelta

from ..http import get_json
from .ulovky_fora import druhy_v_textu

NAZEV = "Vysazování"
DRUH = "vysazeni"

CMS = "https://www.rybsvaz.cz/proxy/cms"
WEBY = {
    70597: ("ČRS – Východočeský ÚS", "https://vcus.rybsvaz.cz/"),
    20119: (None, "https://www.rybsvaz.cz/"),
}
DNU = 365
log = logging.getLogger(__name__)

_MNOZSTVI = re.compile(r"(\d[\d\s.]*(?:,\d+)?)\s*(kg|ks)\b", re.I)


def _num(s: str) -> float:
    return float(s.replace(" ", "").replace(".", "").replace(",", "."))


def _text(h: str) -> str:
    t = html.unescape(re.sub(r"<[^>]+>", " ", h)).replace("\xa0", " ")
    return re.sub(r"\s+", " ", t).strip()


def _rozpis(paragraph_html: str) -> list[dict]:
    """Jeden odstavec týdenního hlášení → záznamy po MO/nádržích."""
    t = _text(paragraph_html)
    if " - " not in t and " – " not in t:
        return []
    hlava, zbytek = re.split(r"\s[-–]\s", t, maxsplit=1)
    druhy = druhy_v_textu(hlava)
    if not druhy:
        return []
    m_hlava = _MNOZSTVI.search(hlava)
    kategorie = None
    km = re.search(r"\b(tržní|násada|násady|plůdek|roček|ročka|dvouroček|K\d|Pd\d|generační)\b", hlava, re.I)
    if km:
        kategorie = km.group(1).lower()
    out = []
    casti = [c.strip() for c in re.split(r",\s*(?=(?:MO|ÚN|VN|ÚS)\s)", zbytek) if c.strip()]
    for c in casti:
        m = re.match(r"(MO|ÚN|VN)\s+(.+?)(?:\s+(\d[\d\s.]*(?:,\d+)?)\s*(kg|ks))?\s*[,.]?\s*$", c)
        if not m:
            continue
        kdo_typ, kdo, mn, jed = m.groups()
        kdo = re.sub(r"\s+(chovný rybník|chovné potoky?)$", "", kdo.strip(), flags=re.I)
        rec = {"druh": druhy[0], "kategorie": kategorie, "popis": hlava}
        if mn:
            rec["mnozstvi"], rec["jednotka"] = _num(mn), jed.lower()
        elif len(casti) == 1 and m_hlava:
            rec["mnozstvi"], rec["jednotka"] = _num(m_hlava.group(1)), m_hlava.group(2).lower()
        if kdo_typ == "MO":
            rec["mo"] = kdo
        else:
            rec["revir_text"] = kdo
        out.append(rec)
    return out


def fetch() -> list[dict]:
    od = (date.today() - timedelta(days=DNU)).isoformat()
    out = []
    for web_id, (svaz, base) in WEBY.items():
        start, items = 0, []
        while True:
            page = get_json(f"{CMS}/contents?webId={web_id}&from={start}&size=200")["items"]
            items += page
            if len(page) < 200:
                break
            start += 200
        clanky = [i for i in items if re.search(r"vysaz|zarybn", i["name"], re.I)
                  and (i.get("displayAt") or "") >= od and (i.get("structure") or {}).get("key") == "AKTUALITA_DETAIL"]
        for c in clanky:
            try:
                d = get_json(f"{CMS}/contents/by-id/{c['id']}?webId={web_id}")
            except Exception as e:  # noqa: BLE001
                log.warning("článek %s: %s", c["id"], e)
                continue
            datum = c["displayAt"][:10]
            url = base + (c.get("friendlyURLs") or {}).get("cs_cz", "")
            data = d.get("data") or {}
            sekce = data.get("sekcePopis") or []
            obsah = " ".join(s.get("sekcePopisObsah") or "" for s in sekce)
            zaznamy = []
            for p in re.findall(r"<p>(.*?)</p>", obsah, re.S):
                zaznamy += _rozpis(p)
            if zaznamy:
                for z in zaznamy:
                    out.append({**z, "datum": datum, "svaz": svaz, "url": url, "clanek": c["name"]})
            else:
                # Zpráva bez rozpisu – revír se pozná podle jména v titulku/perexu.
                text = f"{c['name']}. {_text(data.get('perex') or '')} {_text(obsah)}"
                for druh in druhy_v_textu(text) or ["ryby"]:
                    out.append({"druh": druh, "datum": datum, "svaz": svaz, "url": url, "clanek": c["name"],
                                "revir_text": text[:400], "popis": _text(data.get("perex") or "")[:200]})
    log.info("Vysazování: %d záznamů", len(out))
    if not out:
        raise RuntimeError("nenalezeno žádné vysazení")
    return out
