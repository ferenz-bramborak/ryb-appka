// Doporučení „na co a jak chytat“: kombinuje úlovky z revíru za poslední
// 3 měsíce, teplotu vody, tlak, srážky, stav vody a dobu hájení.
import { isTrout, speciesKey } from './rules.js';

// t: [min, opt_od, opt_do, max] teploty vody °C, ve kterých druh bere.
const DRUHY = {
  'kapr': { t: [6, 15, 25, 30], dravec: false, noc: false,
    nastrahy: { studena: ['malé pelety', 'kukuřice', 'červi'], mirna: ['boilies', 'kukuřice', 'pelety'], tepla: ['boilies', 'pelety', 'kukuřice'] },
    metoda: 'feeder / method feeder, položená' },
  'amur': { t: [14, 20, 28, 32], dravec: false, noc: false,
    nastrahy: { studena: ['kukuřice'], mirna: ['kukuřice', 'boilies'], tepla: ['plovoucí chleba', 'kukuřice', 'rákos'] },
    metoda: 'položená, na hladině' },
  'lín': { t: [12, 17, 24, 28], dravec: false, noc: false,
    nastrahy: { studena: ['žížala'], mirna: ['žížala', 'patentka', 'kukuřice'], tepla: ['žížala', 'kukuřice'] },
    metoda: 'plavaná u rostlin, ráno' },
  'cejn': { t: [6, 12, 22, 27], dravec: false, noc: false,
    nastrahy: { studena: ['patentka', 'červi'], mirna: ['červi', 'kukuřice'], tepla: ['kukuřice', 'pelety'] },
    metoda: 'feeder' },
  'plotice': { t: [2, 8, 20, 26], dravec: false, noc: false,
    nastrahy: { studena: ['patentka', 'červi'], mirna: ['červi', 'chleba'], tepla: ['chleba', 'kukuřice'] },
    metoda: 'plavaná, jemný feeder' },
  'karas': { t: [10, 16, 25, 30], dravec: false, noc: false,
    nastrahy: { studena: ['červi'], mirna: ['červi', 'kukuřice'], tepla: ['kukuřice', 'těsto'] },
    metoda: 'plavaná' },
  'štika': { t: [3, 6, 17, 24], dravec: true, noc: false,
    nastrahy: { studena: ['mrtvá rybka', 'pomalý jig – gumová nástraha'], mirna: ['wobler', 'gumová nástraha', 'rotačka'], tepla: ['povrchové nástrahy', 'plandavka'] },
    metoda: 'přívlač, na rybku' },
  'candát': { t: [5, 10, 20, 26], dravec: true, noc: true,
    nastrahy: { studena: ['gumová nástraha u dna', 'rybka'], mirna: ['gumová nástraha (jig)', 'rybka'], tepla: ['rybka', 'gumová nástraha'] },
    metoda: 'jig u dna, za šera a v noci' },
  'okoun': { t: [5, 10, 22, 27], dravec: true, noc: false,
    nastrahy: { studena: ['dropshot', 'malá gumová nástraha'], mirna: ['malá rotačka', 'gumová nástraha', 'žížala'], tepla: ['rotačka', 'malý wobler'] },
    metoda: 'přívlač, dropshot' },
  'sumec': { t: [16, 20, 28, 32], dravec: true, noc: true,
    nastrahy: { studena: ['rybka'], mirna: ['svazek žížal', 'rybka'], tepla: ['svazek žížal', 'rybka', 'halibut pelety'] },
    metoda: 'položená v noci, kvok' },
  'bolen': { t: [10, 14, 24, 28], dravec: true, noc: false,
    nastrahy: { studena: ['plandavka'], mirna: ['plandavka', 'štíhlý wobler'], tepla: ['povrchové nástrahy', 'plandavka'] },
    metoda: 'rychlá přívlač u proudu' },
  'úhoř': { t: [12, 16, 24, 28], dravec: true, noc: true,
    nastrahy: { studena: ['žížala'], mirna: ['žížala', 'rybka'], tepla: ['žížala', 'rybka'] },
    metoda: 'položená v noci, nejlépe při stoupající kalné vodě' },
  'jelec tloušť': { t: [4, 10, 22, 27], dravec: false, noc: false,
    nastrahy: { studena: ['červi', 'chleba'], mirna: ['chleba', 'malý wobler', 'třešně'], tepla: ['třešně', 'hmyz', 'malý wobler'] },
    metoda: 'plavaná, lehká přívlač' },
  'parma': { t: [8, 12, 22, 26], dravec: false, noc: false,
    nastrahy: { studena: ['červi'], mirna: ['sýr', 'červi', 'pelety'], tepla: ['sýr', 'salám', 'pelety'] },
    metoda: 'feeder v proudu' },
  'pstruh obecný': { t: [2, 6, 15, 19], dravec: true, noc: false,
    nastrahy: { studena: ['nymfa', 'malý wobler'], mirna: ['rotačka', 'wobler', 'muška'], tepla: ['suchá muška', 'malá rotačka'] },
    metoda: 'přívlač, muškaření' },
  'pstruh duhový': { t: [3, 7, 17, 21], dravec: true, noc: false,
    nastrahy: { studena: ['nymfa', 'malá rotačka'], mirna: ['rotačka', 'wobler', 'těsto (kde povoleno)'], tepla: ['muška', 'malá rotačka'] },
    metoda: 'přívlač, muškaření' },
  'lipan': { t: [3, 6, 14, 18], dravec: false, noc: false,
    nastrahy: { studena: ['nymfa'], mirna: ['nymfa', 'suchá muška'], tepla: ['suchá muška'] },
    metoda: 'muškaření' },
  'mník jednovousý': { t: [0, 1, 8, 14], dravec: true, noc: true,
    nastrahy: { studena: ['rybka', 'žížala'], mirna: ['žížala'], tepla: ['žížala'] },
    metoda: 'položená v noci' },
};


export function canonicalSpecies(name) {
  const key = speciesKey(name);
  return DRUHY[key] ? key : null;
}

const VYCHOZI_PSTRUH = ['pstruh obecný', 'pstruh duhový', 'lipan', 'jelec tloušť'];
const VYCHOZI_MIMO = ['kapr', 'cejn', 'štika', 'candát', 'okoun', 'plotice', 'jelec tloušť'];

function tempFactor(t, [min, a, b, max]) {
  if (t == null) return 0.8;
  if (t >= a && t <= b) return 1;
  if (t < min || t > max) return 0.15;
  return t < a ? 0.15 + 0.85 * (t - min) / (a - min) : 0.15 + 0.85 * (max - t) / (max - b);
}

function band(t) {
  if (t == null) return 'mirna';
  return t < 10 ? 'studena' : t > 20 ? 'tepla' : 'mirna';
}

// Podíl druhů v posledním roce oficiální statistiky úlovků (ks).
function officialShares(statistika) {
  if (!statistika?.druhy?.length) return { shares: new Map(), rok: null };
  const rok = statistika.roky?.[0]?.rok;
  const rows = statistika.druhy
    .map(d => ({ druh: canonicalSpecies(d.druh), ks: d.roky.find(r => r.rok === rok)?.ks ?? 0 }))
    .filter(d => d.druh && d.ks > 0);
  const total = rows.reduce((s, d) => s + d.ks, 0);
  return { shares: new Map(rows.map(d => [d.druh, { share: d.ks / total, ks: d.ks }])), rok };
}


export function recommend({ revir, status, catchSummary, statistika, weather, water, waterTemp, date = new Date() }) {
  const t = waterTemp?.value ?? null;
  const tips = [];
  const forum = new Map();
  const forumTotal = catchSummary.reduce((s, c) => s + c.pocet, 0);
  for (const c of catchSummary) {
    const key = canonicalSpecies(c.druh);
    if (key) forum.set(key, { ...c, share: c.pocet / forumTotal });
  }
  const { shares: official, rok } = officialShares(statistika);

  const candidates = new Set([...official.keys(), ...forum.keys()]);
  if (candidates.size < 3) for (const d of isTrout(revir) ? VYCHOZI_PSTRUH : VYCHOZI_MIMO) candidates.add(d);

  const pTrend = weather?.pressureTrend24h ?? 0;
  const falling = pTrend <= -3;
  const risingFast = pTrend >= 5;
  const cloudy = (weather?.current?.cloud ?? 50) >= 60;
  const waterRising = water?.trend === 'roste' || (weather?.rainLast3d ?? 0) >= 15;
  const flood = (water?.spa ?? 0) >= 1;
  const hajene = status?.hajene ?? new Set();
  const zakazane = status?.zakazane ?? new Set();

  const result = [];
  for (const druh of candidates) {
    const p = DRUHY[druh];
    if (!p || hajene.has(druh)) continue;
    const why = [];
    const off = official.get(druh);
    const fo = forum.get(druh);
    let score = 0.2;
    if (off) { score = 0.3 + 0.7 * Math.sqrt(off.share); why.push(`${off.ks} ks uloveno na revíru v roce ${rok} (statistika svazu)`); }
    if (fo) { score = Math.max(score, 0.35) + 0.15; why.push(`${fo.pocet}× zmíněn v úlovcích rybářů za 3 měsíce`); }
    if (!off && !fo) why.push('typický druh pro tento typ revíru');

    const tf = tempFactor(t, p.t);
    score *= tf;
    if (t != null) {
      if (tf >= 0.95) why.push(`voda ~${Math.round(t)} °C mu sedí`);
      else if (tf < 0.5) why.push(`při ~${Math.round(t)} °C bere spíš slabě`);
    }
    if (p.dravec && falling) { score *= 1.2; why.push('klesající tlak aktivuje dravce'); }
    if (p.dravec && cloudy) { score *= 1.1; why.push('zataženo – dravci loví i přes den'); }
    if (risingFast) score *= 0.85;
    if (waterRising && ['úhoř', 'sumec', 'jelec tloušť', 'cejn', 'parma'].includes(druh)) { score *= 1.2; why.push('zvýšená/kalná voda mu svědčí'); }
    if (flood && !['úhoř', 'sumec'].includes(druh)) score *= 0.6;

    let metoda = fo?.metody?.[0] ?? p.metoda;
    if (zakazane.has('privlac') && p.dravec && !['sumec', 'úhoř', 'candát', 'mník jednovousý'].includes(druh)) {
      score *= 0.5;
      metoda = 'na rybku / položenou (přívlač je teď zakázána)';
    }
    const nastrahy = [...(fo?.nastrahy ?? []).slice(0, 2)];
    for (const n of p.nastrahy[band(t)]) if (nastrahy.length < 3 && !nastrahy.includes(n)) nastrahy.push(n);

    result.push({
      druh, score: Math.min(1, score), why, nastrahy, metoda,
      kdy: p.noc ? 'za šera a v noci' : t != null && t > 22 ? 'brzy ráno a večer' : t != null && t < 10 ? 'kolem poledne a odpoledne, kdy je voda nejteplejší' : 'ráno a k večeru',
    });
  }
  result.sort((a, b) => b.score - a.score);

  if (risingFast) tips.push('Tlak prudce stoupá (po frontě) – ryby bývají opatrné, zkus jemnější montáž a menší nástrahy.');
  if (falling) tips.push('Tlak klesá před změnou počasí – často krátké období velmi dobrého záběru.');
  if (flood) tips.push('Vysoký stav vody – drž se klidných zátočin a ústí přítoků, buď opatrný u břehu.');
  if ((weather?.current?.wind ?? 0) >= 8) tips.push('Silný vítr – lov na návětrném břehu, kam vítr žene potravu.');
  if (t != null && t < 6) tips.push('Studená voda – ryby jsou v hlubších místech, nástrahu veď pomalu u dna.');

  return { species: result.slice(0, 4), tips };
}
