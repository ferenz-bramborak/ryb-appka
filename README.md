# Rybářský průvodce

Mobilní webová aplikace (PWA – instaluje se z prohlížeče na plochu telefonu) pro rybáře v ČR.
Když jdeš k vodě, ukáže:

- **na jakém jsi revíru** – podle GPS a skutečného tvaru revíru (polygon/tok), číslo, svaz, MO,
- **pstruhový / mimopstruhový**, jestli se dnes smí lovit, denní doba lovu, co je hájené,
  lovné míry, povolené způsoby lovu, limity a povinná výbava,
- **co se tu chytá** – oficiální statistika úlovků z povolenek po druzích (ČRS)
  a úlovky z rybářských fór za poslední 3 měsíce,
- **vysazování ryb** s datem a množstvím,
- **stav vody** z nejbližší stanice ČHMÚ na stejném toku (stav, průtok, trend, teplota vody, povodňový stupeň),
- **počasí** (teplota, tlak a jeho trend, vítr, výhled na 4 dny, slunce, měsíc),
- **doporučení, na co chytat** – druh, nástraha, technika a čas podle úlovků, teploty vody, tlaku a stavu vody,
- popis revíru, kontakty na hospodařící organizaci a navigaci k vodě.

Funguje i offline u vody (naposledy otevřené revíry zůstávají v mobilu).

## Zdroje dat

| Zdroj | Co dává | Jak často |
|---|---|---|
| ČRS – veřejné API rybsvaz.cz | 1 449 revírů všech 7 územních svazů: popis, polygon, pravidla lovu k datu, kontakty | denně |
| ČRS – statistika úlovků | úlovky po revírech a druzích za poslední roky | měsíčně |
| ČRS – aktuality (CMS) | týdenní hlášení o vysazování (Východočeský ÚS) a zprávy o zarybnění revírů Rady ČRS | denně |
| MRS – veřejné API mrsbrno.cz + mapa revírů (KML) | 333 revírů: popis, typ, tvar revíru | denně |
| mrk.cz „Můj lov“, chytej.cz Trofejní úlovky | úlovky rybářů za 3 měsíce (druh, délka, nástraha, způsob) | denně |
| ČHMÚ otevřená data | 546 vodoměrných stanic | každou hodinu |
| Open-Meteo | počasí (volá přímo aplikace) | živě |

Omezení, o kterých je dobré vědět:
- Úlovky z fór: rybáři svůj revír často neuvádějí („Svazovka“, „Tam, kde to mám rád“), k revíru se
  přiřadí jen zápisy s číslem nebo jednoznačným názvem revíru. Zápisy jen s názvem řeky se ukazují u revírů
  na tom toku zvlášť.
- Vysazování s datem pravidelně zveřejňuje jen Východočeský ÚS a Rada ČRS. U MO se množství uvádí za celou
  organizaci, ne za konkrétní revír.
- MRS nepublikuje pravidla lovu strukturovaně – u moravských revírů se použijí obecná pravidla
  (vyhláška 197/2004 Sb.) a popis revíru z BPVRP.

## Struktura

| Složka | Co dělá |
|---|---|
| `web/` | Aplikace (čisté HTML/CSS/JS, bez build kroku). |
| `scraper/sources/` | Jeden modul na zdroj (`crs`, `mrs`, `statistika`, `vysazeni`, `ulovky_fora`, `chmi`). |
| `scraper/build.py` | Spojí data, přiřadí úlovky a vysazení k revírům a zapíše `web/data/`. |
| `.github/workflows/data-a-web.yml` | Plánované stahování a nasazení na GitHub Pages. Data drží ve větvi `data`. |

## Spuštění lokálně

```sh
pip install -r scraper/requirements.txt
python -m scraper.run                    # denní stažení (~3 min)
python -m scraper.run --only statistika  # statistika úlovků (~5 min)
cd web && python -m http.server 8000     # otevři http://localhost:8000
python -m pytest tests                   # testy parserů
```

## Nasazení

1. V repozitáři: *Settings → Pages → Source: GitHub Actions*.
2. Spusť workflow „Data a web“ (*Actions → Data a web → Run workflow*, režim `vse`), nebo počkej na push do `master`.
3. Aplikace poběží na `https://<uživatel>.github.io/<repo>/`. Na mobilu ji otevři a dej „Přidat na plochu“.

Pravidla v aplikaci jsou informativní – vždy platí rybářský řád a bližší podmínky výkonu rybářského práva
daného svazu.
