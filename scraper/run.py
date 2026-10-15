"""Stáhne data ze zdrojů do data-cache/ a sestaví web/data/.

Když zdroj selže, zůstanou jeho data z minulého běhu (aplikace tak nepřijde
o revíry kvůli jednomu nedostupnému webu).

  python -m scraper.run                 # denní běh: revíry, úlovky, vysazení, voda
  python -m scraper.run --only voda     # hodinový běh: jen stav vody
  python -m scraper.run --only statistika
  python -m scraper.run --build-only    # jen znovu sestavit web/data z cache
"""
from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone

from .build import CACHE, OUT, build
from .sources import chmi, crs, mrs, statistika, ulovky_fora, vysazeni

log = logging.getLogger("scraper")

# (modul, soubor v cache, minimální počet záznamů, aby se výsledek považoval za platný)
DENNI = [
    (crs, "crs.json", 1000),
    (mrs, "mrs.json", 250),
    (ulovky_fora, "ulovky.json", 1),
    (vysazeni, "vysazeni.json", 1),
    (chmi, "voda.json", 300),
]
ZDROJE = {
    "voda": [(chmi, "voda.json", 300)],
    "statistika": [(statistika, "statistika.json", 1000)],
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=sorted(ZDROJE))
    ap.add_argument("--build-only", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    meta_path = OUT / "meta.json"
    meta = json.loads(meta_path.read_text("utf-8")) if meta_path.exists() else {}
    meta.setdefault("zdroje", {})
    CACHE.mkdir(exist_ok=True)

    sources = [] if args.build_only else ZDROJE[args.only] if args.only else DENNI
    for mod, soubor, minimum in sources:
        log.info("Zdroj %s …", mod.NAZEV)
        try:
            data = mod.fetch()
            pocet = len(data)
            if pocet < minimum:
                raise RuntimeError(f"jen {pocet} záznamů (očekáváno aspoň {minimum}) – ponechávám stará data")
            (CACHE / soubor).write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), "utf-8")
            meta["zdroje"][mod.NAZEV] = {"ok": True, "pocet": pocet, "cas": now_iso()}
            log.info("  OK, %d záznamů", pocet)
        except Exception as e:  # noqa: BLE001 – jeden zdroj nesmí shodit ostatní
            log.exception("  CHYBA: %s", e)
            prev = meta["zdroje"].get(mod.NAZEV, {})
            meta["zdroje"][mod.NAZEV] = {**prev, "ok": False, "chyba": str(e)[:300], "cas": now_iso()}

    meta["generated"] = now_iso()
    build(meta)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
