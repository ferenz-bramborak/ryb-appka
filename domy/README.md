# Domeček u lesa

Aplikace: https://claude.ai/artifact/R2yVkpNvzt3uuAL8nbKR9n

Hledání rodinného domu u Brna pro rodinu z Kohoutovic: blízko bráchy (Rosice), dědy (Střelice)
a rodičů (Oslavany), u lesa, se zahradou pro psy a děti, ideálně bungalov, do 15 mil. Kč, 4+ pokoje,
žádné řadovky.

## Jak to funguje

1. **Stahování** (`python -m domy.run`) projde nabídky domů na prodej v okresech Brno-venkov
   a Brno-město na těchto webech:
   - **Sreality** (veřejné JSON API) – sem inzeruje i většina brněnských realitek
     (RE/MAX, M&M, Century 21, Bidli, lokální kanceláře),
   - **iDNES Reality** (HTML),
   - **Bezrealitky** (přímo od majitelů),
   - **Reas** (agregátor + vlastní prodeje).
2. Zahodí, co nesplňuje tvrdá kritéria (`domy/config.py`): cena, počet pokojů, pozemek,
   řadové domy, vzdálenost od rodiny.
3. Sloučí stejný dům inzerovaný na více webech do jedné karty.
4. Z inzerátu vytáhne cenu, plochy, dispozici, typ (bungalov/patrový), stavbu, stav, PENB,
   vodu, kanalizaci, garáž a sklep; ze Sreality vzdálenost ke školce, škole, obchodu, lékaři,
   autobusu a vlaku (u ostatních webů odhad podle nejbližšího inzerátu do 700 m).
5. Ke každému domu spočítá:
   - **les** – vzdálenost k souvislému lesu a podíl lesa do 1 a 2 km
     (satelitní mapa ESA WorldCover 10 m, předpočítaná v `data/geo_mrizka.npz`),
   - **kopce** – převýšení a členitost terénu do 1,5 km (Copernicus DEM 30 m),
   - **dojezdy autem** do Rosic, Střelic, Padochova, centra Brna, Hranic na Moravě a k nejbližšímu
     exitu D1 (OpenStreetMap / OSRM).
6. Uloží stav do `data/stav.json` (historie cen, kdy se dům objevil, kdy zmizel) a připraví
   export pro aplikaci do `data/export/`.

## Aplikace

`app/hledani-domu.html` je stránka publikovaná jako Claude artefakt. Data čte ze sdílené
databáze artefaktu:

| Kolekce | Co obsahuje | Kdo zapisuje |
|---|---|---|
| `nabidky/meta`, `nabidky/cast-N`, `nabidky/mapa` | domy, stav zdrojů, mapka lesů | ranní rutina (Claude) |
| `foto/mapa` | id domu → náhled (soubor nahraný k artefaktu) | ranní rutina |
| `oznaceni/<id>` | hlasy Top / Možná / Ne obou partnerů, společná poznámka | aplikace |
| `analyzy/porovnani` | rozbor vybraných domů od Clauda | rutina nebo tlačítko v aplikaci |
| `nastaveni/vahy` | váhy skóre | aplikace |

Každé ráno rutina spustí stahování, nahraje nové domy do databáze a pokud se změnil výběr
Top/Možná (nebo přibyl zajímavý dům), napíše nový rozbor. Postup je v `RUTINA.md`.

## Ruční spuštění

```sh
pip install -r domy/requirements.txt
python -m domy.run                 # stáhnout, ohodnotit, exportovat
python -m domy.run --bez-stahovani # jen přepočítat a exportovat
python -m domy.geo_sestav          # znovu sestavit mapu lesů a reliéfu (není potřeba)
python -m unittest domy.test_domy
```
