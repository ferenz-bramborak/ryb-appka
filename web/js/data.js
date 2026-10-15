// Načítání dat generovaných pipeline (scraper/) a pomocné funkce nad nimi.

const cache = new Map();

async function loadJson(name) {
  if (cache.has(name)) return cache.get(name);
  const p = fetch(`data/${name}`, { cache: 'no-cache' })
    .then(r => (r.ok ? r.json() : null))
    .catch(() => null);
  cache.set(name, p);
  return p;
}

export async function loadAll() {
  const [reviry, vysazeni, ulovky, voda, meta] = await Promise.all([
    loadJson('reviry.json'),
    loadJson('vysazeni.json'),
    loadJson('ulovky.json'),
    loadJson('voda.json'),
    loadJson('meta.json'),
  ]);
  return {
    reviry: reviry?.reviry ?? [],
    vysazeni: vysazeni?.vysazeni ?? {},
    ulovky: ulovky?.ulovky ?? {},
    stanice: voda?.stanice ?? [],
    meta: meta ?? {},
  };
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
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

// Revír má v `gps` seznam bodů (začátek, konec, případně body podél toku).
export function revirDistanceKm(revir, pos) {
  const pts = revir.gps ?? [];
  if (!pts.length) return Infinity;
  return Math.min(...pts.map(p => distanceKm(pos, p)));
}

export function revirCenter(revir) {
  const pts = revir.gps ?? [];
  if (!pts.length) return null;
  return {
    lat: pts.reduce((s, p) => s + p.lat, 0) / pts.length,
    lon: pts.reduce((s, p) => s + p.lon, 0) / pts.length,
  };
}

export function nearestReviry(reviry, pos, limit = 5) {
  return reviry
    .map(r => ({ revir: r, km: revirDistanceKm(r, pos) }))
    .filter(x => Number.isFinite(x.km))
    .sort((a, b) => a.km - b.km)
    .slice(0, limit);
}

export function searchReviry(reviry, query) {
  const q = normalize(query);
  if (!q) return [];
  const qDigits = q.replace(/\s/g, '');
  return reviry
    .filter(r => {
      if (/^\d+$/.test(qDigits) && (r.id ?? '').includes(qDigits)) return true;
      return normalize(`${r.nazev} ${r.tok ?? ''} ${r.uzivatel ?? ''} ${r.mo ?? ''}`).includes(q);
    })
    .slice(0, 100);
}

// Úlovky za posledních `months` měsíců.
export function recentCatches(ulovky, revirId, months = 3, now = new Date()) {
  const from = new Date(now);
  from.setMonth(from.getMonth() - months);
  return (ulovky[revirId] ?? [])
    .filter(u => {
      const d = new Date(u.datum);
      return !Number.isNaN(d.getTime()) && d >= from && d <= now;
    })
    .sort((a, b) => b.datum.localeCompare(a.datum));
}

export function summarizeCatches(catches) {
  const bySpecies = new Map();
  for (const u of catches) {
    const key = u.druh || 'neurčeno';
    const s = bySpecies.get(key) ?? { druh: key, pocet: 0, delky: [], vahy: [], nastrahy: new Map(), metody: new Map() };
    s.pocet += 1;
    if (u.delka_cm) s.delky.push(u.delka_cm);
    if (u.hmotnost_kg) s.vahy.push(u.hmotnost_kg);
    if (u.nastraha) s.nastrahy.set(u.nastraha, (s.nastrahy.get(u.nastraha) ?? 0) + 1);
    if (u.metoda) s.metody.set(u.metoda, (s.metody.get(u.metoda) ?? 0) + 1);
    bySpecies.set(key, s);
  }
  return [...bySpecies.values()]
    .map(s => ({
      druh: s.druh,
      pocet: s.pocet,
      maxDelka: s.delky.length ? Math.max(...s.delky) : null,
      maxVaha: s.vahy.length ? Math.max(...s.vahy) : null,
      nastrahy: [...s.nastrahy.entries()].sort((a, b) => b[1] - a[1]).map(([k]) => k),
      metody: [...s.metody.entries()].sort((a, b) => b[1] - a[1]).map(([k]) => k),
    }))
    .sort((a, b) => b.pocet - a.pocet);
}
