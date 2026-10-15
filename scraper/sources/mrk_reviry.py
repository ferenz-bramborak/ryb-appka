"""mrk.cz – soupisy svazových revírů: alternativní názvy, které rybáři používají
(„NM“, „D5“, „Nové Mlýny“…), a čerstvé příspěvky z diskusí k revírům.

Alternativní názvy výrazně zlepšují párování úlovků z „Můj lov“ na revír.
mrk.cz je citlivý na zátěž, proto běží pomalu a jen jednou týdně.
"""
from __future__ import annotations

import html
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta

from ..http import get_text
from ..text import html_text

NAZEV = "mrk.cz revíry"
log = logging.getLogger(__name__)

MRK = "https://www.mrk.cz/"
MENU_CZ = [13, 5, 6, 7, 8, 9, 10, 11, 12, 29, 21, 22, 23, 24, 25, 26, 27, 28]
DISKUSE_DNU = 31


def _get(url: str) -> str:
    for pokus in range(4):
        t = get_text(url, encoding="iso-8859-2", delay=1.0 + 4 * pokus)
        if "System je pretizen" not in t:
            return t
    raise RuntimeError("mrk.cz je přetížené")


def _seznam() -> dict[str, str]:
    """mrk id → číslo revíru (6 číslic)."""
    out = {}
    for menu in MENU_CZ:
        h = _get(f"{MRK}rybarske-reviry.php?menuid={menu}")
        for mid, cislo in re.findall(r'href="rybarske-reviry\.php\?id=(\d+)"[^>]*>\s*(\d{6})\s*-', h):
            out[mid] = cislo
    return out


def _detail(mid: str, cislo: str, od: date) -> dict | None:
    try:
        h = _get(f"{MRK}rybarske-reviry.php?id={mid}")
    except Exception as e:  # noqa: BLE001
        log.debug("mrk revír %s: %s", mid, e)
        return None
    rec = {"id": cislo, "url": f"{MRK}rybarske-reviry.php?id={mid}"}
    m = re.search(r"Alternativní názvy revíru na MRKu:\s*(.*?)</p>", h, re.S)
    if m:
        rec["aliasy"] = [a.strip() for a in html.unescape(m.group(1)).split(",") if a.strip()]
    prispevky = []
    for nick, cas, body in re.findall(
            r"answer\('([^']*)', \d+, '(\d{1,2}\.\d{1,2}\.\d{4}) [\d:]+'\).*?class=\"zapistelo\">(.*?)</div><ul class=\"rating\"",
            h, re.S):
        d = datetime.strptime(cas, "%d.%m.%Y").date()
        if d < od:
            continue
        text = html_text(re.sub(r"<i [^>]*class=\"to\".*?</i></i>\s*&gt;&gt;", "", body))
        if len(text) >= 15:
            prispevky.append({"datum": d.isoformat(), "autor": nick, "text": text[:400]})
    if prispevky:
        rec["diskuse"] = prispevky
    return rec


def fetch() -> list[dict]:
    od = date.today() - timedelta(days=DISKUSE_DNU)
    seznam = _seznam()
    log.info("mrk.cz: %d svazových revírů", len(seznam))
    with ThreadPoolExecutor(max_workers=2) as pool:
        out = [r for r in pool.map(lambda kv: _detail(kv[0], kv[1], od), seznam.items()) if r]
    log.info("mrk.cz: %d revírů načteno, %d s aliasy, %d s čerstvou diskusí",
             len(out), sum(1 for r in out if r.get("aliasy")), sum(1 for r in out if r.get("diskuse")))
    return out
