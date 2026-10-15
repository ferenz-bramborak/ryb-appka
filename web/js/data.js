// Načítání dat generovaných pipeline (scraper/) a geometrické pomůcky.

const cache = new Map();

async function loadJson(path) {
  if (cache.has(path)) return cache.get(path);
  const p = fetch(`data/${path}`, { cache: 'no-cache' })
    .then(r => (r.ok ? r.json() : null))
    .catch(() => null);
  cache.set(path, p);
  return p;
}

export async function loadIndex() {
  const [reviry, voda, meta] = await Promise.all([
    loadJson('reviry.json'),
    loadJson('voda.json'),
    loadJson('meta.json'),
  ]);
  return { reviry: reviry?.reviry ?? [], stanice: voda?.stanice ?? [], meta: meta ?? {} };
}

export function loadDetail(id) {
  return loadJson(`r/${encodeURIComponent(id)}.json`).then(d => d ?? {});
}

export function normalize(s) {
  return (s ?? '')
    .toString()
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

export function distanceKm(a, b) {
  const R = 6371;
  const toRad = d => (d * Math.PI) / 180;
  const dLat = toRad(b.lat - a.lat);
  const dLon = toRad(b.lon - a.lon);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

// Vzdálenost bodu od úsečky (v km, lokální rovinná aproximace – stačí na stovky metrů).
function segDistanceKm(p, a, b) {
  const kx = 111.32 * Math.cos((p.lat * Math.PI) / 180);
  const ky = 110.57;
  const ax = (a[1] - p.lon) * kx, ay = (a[0] - p.lat) * ky;
  const bx = (b[1] - p.lon) * kx, by = (b[0] - p.lat) * ky;
  const dx = bx - ax, dy = by - ay;
  const len2 = dx * dx + dy * dy;
  const t = len2 ? Math.max(0, Math.min(1, -(ax * dx + ay * dy) / len2)) : 0;
  return Math.hypot(ax + t * dx, ay + t * dy);
}

function pointInRing(p, ring) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [yi, xi] = ring[i];
    const [yj, xj] = ring[j];
    if ((yi > p.lat) !== (yj > p.lat) && p.lon < ((xj - xi) * (p.lat - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

// Vzdálenost od tvaru revíru: 0 uvnitř polygonu, jinak k nejbližší hraně/linii.
export function shapeDistanceKm(casti, typ, p) {
  if (!casti?.length) return Infinity;
  if (typ === 'polygon' && casti.some(r => pointInRing(p, r))) return 0;
  let best = Infinity;
  for (const part of casti) {
    if (part.length === 1) best = Math.min(best, distanceKm(p, { lat: part[0][0], lon: part[0][1] }));
    for (let i = 1; i < part.length; i++) best = Math.min(best, segDistanceKm(p, part[i - 1], part[i]));
  }
  return best;
}

export function pointsDistanceKm(revir, pos) {
  const pts = [...(revir.gps ?? []), ...(revir.stred ? [revir.stred] : [])];
  if (!pts.length) return Infinity;
  return Math.min(...pts.map(p => distanceKm(pos, p)));
}

function bboxDistanceKm(bbox, p) {
  if (!bbox) return Infinity;
  const [s, w, n, e] = bbox;
  const lat = Math.max(s, Math.min(n, p.lat));
  const lon = Math.max(w, Math.min(e, p.lon));
  return distanceKm(p, { lat, lon });
}

export function revirCenter(r) {
  return r.stred ?? r.gps?.[0] ?? null;
}

// Najde revíry kolem polohy. Nejdřív hrubě podle bboxu/bodů, pak přesně podle tvaru.
export async function locate(reviry, pos, limit = 6) {
  const rough = reviry
    .map(r => ({ revir: r, km: Math.min(bboxDistanceKm(r.bbox, pos), pointsDistanceKm(r, pos)) }))
    .filter(x => Number.isFinite(x.km))
    .sort((a, b) => a.km - b.km)
    .slice(0, 25);
  const precise = await Promise.all(
    rough.map(async x => {
      if (!x.revir.geom || x.km > 3) return x;
      const d = await loadDetail(x.revir.id);
      const km = shapeDistanceKm(d.casti, x.revir.geom, pos);
      return { ...x, km: Number.isFinite(km) ? km : pointsDistanceKm(x.revir, pos) };
    }),
  );
  return precise.sort((a, b) => a.km - b.km).slice(0, limit);
}

export function searchReviry(reviry, query) {
  const q = normalize(query);
  if (!q) return [];
  const qDigits = q.replace(/\s/g, '');
  return reviry
    .filter(r => {
      if (/^\d{3,}$/.test(qDigits)) return r.id.includes(qDigits);
      return normalize(`${r.nazev} ${r.mo ?? ''} ${r.svaz ?? ''}`).includes(q);
    })
    .slice(0, 100);
}

export function recentCatches(list, months = 3, now = new Date()) {
  const from = new Date(now);
  from.setMonth(from.getMonth() - months);
  return (list ?? []).filter(u => {
    const d = new Date(u.datum);
    return !Number.isNaN(d.getTime()) && d >= from;
  });
}

export function summarizeCatches(catches) {
  const by = new Map();
  for (const u of catches) {
    const s = by.get(u.druh) ?? { druh: u.druh, pocet: 0, delky: [], nastrahy: new Map(), metody: new Map() };
    s.pocet += 1;
    if (u.delka_cm) s.delky.push(u.delka_cm);
    if (u.nastraha) s.nastrahy.set(u.nastraha, (s.nastrahy.get(u.nastraha) ?? 0) + 1);
    if (u.metoda) s.metody.set(u.metoda, (s.metody.get(u.metoda) ?? 0) + 1);
    by.set(u.druh, s);
  }
  const top = m => [...m.entries()].sort((a, b) => b[1] - a[1]).map(([k]) => k);
  return [...by.values()]
    .map(s => ({ druh: s.druh, pocet: s.pocet, maxDelka: s.delky.length ? Math.max(...s.delky) : null, nastrahy: top(s.nastrahy), metody: top(s.metody) }))
    .sort((a, b) => b.pocet - a.pocet);
}
