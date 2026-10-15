# Ranní rutina (pro Clauda)

Spouští se každé ráno jako naplánovaná úloha v čerstvé cloudové session. Aplikace:
https://claude.ai/artifact/R2yVkpNvzt3uuAL8nbKR9n

## 1. Příprava

```sh
git fetch origin claude/stoic-fermat-z88fbo
git checkout -B claude/stoic-fermat-z88fbo origin/claude/stoic-fermat-z88fbo
pip install -q -r domy/requirements.txt
python -m domy.run
python -m unittest domy.test_domy
```

Když nějaký zdroj selže, ostatní běží dál a v aplikaci se ukáže výpadek. Když selžou všechny,
zkontroluj síť (`curl -sS "$HTTPS_PROXY/__agentproxy/status"`) a skonči bez zápisu.

## 2. Nahrání do databáze aplikace (nástroj ArtifactData, url výše)

1. `list` kolekce `nabidky` → poznamenej si `version` existujících dokumentů.
2. `batch` se `set` pro `nabidky/meta`, `nabidky/mapa` a všechny `nabidky/cast-N` ze souborů
   `domy/data/export/nabidky/*.json` (`file_path`, u existujících `if_version`).
   Batch max. 50 zápisů a 1 MiB – části rozděl do více batchů (cca 4 části na batch).
   Dokumenty `cast-N`, které už nejsou v `meta.casti`, smaž.
3. Nové náhledy `domy/data/export/foto/<id>.webp` (jen domy, které v aplikaci fotku ještě nemají)
   nahraj nástrojem `Artifact` (`url` výše, `asset: true`, `file_paths` po 25 kusech).
   Z výsledku sestav soubor `{"<id domu>": "/_blob/<id assetu>", …}` (id domu = název souboru
   bez `.webp`), ulož ho do scratchpadu a spusť `python -m domy.run --potvrd-foto <soubor>`.
   Pak `set` dokumentu `foto/mapa` z celého souboru `domy/data/foto_v_db.json`
   (`file_path`, s `if_version` z předchozího `get`).

## 3. Rozbor

1. `list` kolekce `oznaceni` a `get` dokumentu `analyzy/porovnani`.
2. Vybrané domy = ty, kde v `hlasy` má někdo `top` nebo `mozna`. Data domů najdeš
   v `domy/data/export/nabidky/cast-*.json` (pole `id`); pokud tam dům není, je stažený
   z nabídky – použij `snapshot` z označení a napiš, že inzerát zmizel.
3. Nové domy dneška = `prvni` je dnešní datum.
4. Napiš nový rozbor, pokud se výběr změnil oproti `analyzy/porovnani.domy`, pokud se
   vybranému domu změnila cena nebo zmizel, nebo pokud přibyl nový dům, který stojí za pozornost
   (les do 500 m, bungalov, 5+ pokojů, pozemek 800 m²+, dobrý stav, rodina do 15 min).
   Jinak rozbor nech být.
5. Rozbor piš česky, věcně, markdownem (aplikace umí `###`, odrážky, `**tučně**`):
   - `### Novinky` – nové zajímavé domy (obec, cena, proč), max 5,
   - `### Pořadí` – vybrané domy očíslované s jednou větou proč,
   - `### Dům po domu` – plusy, minusy, rizika (stav, PENB, pozemek, sousedé, hluk, dojezdy),
   - `### Na co se zeptat na prohlídce`,
   - `### Doporučení`.
   Rodina: on 40, ona 33, dcera 8 měsíců, další dítě do 2 let, dva psi; teď panelák
   v Brně-Kohoutovicích. Chtějí les a kopce (ne placku s poli), zahradu, ne řadovku, ideálně
   bungalov k nastěhování, zděný, 4+ pokoje, do 15 mil.; brácha Rosice, děda Střelice,
   rodiče Oslavany, D1 blízko. Poznámky z `oznaceni.poznamka` ber v úvahu.
6. `set` dokumentu `analyzy/porovnani` (s `if_version`) na
   `{text, cas: <ISO teď>, autor: "rutina", domy: [id vybraných domů]}`.

## 4. Uložení stavu

```sh
git add domy/data/stav.json domy/data/foto_v_db.json
git commit -m "Domy: aktualizace nabídek $(date -u +%F)"
git push -u origin claude/stoic-fermat-z88fbo
```

Data z databáze (označení, poznámky) do repozitáře nepiš. Na konci jednou větou shrň:
kolik nových domů, kolik celkem, co se změnilo u vybraných.
