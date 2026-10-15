// Pravidla lovu. U revírů ČRS se berou z rybsvaz.cz (platná k datu stažení dat),
// jinde (MRS) se použijí orientační obecná pravidla z vyhlášky č. 197/2004 Sb.
// Rozhoduje vždy platný rybářský řád a bližší podmínky svazu.
import { normalize } from './data.js';

const HAJENI = [
  { druh: 'štika', od: [1, 1], do: [6, 15] },
  { druh: 'candát', od: [1, 1], do: [6, 15] },
  { druh: 'bolen', od: [1, 1], do: [6, 15] },
  { druh: 'sumec', od: [1, 1], do: [6, 15] },
  { druh: 'pstruh obecný', od: [9, 1], do: [4, 15] },
  { druh: 'lipan', od: [12, 1], do: [5, 31] },
];
const PSTRUH_SEZONA = { od: [4, 16], do: [8, 31] };

function inRange(date, od, doo) {
  const md = (date.getMonth() + 1) * 100 + date.getDate();
  const a = od[0] * 100 + od[1];
  const b = doo[0] * 100 + doo[1];
  return a <= b ? md >= a && md <= b : md >= a || md <= b;
}
const fmt = ([m, d]) => `${d}. ${m}.`;

export function isTrout(revir) {
  return revir?.typ === 'pstruhovy';
}

// „Štika obecná“ i „štika“ → „štika“; „Jelec tloušť“ → „jelec tloušť“.
export function speciesKey(name) {
  const n = normalize(name);
  const map = [
    ['pstruh duh', 'pstruh duhový'], ['pstruh obec', 'pstruh obecný'], ['jelec tloust', 'jelec tloušť'],
    ['jelec jesen', 'jelec jesen'], ['mnik', 'mník jednovousý'], ['candat', 'candát'], ['stika', 'štika'],
    ['sumec', 'sumec'], ['kapr', 'kapr'], ['amur', 'amur'], ['lin', 'lín'], ['cejn', 'cejn'], ['bolen', 'bolen'],
    ['okoun', 'okoun'], ['parma', 'parma'], ['uhor', 'úhoř'], ['lipan', 'lipan'], ['siven', 'siven'],
    ['hlavatka', 'hlavatka'], ['karas', 'karas'], ['ostroretka', 'ostroretka'], ['podoustev', 'podoustev'],
    ['plotice', 'plotice'], ['tloust', 'jelec tloušť'],
  ];
  for (const [prefix, key] of map) if (n.startsWith(prefix)) return key;
  return n;
}

// Stav lovu na revíru dnes: {open, notes[], hajene:Set, zakazaneZpusoby:Set}
export function seasonStatus(revir, detail, date = new Date()) {
  const p = detail?.pravidla;
  const notes = [];
  const hajene = new Set();
  const zakazane = new Set();

  if (p) {
    const lovRyb = p.podminky?.find(x => normalize(x.nazev) === 'lov ryb');
    const open = p.doba_lovu !== 'zakázáno' && lovRyb?.povoleno !== false;
    const hajeneNazvy = (p.druhy ?? []).filter(d => d.hajen).map(d => d.druh.toLowerCase());
    for (const d of hajeneNazvy) hajene.add(speciesKey(d));
    const zakazaneNazvy = (p.zpusoby ?? []).filter(z => !z.povoleno).map(z => z.nazev.toLowerCase());
    for (const z of zakazaneNazvy) zakazane.add(normalize(z));
    if (!open) {
      notes.push({ level: 'bad', text: isTrout(revir)
        ? `Pstruhový revír – teď se tu nesmí lovit (sezóna ${fmt(PSTRUH_SEZONA.od)}–${fmt(PSTRUH_SEZONA.do)}).`
        : 'Lov je na revíru teď zakázán.' });
    } else if (p.doba_lovu) {
      notes.push({ level: 'good', text: `Lov dnes povolen ${p.doba_lovu}.` });
    }
    if (open && hajene.size) notes.push({ level: 'warn', text: `Teď hájeno nebo zakázáno ponechat: ${hajeneNazvy.join(', ')}.` });
    if (open && zakazane.size) notes.push({ level: 'warn', text: `Teď zakázané způsoby lovu: ${zakazaneNazvy.join(', ')}.` });
    return { open, notes, hajene, zakazane, zdroj: 'svaz', platneK: p.platne_k };
  }

  // Revíry bez pravidel z API (MRS): obecná pravidla.
  if (isTrout(revir)) {
    const open = inRange(date, PSTRUH_SEZONA.od, PSTRUH_SEZONA.do);
    notes.push({ level: open ? 'good' : 'bad', text: open
      ? `Pstruhový revír – sezóna běží (${fmt(PSTRUH_SEZONA.od)}–${fmt(PSTRUH_SEZONA.do)}).`
      : `Pstruhový revír – lov je povolen jen ${fmt(PSTRUH_SEZONA.od)}–${fmt(PSTRUH_SEZONA.do)}. Teď je zavřeno.` });
    if (!open) return { open, notes, hajene, zakazane, zdroj: 'obecne' };
  }
  for (const h of HAJENI) if (inRange(date, h.od, h.do)) hajene.add(h.druh);
  if (hajene.size) notes.push({ level: 'warn', text: `Obecně hájeno: ${[...hajene].join(', ')} (ověř v BPVRP MRS).` });
  if (!isTrout(revir) && inRange(date, [1, 1], [6, 15])) {
    notes.push({ level: 'warn', text: 'Do 15. 6. platí v mimopstruhových revírech omezení přívlače.' });
  }
  return { open: true, notes, hajene, zakazane, zdroj: 'obecne' };
}
