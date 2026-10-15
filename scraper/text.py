"""Zpracování volného textu zpráv: čištění HTML, data, typ zprávy a vysazení."""
from __future__ import annotations

import html
import re
from datetime import date, datetime
from email.utils import parsedate_to_datetime

from .sources.ulovky_fora import druhy_v_textu


def html_text(h: str) -> str:
    h = re.sub(r"<(script|style|noscript)\b.*?</\1>", " ", h or "", flags=re.S | re.I)
    h = re.sub(r"<br\s*/?>|</p>|</li>|</h\d>|</div>", "\n", h, flags=re.I)
    t = html.unescape(re.sub(r"<[^>]+>", " ", h)).replace("\xa0", " ")
    t = re.sub(r"[ \t]+", " ", t)
    return re.sub(r"\n\s*\n+", "\n", t).strip()


_MESICE = {"ledna": 1, "února": 2, "března": 3, "dubna": 4, "května": 5, "června": 6, "července": 7,
           "srpna": 8, "září": 9, "října": 10, "listopadu": 11, "prosince": 12}


def parse_date(s: str | None, today: date | None = None) -> date | None:
    """Rozpozná 15.9.2026, 15. 9. 2026, 2026-09-15, 15. září 2026 i RFC 822 z RSS."""
    if not s:
        return None
    today = today or date.today()
    s = s.strip()
    try:
        return parsedate_to_datetime(s).date()
    except (TypeError, ValueError, IndexError):
        pass
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return _safe(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.search(r"\b(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})\b", s)
    if m:
        return _safe(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    m = re.search(r"\b(\d{1,2})\.\s*(" + "|".join(_MESICE) + r")\s+(\d{4})", s, re.I)
    if m:
        return _safe(int(m.group(3)), _MESICE[m.group(2).lower()], int(m.group(1)))
    return None


def _safe(y, m, d):
    try:
        return date(y, m, d)
    except ValueError:
        return None


def dates_in_text(text: str) -> list[date]:
    out = []
    for m in re.finditer(r"\b\d{1,2}\.\s*\d{1,2}\.\s*\d{4}\b|\b\d{4}-\d{2}-\d{2}\b", text or ""):
        d = parse_date(m.group(0))
        if d and d.year >= 2000:
            out.append(d)
    return out


TYPY = [
    ("vysazeni", r"vysaz|vysadil|zarybn|násad|nasazen[ao] .*(kapr|štik|pstruh|amur|candát)|vypuštěn[oiy] .*(ryb|plůd|jeseter)"),
    ("zakaz", r"zákaz (lovu|rybolovu)|uzavřen[íý]? revír|lov (je )?zakázán|výlov|vypouštění nádrže"),
    ("uhyn", r"úhyn|otrav|mrtvé ryby|hynou"),
    ("zavody", r"závod[yůu]? |rybářské závody|dětské rybářské"),
]


def typ_zpravy(text: str) -> str:
    t = (text or "").lower()
    for typ, rx in TYPY:
        if re.search(rx, t):
            return typ
    return "info"


_MN = r"(\d{1,3}(?:[ .]\d{3})*(?:,\d+)?|\d+(?:,\d+)?)\s*(kg|ks|kusů|kilogramů)"


def vysazeni_z_textu(text: str) -> list[dict]:
    """Volný text → [{druh, mnozstvi, jednotka}] pro dvojice „druh … množství“ ve stejné větě."""
    out = []
    for veta in re.split(r"(?<=[.;!?\n])\s+|,\s+(?=\D)", text or ""):
        druhy = druhy_v_textu(veta)
        if not druhy:
            continue
        m = re.search(_MN, veta, re.I)
        rec = {"druh": druhy[0]}
        if m and len(druhy) == 1:
            rec["mnozstvi"] = float(m.group(1).replace(" ", "").replace(".", "").replace(",", "."))
            rec["jednotka"] = "kg" if m.group(2).lower().startswith("k") and "g" in m.group(2).lower() else "ks"
        if not any(r["druh"] == rec["druh"] for r in out):
            out.append(rec)
        for d in druhy[1:]:
            if not any(r["druh"] == d for r in out):
                out.append({"druh": d})
    return out


def iso(d: date | datetime | None) -> str | None:
    return d.isoformat()[:10] if d else None
