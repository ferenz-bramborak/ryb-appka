# Rybářský průvodce

Mobilní webová aplikace (PWA – instaluje se z prohlížeče na plochu telefonu) pro rybáře v ČR.
Když jdeš k vodě, ukáže:

- **jaký je to revír** – nejbližší podle GPS, číslo, svaz/MO, popis hranic a bližší podmínky,
- **pstruhový / mimopstruhový** a jestli je teď sezóna, co je hájené,
- **vysazování ryb** (druh, kdy, kolik),
- **úlovky z rybářských fór za poslední 3 měsíce** přiřazené k revíru,
- **stav vody** z nejbližší stanice ČHMÚ (stav, průtok, trend, povodňový stupeň),
- **počasí** (Open-Meteo: teplota, tlak a jeho trend, vítr, výhled na 4 dny, východ/západ slunce, měsíc),
- **doporučení, na co chytat** – druh, nástraha, technika a čas podle úlovků, teploty vody, tlaku a stavu vody.

Funguje i offline u vody (poslední stažená data se drží v mobilu).

## Struktura

| Složka | Co dělá |
|---|---|
| `web/` | Aplikace (čisté HTML/CSS/JS, bez build kroku). Počasí stahuje přímo z mobilu. |
| `web/data/` | JSON data generovaná pipeline – formát popisuje `scraper/schema.py`. |
| `scraper/` | Python pipeline: `python -m scraper.run` stáhne všechny zdroje a zapíše `web/data/`. |
| `.github/workflows/data-a-web.yml` | Denně stahuje revíry/úlovky, každou hodinu stav vody, a nasazuje web na GitHub Pages. |

## Stav zdrojů dat

| Zdroj | Stav |
|---|---|
| Počasí – Open-Meteo | hotovo (volá se z aplikace) |
| Revíry ČRS (všechny územní svazy) | **čeká** – scraper zatím nenapsán |
| Revíry MRS | **čeká** – scraper zatím nenapsán |
| Úlovky z fór (chytej.cz, mrk.cz, …) | **čeká** – scraper zatím nenapsán |
| Stav vody ČHMÚ | **čeká** – načítání zatím nenapsáno |

## Spuštění lokálně

```sh
pip install -r scraper/requirements.txt
python -m scraper.run
cd web && python -m http.server 8000   # otevři http://localhost:8000
```

## Nasazení

V nastavení repozitáře: *Settings → Pages → Source: GitHub Actions*. Pak workflow „Data a web“
nasadí aplikaci na `https://<uživatel>.github.io/<repo>/`. Na mobilu ji otevři a dej „Přidat na plochu“.

Pravidla hájení v aplikaci jsou orientační (vyhláška 197/2004 Sb.) – vždy platí rybářský řád
a bližší podmínky daného svazu.
