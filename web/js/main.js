import { loadAll, nearestReviry, recentCatches, revirCenter, searchReviry, summarizeCatches } from './data.js';
import { isTrout, seasonStatus } from './rules.js';
import { describeCode, fetchWeather, moonLabel, moonPhase } from './weather.js';
import { describeWater, stationForRevir, waterTemperature } from './water.js';
import { recommend } from './recommend.js';

const view = document.getElementById('view');
let DB = null;
let lastPos = null;

const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fmtDate = iso => (iso ? new Date(iso).toLocaleDateString('cs-CZ', { day: 'numeric', month: 'numeric', year: 'numeric' }) : '');
const fmtTime = iso => (iso ? new Date(iso).toLocaleTimeString('cs-CZ', { hour: '2-digit', minute: '2-digit' }) : '');
const num = (v, d = 0) => (v == null || Number.isNaN(v) ? '–' : Number(v).toLocaleString('cs-CZ', { maximumFractionDigits: d, minimumFractionDigits: d }));

function typBadge(r) {
  if (r.typ === 'pstruhovy') return '<span class="badge trout">Pstruhový</span>';
  if (r.typ === 'mimopstruhovy') return '<span class="badge nontrout">Mimopstruhový</span>';
  return '<span class="badge neutral">Typ neuveden</span>';
}

function notice(n) {
  return `<div class="notice ${n.level}">${esc(n.text)}</div>`;
}

function emptyData() {
  return `<div class="card"><h2>Zatím nejsou stažená data revírů</h2>
    <p class="muted">Data o revírech, vysazování a úlovcích stahuje automatická úloha (GitHub Actions) jednou denně.
    Jakmile poprvé proběhne, revíry se tu objeví.</p></div>`;
}

function getPosition() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) return reject(new Error('Prohlížeč nepodporuje polohu.'));
    navigator.geolocation.getCurrentPosition(
      p => resolve({ lat: p.coords.latitude, lon: p.coords.longitude }),
      e => reject(new Error(e.code === 1 ? 'Přístup k poloze byl zamítnut.' : 'Polohu se nepodařilo zjistit.')),
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 },
    );
  });
}

function revirListItem(r, km) {
  return `<li><a href="#/revir/${encodeURIComponent(r.id)}">
    <div class="spread"><strong>${esc(r.nazev)}</strong>${km != null ? `<span class="muted small">${num(km, 1)} km</span>` : ''}</div>
    <div class="row small muted">${typBadge(r)} <span>${esc(r.cislo ?? r.id)}</span> <span>${esc(r.svaz ?? '')}</span></div>
  </a></li>`;
}

// ---------- U vody ----------
async function viewHome() {
  if (!DB.reviry.length) { view.innerHTML = emptyData(); return; }
  view.innerHTML = `<div class="card"><p class="loading">Zjišťuji polohu…</p></div>`;
  try {
    lastPos = await getPosition();
  } catch (e) {
    view.innerHTML = `<div class="card"><h2>Kde jsi?</h2><p>${esc(e.message)}</p>
      <p>Revír můžeš najít i <a href="#/hledat">podle názvu nebo čísla</a> nebo <a href="#/mapa">na mapě</a>.</p>
      <button class="btn" id="retry">Zkusit znovu</button></div>`;
    document.getElementById('retry').onclick = viewHome;
    return;
  }
  const near = nearestReviry(DB.reviry, lastPos, 6);
  if (!near.length) { view.innerHTML = `<div class="card">V okolí jsem žádný revír nenašel.</div>`; return; }
  const [first, ...rest] = near;
  view.innerHTML = `
    <div class="card"><div class="muted small">Nejbližší revír · ${num(first.km, 1)} km</div></div>
    <div id="detail"></div>
    <div class="card"><h2>Další revíry v okolí</h2><ul class="list">${rest.map(x => revirListItem(x.revir, x.km)).join('')}</ul></div>`;
  renderDetail(first.revir, document.getElementById('detail'));
}

// ---------- Detail revíru ----------
async function viewRevir(id) {
  const r = DB.reviry.find(x => x.id === id);
  if (!r) { view.innerHTML = `<div class="card">Revír ${esc(id)} nenalezen.</div>`; return; }
  view.innerHTML = '<div id="detail"></div>';
  renderDetail(r, document.getElementById('detail'));
}

function renderDetail(r, el) {
  const season = seasonStatus(r);
  const catches = recentCatches(DB.ulovky, r.id, 3);
  const summary = summarizeCatches(catches);
  const stocking = (DB.vysazeni[r.id] ?? []).slice().sort((a, b) => (b.datum ?? '').localeCompare(a.datum ?? ''));
  const station = stationForRevir(r, DB.stanice);
  const center = revirCenter(r);

  el.innerHTML = `
    <div class="card">
      <div class="row">${typBadge(r)}${r.rmv ? '<span class="badge warn">Revír místního významu</span>' : ''}</div>
      <div class="big-title">${esc(r.nazev)}</div>
      <div class="muted small">č. ${esc(r.cislo ?? r.id)} · ${esc(r.svaz ?? '')}${r.uzivatel ? ' · ' + esc(r.uzivatel) : ''}</div>
      ${r.vymera_ha || r.delka_km ? `<div class="muted small">${r.delka_km ? num(r.delka_km, 1) + ' km' : ''}${r.delka_km && r.vymera_ha ? ' · ' : ''}${r.vymera_ha ? num(r.vymera_ha, 1) + ' ha' : ''}</div>` : ''}
      ${season.notes.map(notice).join('')}
      <div class="row">
        ${center ? `<a class="btn secondary" target="_blank" rel="noopener" href="https://www.google.com/maps/dir/?api=1&destination=${center.lat},${center.lon}">Navigovat</a>` : ''}
        ${r.url ? `<a class="btn secondary" target="_blank" rel="noopener" href="${esc(r.url)}">Zdroj popisu</a>` : ''}
      </div>
    </div>

    <div class="card"><h2>🎣 Doporučení</h2><div id="reco" class="loading">Počítám podle počasí a úlovků…</div></div>
    <div class="card"><h2>🌦️ Počasí</h2><div id="weather" class="loading">Načítám počasí…</div></div>
    <div class="card"><h2>💧 Stav vody</h2>${renderWater(station)}</div>

    <div class="card"><h2>🐟 Úlovky za poslední 3 měsíce</h2>${renderCatches(summary, catches)}</div>
    <div class="card"><h2>🪣 Vysazování</h2>${renderStocking(stocking)}</div>

    <div class="card"><h2>📋 Popis revíru</h2>
      ${r.popis ? `<p class="pre">${esc(r.popis)}</p>` : '<p class="muted">Popis není k dispozici.</p>'}
      ${r.omezeni ? `<h3>Bližší podmínky / omezení</h3><p class="pre">${esc(r.omezeni)}</p>` : ''}
    </div>`;

  if (!center) {
    document.getElementById('weather').textContent = 'Revír nemá souřadnice – počasí nelze zjistit.';
    finishReco(r, summary, null, station);
    return;
  }
  fetchWeather(center)
    .then(w => {
      document.getElementById('weather').outerHTML = renderWeather(w);
      finishReco(r, summary, w, station);
    })
    .catch(() => {
      document.getElementById('weather').textContent = 'Počasí se nepodařilo načíst (jsi online?).';
      finishReco(r, summary, null, station);
    });
}

function finishReco(r, summary, weather, station) {
  const wt = waterTemperature(station?.s, weather);
  const season = seasonStatus(r);
  const box = document.getElementById('reco');
  if (!box) return;
  box.classList.remove('loading');
  if (!season.open) {
    box.innerHTML = `<p>Revír je teď mimo sezónu – lovit se tu nesmí. Zkus <a href="#/">mimopstruhový revír v okolí</a>.</p>`;
    return;
  }
  const { species, tips } = recommend({ revir: r, catchSummary: summary, weather, water: station?.s, waterTemp: wt });
  box.innerHTML = `
    ${wt ? `<p class="small muted">Teplota vody: <strong>${num(wt.value, 1)} °C</strong>${wt.estimated ? ' (odhad z teploty vzduchu)' : ''}</p>` : ''}
    ${species.map(s => `
      <div class="reco">
        <div class="spread"><span class="species">${esc(s.druh)}</span><div class="bar" title="šance"><i style="width:${Math.round(s.score * 100)}%"></i></div></div>
        <div><strong>Nástraha:</strong> ${esc(s.nastrahy.join(', '))}</div>
        <div><strong>Jak:</strong> ${esc(s.metoda)} · <strong>Kdy:</strong> ${esc(s.kdy)}</div>
        <div class="why">${esc(s.why.join(' · '))}</div>
      </div>`).join('')}
    ${tips.map(t => `<div class="notice warn">${esc(t)}</div>`).join('')}
    <p class="small muted">Doporučení je odhad z úlovků, počasí a ročního období. Vždy dodržuj rybářský řád a bližší podmínky revíru.</p>`;
}

function renderWeather(w) {
  const c = w.current;
  const [ico, txt] = describeCode(c.code);
  const trend = w.pressureTrend24h;
  const trendTxt = trend <= -3 ? '↘ klesá' : trend >= 3 ? '↗ stoupá' : '→ stálý';
  const today = w.days[0];
  return `<div>
    <div class="spread"><span style="font-size:28px">${ico} ${num(c.temp, 0)} °C</span><span class="muted">${esc(txt)}</span></div>
    <div class="stat-grid" style="margin-top:8px">
      <div class="stat"><div class="label">Tlak</div><div class="value">${num(c.pressure, 0)} hPa</div><div class="small muted">${trendTxt} (${trend > 0 ? '+' : ''}${num(trend, 1)} / 24 h)</div></div>
      <div class="stat"><div class="label">Vítr</div><div class="value">${num(c.wind, 1)} m/s</div><div class="small muted">oblačnost ${num(c.cloud)} %</div></div>
      <div class="stat"><div class="label">Slunce</div><div class="value">${fmtTime(today?.sunrise)}–${fmtTime(today?.sunset)}</div></div>
      <div class="stat"><div class="label">Měsíc</div><div class="value" style="font-size:16px">${moonLabel(moonPhase())}</div><div class="small muted">srážky 3 dny: ${num(w.rainLast3d, 1)} mm</div></div>
    </div>
    <h3>Výhled</h3>
    <div class="weather-days">${w.days.map((d, i) => `
      <div><div>${i === 0 ? 'Dnes' : new Date(d.date).toLocaleDateString('cs-CZ', { weekday: 'short' })}</div>
      <div class="ico">${describeCode(d.code)[0]}</div>
      <div class="t">${num(d.tmax)}° / ${num(d.tmin)}°</div>
      <div class="muted">${num(d.rain, 1)} mm</div><div class="muted">${num(d.wind)} m/s</div></div>`).join('')}
    </div>
  </div>`;
}

function renderWater(match) {
  if (!match) return '<p class="muted">V blízkosti revíru není vodoměrná stanice ČHMÚ (u nádrží a menších toků je to běžné).</p>';
  const s = match.s;
  const notes = describeWater(s) ?? [];
  return `
    <div class="muted small">Stanice ${esc(s.nazev)}${s.tok ? ' (' + esc(s.tok) + ')' : ''} · ${num(match.km, 1)} km${match.sameRiver ? '' : ' · jiný tok'}${s.cas ? ' · ' + fmtDate(s.cas) + ' ' + fmtTime(s.cas) : ''}</div>
    <div class="stat-grid" style="margin-top:8px">
      <div class="stat"><div class="label">Vodní stav</div><div class="value">${num(s.stav_cm)} cm</div><div class="small muted">${esc(s.trend ?? '')}</div></div>
      <div class="stat"><div class="label">Průtok</div><div class="value">${num(s.prutok_m3s, 2)} m³/s</div></div>
      ${Number.isFinite(s.teplota_vody) ? `<div class="stat"><div class="label">Teplota vody</div><div class="value">${num(s.teplota_vody, 1)} °C</div></div>` : ''}
      <div class="stat"><div class="label">Povodňový stupeň</div><div class="value">${s.spa ? s.spa + '. SPA' : 'žádný'}</div></div>
    </div>
    ${notes.map(notice).join('')}`;
}

function renderCatches(summary, catches) {
  if (!catches.length) return '<p class="muted">Na rybářských fórech jsem za poslední 3 měsíce z tohoto revíru žádný úlovek nenašel.</p>';
  return `
    <table class="simple"><thead><tr><th>Druh</th><th class="num">Kusů</th><th class="num">Max</th><th>Nástraha</th></tr></thead><tbody>
    ${summary.map(s => `<tr><td>${esc(s.druh)}</td><td class="num">${s.pocet}</td>
      <td class="num">${s.maxDelka ? num(s.maxDelka) + ' cm' : s.maxVaha ? num(s.maxVaha, 1) + ' kg' : '–'}</td>
      <td>${esc(s.nastrahy.slice(0, 2).join(', ') || '–')}</td></tr>`).join('')}
    </tbody></table>
    <details style="margin-top:10px"><summary>Jednotlivé úlovky (${catches.length})</summary>
      <ul class="list small">${catches.slice(0, 50).map(u => `<li style="padding:6px 0">
        <strong>${esc(u.druh)}</strong> ${u.delka_cm ? num(u.delka_cm) + ' cm' : ''} ${u.hmotnost_kg ? num(u.hmotnost_kg, 1) + ' kg' : ''}
        · ${fmtDate(u.datum)}${u.nastraha ? ' · ' + esc(u.nastraha) : ''}
        ${u.url ? ` · <a href="${esc(u.url)}" target="_blank" rel="noopener">${esc(u.zdroj ?? 'zdroj')}</a>` : ''}
      </li>`).join('')}</ul></details>`;
}

function renderStocking(list) {
  if (!list.length) return '<p class="muted">Informace o vysazení nejsou k dispozici.</p>';
  const yearAgo = new Date(); yearAgo.setFullYear(yearAgo.getFullYear() - 1);
  return `<table class="simple"><thead><tr><th>Datum</th><th>Druh</th><th class="num">Množství</th></tr></thead><tbody>
    ${list.slice(0, 30).map(v => `<tr style="${v.datum && new Date(v.datum) < yearAgo ? 'opacity:.6' : ''}">
      <td>${esc(v.datum_text ?? fmtDate(v.datum))}</td><td>${esc(v.druh)}${v.vek ? ' <span class="muted small">(' + esc(v.vek) + ')</span>' : ''}</td>
      <td class="num">${v.mnozstvi != null ? num(v.mnozstvi, v.mnozstvi % 1 ? 1 : 0) + ' ' + esc(v.jednotka ?? '') : '–'}</td></tr>`).join('')}
  </tbody></table>`;
}

// ---------- Mapa ----------
let map = null;
function viewMap() {
  if (!DB.reviry.length) { view.innerHTML = emptyData(); return; }
  view.innerHTML = '<div id="map"></div>';
  map?.remove();
  map = L.map('map').setView(lastPos ? [lastPos.lat, lastPos.lon] : [49.8, 15.5], lastPos ? 11 : 7);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 18, attribution: '&copy; OpenStreetMap',
  }).addTo(map);
  for (const r of DB.reviry) {
    const c = revirCenter(r);
    if (!c) continue;
    L.circleMarker([c.lat, c.lon], {
      radius: 6, weight: 1, color: '#fff', fillOpacity: 0.9,
      fillColor: isTrout(r) ? '#8a3b9e' : '#1f5f4a',
    }).addTo(map).bindPopup(`<a href="#/revir/${encodeURIComponent(r.id)}">${esc(r.nazev)}</a><br>${esc(r.cislo ?? r.id)} · ${isTrout(r) ? 'pstruhový' : 'mimopstruhový'}`);
  }
  if (lastPos) L.circleMarker([lastPos.lat, lastPos.lon], { radius: 8, color: '#1a73e8', fillOpacity: 1 }).addTo(map);
}

// ---------- Hledání ----------
function viewSearch() {
  if (!DB.reviry.length) { view.innerHTML = emptyData(); return; }
  view.innerHTML = `<div class="card"><input type="search" id="q" placeholder="Název, tok, číslo revíru nebo MO…" autofocus>
    <ul class="list" id="results"></ul></div>`;
  const q = document.getElementById('q');
  const out = document.getElementById('results');
  q.value = sessionStorage.getItem('q') ?? '';
  const run = () => {
    try { sessionStorage.setItem('q', q.value); } catch { /* soukromý režim */ }
    const res = searchReviry(DB.reviry, q.value);
    out.innerHTML = res.length ? res.map(r => revirListItem(r)).join('') : q.value ? '<li class="muted" style="padding:10px 0">Nic nenalezeno.</li>' : '';
  };
  q.oninput = run;
  run();
}

// ---------- Router ----------
function route() {
  const h = location.hash || '#/';
  let tab = 'home';
  if (h.startsWith('#/revir/')) { tab = null; viewRevir(decodeURIComponent(h.slice(8))); }
  else if (h === '#/mapa') { tab = 'map'; viewMap(); }
  else if (h === '#/hledat') { tab = 'search'; viewSearch(); }
  else viewHome();
  document.querySelectorAll('.tabbar a').forEach(a => a.classList.toggle('active', a.dataset.tab === tab));
  window.scrollTo(0, 0);
}

async function init() {
  view.innerHTML = '<p class="loading">Načítám data…</p>';
  DB = await loadAll();
  if (DB.meta.generated) document.getElementById('data-age').textContent = 'data: ' + fmtDate(DB.meta.generated);
  window.addEventListener('hashchange', route);
  route();
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('sw.js').catch(() => {});
}

init();
