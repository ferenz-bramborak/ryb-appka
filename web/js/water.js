// Přiřazení vodoměrné stanice ČHMÚ k revíru a interpretace stavu vody.
import { distanceKm, normalize, pointsDistanceKm, revirCenter } from './data.js';

// Preferuje stanici na stejném toku (do 40 km), jinak nejbližší stanici do 8 km.
export function stationForRevir(revir, stanice) {
  const center = revirCenter(revir);
  if (!center || !stanice.length) return null;
  const tok = normalize(revir.tok);
  const scored = stanice
    .filter(s => Number.isFinite(s.lat) && Number.isFinite(s.lon))
    .map(s => ({ s, km: Math.min(pointsDistanceKm(revir, s), distanceKm(center, s)) }));
  const sameRiver = tok
    ? scored.filter(x => normalize(x.s.tok) === tok && x.km <= 40).sort((a, b) => a.km - b.km)
    : [];
  if (sameRiver.length) return { ...sameRiver[0], sameRiver: true };
  const near = scored.filter(x => x.km <= 8).sort((a, b) => a.km - b.km);
  return near.length ? { ...near[0], sameRiver: false } : null;
}

export function describeWater(st) {
  if (!st) return null;
  const notes = [];
  if (st.spa >= 1) {
    notes.push({ level: 'bad', text: `Vyhlášen ${st.spa}. stupeň povodňové aktivity – zvýšená opatrnost, voda kalná a rychlá.` });
  }
  if (st.trend === 'roste') notes.push({ level: 'warn', text: 'Hladina stoupá – voda se kalí, ryby se stahují ke břehům a do klidnějších míst.' });
  if (st.trend === 'klesá') notes.push({ level: 'good', text: 'Hladina klesá a čistí se – po zvýšené vodě často dobrá aktivita ryb.' });
  return notes;
}

// Teplota vody: z měření stanice, jinak hrubý odhad z průměrné teploty vzduchu.
export function waterTemperature(st, weather) {
  if (st && Number.isFinite(st.teplota_vody)) return { value: st.teplota_vody, estimated: false };
  if (weather?.airMean5d != null) {
    return { value: Math.max(0.5, 0.8 * weather.airMean5d + 2), estimated: true };
  }
  return null;
}
