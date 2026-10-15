"""Stáhne data ze všech zdrojů a zapíše je do web/data/*.json.

Když zdroj selže, ponechají se jeho data z minulého běhu (aplikace tak
nepřijde o revíry kvůli jednomu nedostupnému webu).

Spuštění:  python -m scraper.run [--only voda]
"""
from __future__ import annotations

import argparse
import json
import logging
import traceback
from datetime import datetime, timezone
from pathlib import Path

from .schema import to_json
from .sources import ALL

OUT = Path(__file__).resolve().parent.parent / "web" / "data"
log = logging.getLogger("scraper")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read(name: str, default):
    p = OUT / name
    if p.exists():
        try:
            return json.loads(p.read_text("utf-8"))
        except json.JSONDecodeError:
            log.warning("Poškozený %s, začínám znovu", name)
    return default


def write(name: str, data) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = OUT / f".{name}.tmp"
    tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), "utf-8")
    tmp.replace(OUT / name)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["reviry", "ulovky", "voda"], help="spustit jen zdroje daného druhu")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    reviry = read("reviry.json", {"reviry": []})["reviry"]
    vysazeni = read("vysazeni.json", {"vysazeni": {}})["vysazeni"]
    ulovky = read("ulovky.json", {"ulovky": {}})["ulovky"]
    stanice = read("voda.json", {"stanice": []})["stanice"]
    meta = read("meta.json", {"zdroje": {}})
    meta.setdefault("zdroje", {})

    for src in ALL:
        if args.only and src.DRUH != args.only:
            continue
        log.info("Zdroj %s …", src.NAZEV)
        try:
            result = src.fetch()
            if src.DRUH == "reviry":
                new_reviry, new_vys = result
                if not new_reviry:
                    raise RuntimeError("zdroj nevrátil žádné revíry")
                reviry = [r for r in reviry if r.get("_zdroj") != src.NAZEV]
                reviry += [{**to_json(r), "_zdroj": src.NAZEV} for r in new_reviry]
                vysazeni.update(to_json(new_vys))
                pocet = len(new_reviry)
            elif src.DRUH == "ulovky":
                ulovky = to_json(result)
                pocet = sum(len(v) for v in ulovky.values())
            else:
                if not result:
                    raise RuntimeError("zdroj nevrátil žádné stanice")
                stanice = to_json(result)
                pocet = len(stanice)
            meta["zdroje"][src.NAZEV] = {"ok": True, "pocet": pocet, "cas": now_iso()}
            log.info("  OK, %d záznamů", pocet)
        except Exception as e:  # noqa: BLE001 – jeden zdroj nesmí shodit ostatní
            log.error("  CHYBA: %s", e)
            log.debug(traceback.format_exc())
            prev = meta["zdroje"].get(src.NAZEV, {})
            meta["zdroje"][src.NAZEV] = {**prev, "ok": False, "chyba": str(e), "cas": now_iso()}

    ids = {r["id"] for r in reviry}
    ulovky = {k: v for k, v in ulovky.items() if k in ids}
    reviry.sort(key=lambda r: (r.get("nazev") or "", r["id"]))
    meta["generated"] = now_iso()

    write("reviry.json", {"reviry": reviry})
    write("vysazeni.json", {"vysazeni": vysazeni})
    write("ulovky.json", {"ulovky": ulovky})
    write("voda.json", {"stanice": stanice})
    write("meta.json", meta)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
