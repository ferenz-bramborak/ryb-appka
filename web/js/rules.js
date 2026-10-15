// Orientační pravidla lovu podle vyhlášky č. 197/2004 Sb. (doby hájení a sezóna
// pstruhových revírů). Konkrétní revír může mít bližší podmínky přísnější –
// ty jsou v popisu revíru a v Bližších podmínkách výkonu rybářského práva
// daného svazu. Appka je jen pomůcka, rozhoduje platný předpis.

// [měsíc, den] včetně; rozsah může přecházet přes Nový rok.
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

export function seasonStatus(revir, date = new Date()) {
  const notes = [];
  if (isTrout(revir)) {
    const open = inRange(date, PSTRUH_SEZONA.od, PSTRUH_SEZONA.do);
    notes.push({
      level: open ? 'good' : 'bad',
      text: open
        ? `Pstruhový revír – sezóna běží (${fmt(PSTRUH_SEZONA.od)}–${fmt(PSTRUH_SEZONA.do)}).`
        : `Pstruhový revír – lov je povolen jen ${fmt(PSTRUH_SEZONA.od)}–${fmt(PSTRUH_SEZONA.do)}. Teď je zavřeno.`,
    });
    return { open, notes };
  }
  const hajene = HAJENI.filter(h => inRange(date, h.od, h.do));
  if (hajene.length) {
    notes.push({
      level: 'warn',
      text: 'Teď hájeno: ' + hajene.map(h => `${h.druh} (${fmt(h.od)}–${fmt(h.do)})`).join(', ') + '.',
    });
  }
  if (inRange(date, [1, 1], [6, 15])) {
    notes.push({ level: 'warn', text: 'Do 15. 6. platí v mimopstruhových revírech omezení přívlače – ověř bližší podmínky svazu.' });
  }
  return { open: true, notes };
}

export function isProtected(druh, date = new Date()) {
  const d = (druh ?? '').toLowerCase();
  return HAJENI.some(h => d.startsWith(h.druh) && inRange(date, h.od, h.do));
}
