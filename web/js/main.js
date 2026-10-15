import { distanceKm, loadDetail, loadIndex, loadNovinky, locate, recentCatches, revirCenter, searchReviry, summarizeCatches } from './data.js';
import { isTrout, seasonStatus } from './rules.js';
import { describeCode, fetchWeather, moonLabel, moonPhase } from './weather.js';
import { describeWater, stationForRevir, waterTemperature } from './water.js';
import { recommend } from './recommend.js';

const view = document.getElementById('view');
let DB = null;
let lastPos = null;
let renderToken = 0;

const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fmtDate = iso => (iso ? new Date(iso).toLocaleDateString('cs-CZ', { day: 'numeric', month: 'numeric', year: 'numeric' }) : '');
const fmtTime = iso => (iso ? new Date(iso).toLocaleTimeString('cs-CZ', { hour: '2-digit', minute: '2-digit' }) : '');
const num = (v, d = 0) => (v == null || Number.isNaN(v) ? '–' : Number(v).toLocaleString('cs-CZ', { maximumFractionDigits: d, minimumFractionDigits: d }));
const safeUrl = u => (/^https?:\/\//i.test(u ?? '') ? u : u ? `https://${u}` : '');
const cap = s => (s ? s[0].toUpperCase() + s.slice(1) : s);

function typBadge(r) {
  if (r.typ === 'pstruhovy') return '<span class="badge trout">Pstruhový</span>';
  if (r.typ === 'mimopstruhovy') return '<span class="badge nontrout">Mimopstruhový</span>';
  return '<span class="badge neutral">Typ neuveden</span>';
}
const notice = n => `<div class="notice ${n.level}">${esc(n.text)}</div>`;

function emptyData() {
  return `<div class="card"><h2>Zatím nejsou stažená data revírů</h2>
    <p class="muted">Data stahuje automatická úloha (GitHub Actions) jednou denně. Jakmile poprvé proběhne, revíry se tu objeví.</p></div>`;
}

function getPosition() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) return reject(new Error('Prohlížeč nepodporuje polohu.'));
    navigator.geolocation.getCurrentPosition(
      p => resolve({ lat: p.coords.latitude, lon: p.coords.longitude }),
      e => reject(new Error(e.code === 1 ? 'Přístup k poloze byl zamítnut. Povol ho v nastavení prohlížeče.' : 'Polohu se nepodařilo zjistit.')),
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 },
    );
  });
}

function revirListItem(r, km) {
  return `<li><a href="#/revir/${encodeURIComponent(r.id)}">
    <div class="spread"><strong>${esc(r.nazev)}</strong>${km != null ? `<span class="muted small">${km < 0.05 ? 'tady' : num(km, 1) + ' km'}</span>` : ''}</div>
    <div class="row small muted">${typBadge(r)} <span>${esc(r.cislo ?? r.id)}</span> <span>${esc(r.svaz ?? '')}</span></div>
  </a></li>`;
}

// ---------- U vody ----------
async function viewHome() {
  if (!DB.reviry.length) { view.innerHTML = emptyData(); return; }
  const token = ++renderToken;
  view.innerHTML = `<div class="card"><p class="loading">Zjišťuji polohu…</p></div>`;
  try {
    lastPos = await getPosition();
  } catch (e) {
    if (token !== renderToken) return;
    view.innerHTML = `<div class="card"><h2>Kde jsi?</h2><p>${esc(e.message)}</p>
      <p>Revír najdeš i <a href="#/hledat">podle názvu nebo čísla</a> nebo <a href="#/mapa">na mapě</a>.</p>
      <button class="btn" id="retry">Zkusit znovu</button></div>`;
    document.getElementById('retry').onclick = viewHome;
    return;
  }
  if (token !== renderToken) return;
  view.innerHTML = `<div class="card"><p class="loading">Hledám revír…</p></div>`;
  const near = await locate(DB.reviry, lastPos, 7);
  if (token !== renderToken) return;
  if (!near.length) { view.innerHTML = `<div class="card">V okolí jsem žádný revír nenašel.</div>`; return; }
  const [first, ...rest] = near;
  const here = first.km <= 0.3;
  view.innerHTML = `
    <div class="card"><div class="${here ? '' : 'muted '}small">${here ? '📍 <strong>Jsi na revíru</strong>' : `Nejbližší revír · ${num(first.km, 1)} km`}</div>
      ${!here && first.km > 1 ? '<div class="small muted">Nejsi přímo u vody – ukazuji nejbližší revír.</div>' : ''}</div>
    <div id="detail"></div>
    <div class="card"><h2>Další revíry v okolí</h2><ul class="list">${rest.map(x => revirListItem(x.revir, x.km)).join('')}</ul></div>`;
  renderDetail(first.revir, document.getElementById('detail'), token);
}

// ---------- Detail revíru ----------
function viewRevir(id) {
  const r = DB.reviry.find(x => x.id === id);
  if (!r) { view.innerHTML = `<div class="card">Revír ${esc(id)} nenalezen.</div>`; return; }
  view.innerHTML = '<div id="detail"></div>';
  renderDetail(r, document.getElementById('detail'), ++renderToken);
}

async function renderDetail(r, el, token) {
  el.innerHTML = `<div class="card"><div class="big-title">${esc(r.nazev)}</div><p class="loading">Načítám detail…</p></div>`;
  const d = await loadDetail(r.id);
  if (token !== renderToken) return;
  const status = seasonStatus(r, d);
  const catches = recentCatches(d.ulovky, 3);
  const tokCatches = recentCatches(d.ulovky_tok, 3);
  const summary = summarizeCatches(catches);
  const station = stationForRevir(r, DB.stanice);
  const center = revirCenter(r);

  el.innerHTML = `
    <div class="card">
      <div class="row">${typBadge(r)}${r.rmv ? '<span class="badge warn">Revír místního významu</span>' : ''}${r.lodi ? '<span class="badge neutral">lov z lodě</span>' : ''}${r.nonstop ? '<span class="badge neutral">nonstop</span>' : ''}</div>
      <div class="big-title">${esc(r.nazev)}</div>
      <div class="muted small">č. ${esc(r.cislo ?? r.id)} · ${esc(r.svaz ?? '')}${r.mo ? ' · MO ' + esc(r.mo) : ''}</div>
      ${r.delka_km || r.vymera_ha ? `<div class="muted small">${[r.delka_km ? num(r.delka_km, 1) + ' km' : '', r.vymera_ha ? num(r.vymera_ha, 1) + ' ha' : ''].filter(Boolean).join(' · ')}</div>` : ''}
      ${status.notes.map(notice).join('')}
      ${status.zdroj === 'svaz' && status.platneK ? `<div class="small muted">Pravidla podle ČRS platná k ${fmtDate(status.platneK)}.</div>` : ''}
      <div class="row" style="margin-top:8px">
        ${center ? `<a class="btn secondary" target="_blank" rel="noopener" href="https://www.google.com/maps/dir/?api=1&destination=${center.lat},${center.lon}">Navigovat</a>` : ''}
        ${d.url ? `<a class="btn secondary" target="_blank" rel="noopener" href="${esc(d.url)}">Karta revíru u svazu</a>` : ''}
      </div>
    </div>

    <div class="card"><h2>🎣 Doporučení</h2><div id="reco" class="loading">Počítám podle počasí a úlovků…</div></div>
    <div class="card"><h2>🌦️ Počasí</h2><div id="weather" class="loading">Načítám počasí…</div></div>
    <div class="card"><h2>💧 Stav vody</h2>${renderWater(station)}</div>
    <div class="card"><h2>🐟 Co se tu chytá</h2>${renderStatistika(d.statistika)}${renderCatches(catches, tokCatches, r)}</div>
    <div class="card"><h2>🪣 Vysazování</h2>${renderStocking(d.vysazeni)}</div>
    ${renderRevirNovinky(d)}
    ${renderPravidla(d.pravidla)}
    <div class="card"><h2>📋 Popis revíru</h2>
      ${d.popis ? `<p class="pre">${esc(d.popis)}</p>` : '<p class="muted">Popis není k dispozici.</p>'}
    </div>
    ${renderKontakty(d.kontakty)}`;

  const finish = weather => {
    if (token !== renderToken) return;
    finishReco(r, status, summary, d.statistika, weather, station);
  };
  if (!center) {
    document.getElementById('weather').textContent = 'Revír nemá souřadnice – počasí nelze zjistit.';
    finish(null);
    return;
  }
  fetchWeather(center)
    .then(w => {
      if (token !== renderToken) return;
      document.getElementById('weather').outerHTML = renderWeather(w);
      finish(w);
    })
    .catch(() => {
      const el2 = document.getElementById('weather');
      if (el2) el2.textContent = 'Počasí se nepodařilo načíst (jsi online?).';
      finish(null);
    });
}

function finishReco(r, status, summary, statistika, weather, station) {
  const box = document.getElementById('reco');
  if (!box) return;
  box.classList.remove('loading');
  if (!status.open) {
    box.innerHTML = '<p>Na revíru se teď lovit nesmí. Zkus <a href="#/">jiný revír v okolí</a>.</p>';
    return;
  }
  const wt = waterTemperature(station?.s, weather);
  const { species, tips } = recommend({ revir: r, status, catchSummary: summary, statistika, weather, water: station?.s, waterTemp: wt });
  box.innerHTML = `
    ${wt ? `<p class="small muted">Teplota vody: <strong>${num(wt.value, 1)} °C</strong>${wt.estimated ? ' (odhad z teploty vzduchu)' : ` (stanice ${esc(station.s.nazev)})`}</p>` : ''}
    ${species.map(s => `
      <div class="reco">
        <div class="spread"><span class="species">${esc(cap(s.druh))}</span><div class="bar" title="šance"><i style="width:${Math.round(s.score * 100)}%"></i></div></div>
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
    <div class="muted small">Stanice ${s.url ? `<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.nazev)}</a>` : esc(s.nazev)}${s.tok ? ' (' + esc(s.tok) + ')' : ''} · ${num(match.km, 1)} km${match.sameRiver ? '' : ' · jiný tok'}${s.cas ? ' · ' + fmtDate(s.cas) + ' ' + fmtTime(s.cas) : ''}</div>
    <div class="stat-grid" style="margin-top:8px">
      <div class="stat"><div class="label">Vodní stav</div><div class="value">${num(s.stav_cm)} cm</div><div class="small muted">${esc(s.trend ?? '')}</div></div>
      <div class="stat"><div class="label">Průtok</div><div class="value">${num(s.prutok_m3s, 2)} m³/s</div></div>
      ${Number.isFinite(s.teplota_vody) ? `<div class="stat"><div class="label">Teplota vody</div><div class="value">${num(s.teplota_vody, 1)} °C</div></div>` : ''}
      <div class="stat"><div class="label">Povodňový stupeň</div><div class="value">${s.spa ? s.spa + '. SPA' : 'žádný'}</div></div>
    </div>
    ${notes.map(notice).join('')}`;
}

function renderStatistika(st) {
  if (!st?.druhy?.length) return '';
  const rok = st.roky[0].rok;
  const prev = st.roky[1]?.rok;
  const total = st.roky[0];
  return `
    <h3>Oficiální úlovky z povolenek (${rok})</h3>
    <table class="simple"><thead><tr><th>Druh</th><th class="num">${rok} ks</th><th class="num">kg</th>${prev ? `<th class="num">${prev} ks</th>` : ''}</tr></thead><tbody>
    ${st.druhy.slice(0, 10).map(d => {
      const a = d.roky.find(x => x.rok === rok);
      const b = prev ? d.roky.find(x => x.rok === prev) : null;
      return `<tr><td>${esc(cap(d.druh))}</td><td class="num">${a ? num(a.ks) : '–'}</td><td class="num">${a ? num(a.kg, 0) : '–'}</td>${prev ? `<td class="num">${b ? num(b.ks) : '–'}</td>` : ''}</tr>`;
    }).join('')}
    </tbody></table>
    <p class="small muted">Celkem ${num(total.ks)} ks / ${num(total.kg, 0)} kg ponechaných ryb. Zdroj: statistika úlovků ČRS.</p>`;
}

function catchItem(u) {
  return `<li style="padding:6px 0">
    <strong>${esc(cap(u.druh))}</strong>${u.delka_cm ? ' ' + num(u.delka_cm) + ' cm' : ''}${u.hmotnost_kg ? ' ' + num(u.hmotnost_kg, 1) + ' kg' : ''}
    · ${fmtDate(u.datum)}${u.nastraha ? ' · ' + esc(u.nastraha) : ''}${u.metoda ? ' · ' + esc(u.metoda) : ''}
    ${u.revir_text ? `<div class="small muted">revír: „${esc(u.revir_text)}“</div>` : ''}
    ${u.text ? `<div class="small muted">${esc(u.text.slice(0, 160))}${u.text.length > 160 ? '…' : ''}</div>` : ''}
    ${u.url ? `<a class="small" href="${esc(u.url)}" target="_blank" rel="noopener">${esc(u.zdroj ?? 'zdroj')}</a>` : ''}
  </li>`;
}

function renderCatches(catches, tokCatches, r) {
  const head = '<h3>Úlovky z fór za poslední 3 měsíce</h3>';
  if (!catches.length && !tokCatches.length) {
    return `${head}<p class="muted small">Na mrk.cz ani chytej.cz jsem za poslední 3 měsíce úlovek z tohoto revíru nenašel (rybáři často revír neuvádějí).</p>`;
  }
  const sum = summarizeCatches(catches);
  return `${head}
    ${catches.length ? `<p class="small">Z tohoto revíru: ${sum.map(s => `${esc(s.druh)} ${s.pocet}×`).join(', ')}</p>
      <ul class="list small">${catches.map(catchItem).join('')}</ul>` : ''}
    ${tokCatches.length ? `<details style="margin-top:8px"><summary>Z toku ${esc(r.tok)} bez upřesnění úseku (${tokCatches.length})</summary>
      <ul class="list small">${tokCatches.map(catchItem).join('')}</ul></details>` : ''}
    <p class="small muted">Druh je rozpoznán z textu zápisu – může jít i o zmínku, ne jen o úlovek.</p>`;
}

function renderStocking(list) {
  if (!list?.length) return '<p class="muted">Za poslední rok jsem o vysazení na tento revír nenašel zprávu. Týdenní hlášení zveřejňuje jen část svazů.</p>';
  return `<table class="simple"><thead><tr><th>Datum</th><th>Druh</th><th class="num">Množství</th></tr></thead><tbody>
    ${list.slice(0, 25).map(v => `<tr>
      <td>${v.url ? `<a href="${esc(v.url)}" target="_blank" rel="noopener">${fmtDate(v.datum)}</a>` : fmtDate(v.datum)}</td>
      <td>${esc(cap(v.druh))}${v.kategorie ? ` <span class="muted small">${esc(v.kategorie)}</span>` : ''}</td>
      <td class="num">${v.mnozstvi != null ? num(v.mnozstvi) + ' ' + esc(v.jednotka ?? '') : '–'}</td></tr>`).join('')}
  </tbody></table>
  ${list.some(v => v.mo) ? '<p class="small muted">Hlášení svazu uvádí množství pro celou MO – ryby mohly jít i do jiného revíru téže organizace.</p>' : ''}`;
}

function renderPravidla(p) {
  if (!p) return '';
  const yesno = ok => (ok ? '<span class="badge good">povoleno</span>' : '<span class="badge bad">zakázáno</span>');
  return `<div class="card"><h2>📏 Pravidla lovu</h2>
    ${p.doba_lovu ? `<p><strong>Denní doba lovu:</strong> ${esc(p.doba_lovu)}</p>` : ''}
    ${p.zpusoby?.length ? `<h3>Způsoby lovu</h3><table class="simple"><tbody>${p.zpusoby.map(z => `<tr><td>${esc(z.nazev)}</td><td class="num">${yesno(z.povoleno)}</td></tr>`).join('')}</tbody></table>` : ''}
    ${p.podminky?.length ? `<h3>Podmínky</h3><table class="simple"><tbody>${p.podminky.map(z => `<tr><td>${esc(cap(z.nazev))}</td><td class="num">${yesno(z.povoleno)}</td></tr>`).join('')}</tbody></table>` : ''}
    ${p.druhy?.length ? `<details style="margin-top:10px"><summary>Lovné míry a hájení</summary>
      <table class="simple"><thead><tr><th>Druh</th><th>Dnes</th><th class="num">Míra</th></tr></thead><tbody>
      ${p.druhy.map(d => `<tr><td>${esc(d.druh)}</td><td>${d.hajen ? '<span class="badge bad">nelze ponechat</span>' : '<span class="badge good">lze</span>'}</td>
        <td class="num">${d.mira ? d.mira + ' cm' : '–'}${d.horni_mira ? ' – ' + d.horni_mira + ' cm' : ''}</td></tr>`).join('')}
      </tbody></table></details>` : ''}
    ${p.limity?.length ? `<details style="margin-top:10px"><summary>Limity úlovků</summary><p class="pre small">${esc(p.limity.join('\n\n'))}</p></details>` : ''}
    ${p.vybava?.length ? `<details style="margin-top:10px"><summary>Povinná výbava</summary><ul class="small">${p.vybava.map(v => `<li>${esc(v)}</li>`).join('')}</ul></details>` : ''}
  </div>`;
}

function renderKontakty(k) {
  if (!k || (!k.mo && !k.uzivatel)) return '';
  const one = (title, c) => (c ? `<div style="margin-bottom:8px"><div class="small muted">${title}</div><strong>${esc(c.nazev)}</strong>
    ${c.tel ? `<div><a href="tel:${esc(c.tel.replace(/\s/g, ''))}">${esc(c.tel)}</a></div>` : ''}
    ${c.email ? `<div><a href="mailto:${esc(c.email)}">${esc(c.email)}</a></div>` : ''}
    ${c.web ? `<div><a href="${esc(safeUrl(c.web))}" target="_blank" rel="noopener">${esc(c.web)}</a></div>` : ''}
    ${c.adresa ? `<div class="small muted">${esc(c.adresa)}</div>` : ''}</div>` : '');
  return `<div class="card"><h2>☎️ Kontakty</h2>${one('Hospodařící organizace', k.mo)}${one('Uživatel revíru', k.uzivatel)}</div>`;
}


// ---------- Novinky ----------
const TYPY = {
  vysazeni: ['🪣', 'Vysazení', 'good'],
  zakaz: ['⛔', 'Zákaz / omezení', 'bad'],
  uhyn: ['☠️', 'Úhyn / škody', 'bad'],
  zavody: ['🏆', 'Závody', 'neutral'],
  info: ['ℹ️', 'Zpráva', 'neutral'],
};
const typBadgeNews = t => { const [i, n, c] = TYPY[t] ?? TYPY.info; return `<span class="badge ${c}">${i} ${n}</span>`; };

const store = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch { /* soukromý režim */ } },
};

async function updateNewsBadge() {
  const feed = await loadNovinky();
  const seen = store.get('novinky-videno') ?? '';
  const n = feed.filter(z => z.datum > seen).length;
  const b = document.getElementById('news-badge');
  if (!b) return;
  b.hidden = !n || !seen;  // při úplně první návštěvě nestrašit číslem
  b.textContent = n > 99 ? '99+' : String(n);
}

function vysazeniTable(rows) {
  if (!rows?.length) return '';
  const row = v => `<tr>
    <td>${esc(cap(v.druh))}${v.kategorie ? ` <span class="muted">${esc(v.kategorie)}</span>` : ''}</td>
    <td>${esc(v.mo ? 'MO ' + v.mo : v.revir_text ?? '')}</td>
    <td class="num nowrap">${v.mnozstvi != null ? num(v.mnozstvi) + '&nbsp;' + esc(v.jednotka ?? '') : ''}</td></tr>`;
  const head = rows.slice(0, 6), rest = rows.slice(6);
  return `<table class="simple small" style="margin-top:6px"><tbody>${head.map(row).join('')}</tbody></table>
    ${rest.length ? `<details><summary class="small">Celý rozpis (${rows.length} položek)</summary>
      <table class="simple small"><tbody>${rest.map(row).join('')}</tbody></table></details>` : ''}`;
}

function newsItem(z, seen) {
  const revs = z.reviry ?? [];
  return `<div class="card news-item ${seen && z.datum > seen ? 'new' : ''}">
    <div class="spread"><span class="small muted">${fmtDate(z.datum)}</span>${typBadgeNews(z.typ)}</div>
    <h3>${z.url ? `<a href="${esc(z.url)}" target="_blank" rel="noopener">${esc(z.titulek ?? 'Zpráva')}</a>` : esc(z.titulek ?? 'Zpráva')}</h3>
    <div class="small muted">${esc(z.zdroj ?? '')}${z.mo && !String(z.zdroj ?? '').includes(z.mo) ? ' · MO ' + esc(z.mo) : ''}</div>
    ${z.text ? `<p class="small" style="margin:6px 0">${esc(z.text.slice(0, 260))}${z.text.length > 260 ? '…' : ''}</p>` : ''}
    ${vysazeniTable(z.vysazeni)}
    ${revs.length ? `<div class="revir-chips">${revs.slice(0, 10).map(r => `<a href="#/revir/${encodeURIComponent(r.id)}">${esc(r.nazev)}</a>`).join('')}${revs.length > 10 ? `<span class="small muted">+${revs.length - 10} revírů</span>` : ''}</div>` : ''}
  </div>`;
}

async function viewNovinky() {
  view.innerHTML = '<p class="loading">Načítám novinky…</p>';
  const feed = await loadNovinky();
  const seen = store.get('novinky-videno') ?? '';
  let filtr = store.get('novinky-filtr') ?? 'vse';
  const byId = new Map(DB.reviry.map(r => [r.id, r]));
  const poblizKm = 30;
  const nearby = z => lastPos && (z.reviry ?? []).some(r => {
    const c = revirCenter(byId.get(r.id) ?? {});
    return c && distanceKm(lastPos, c) <= poblizKm;
  });
  const FILTRY = [
    ['vse', 'Vše', () => true],
    ['vysazeni', '🪣 Vysazení', z => z.typ === 'vysazeni'],
    ['zakazy', '⛔ Zákazy a úhyny', z => z.typ === 'zakaz' || z.typ === 'uhyn'],
    ['pobliz', `📍 Do ${poblizKm} km`, nearby],
  ];
  const render = () => {
    const f = FILTRY.find(x => x[0] === filtr) ?? FILTRY[0];
    const items = feed.filter(f[2]);
    view.innerHTML = `
      <div class="chips">${FILTRY.map(([k, n]) => `<button class="chip ${k === filtr ? 'active' : ''}" data-f="${k}">${n}</button>`).join('')}</div>
      ${filtr === 'pobliz' && !lastPos ? '<div class="card small">Pro novinky z okolí otevři nejdřív záložku „U vody“, aby appka znala tvou polohu.</div>' : ''}
      ${items.length ? items.map(z => newsItem(z, seen)).join('') : '<div class="card muted">Za poslední měsíc tu nic není.</div>'}
      <p class="small muted">Zprávy za poslední měsíc: hlášení svazů o vysazování, novinky místních organizací, Bleskovky a diskuse z mrk.cz.</p>`;
    view.querySelectorAll('.chip').forEach(b => { b.onclick = () => { filtr = b.dataset.f; store.set('novinky-filtr', filtr); render(); }; });
  };
  render();
  if (feed[0]) store.set('novinky-videno', feed[0].datum);
  updateNewsBadge();
}

function renderRevirNovinky(d) {
  const items = [...(d.novinky ?? []), ...(d.diskuse ?? []).map(x => ({ datum: x.datum, typ: 'info', titulek: x.text, zdroj: `mrk.cz – diskuse (${x.autor})`, url: d.mrk }))]
    .sort((a, b) => b.datum.localeCompare(a.datum));
  if (!items.length) return '';
  return `<div class="card"><h2>📰 Novinky z revíru</h2><ul class="list small">${items.slice(0, 10).map(z => `<li style="padding:6px 0">
    <div class="spread"><span class="muted">${fmtDate(z.datum)}</span>${typBadgeNews(z.typ)}</div>
    <div>${z.url ? `<a href="${esc(z.url)}" target="_blank" rel="noopener">${esc(z.titulek.slice(0, 200))}</a>` : esc(z.titulek.slice(0, 200))}</div>
    <div class="muted">${esc(z.zdroj ?? '')}</div></li>`).join('')}</ul></div>`;
}

// ---------- Mapa ----------
let map = null;
const shapeLayers = new Map();
function viewMap() {
  if (!DB.reviry.length) { view.innerHTML = emptyData(); return; }
  if (typeof L === 'undefined') { view.innerHTML = '<div class="card">Mapu se nepodařilo načíst (jsi online?).</div>'; return; }
  view.innerHTML = '<div id="map"></div>';
  map?.remove();
  shapeLayers.clear();
  map = L.map('map', { preferCanvas: true }).setView(lastPos ? [lastPos.lat, lastPos.lon] : [49.8, 15.5], lastPos ? 12 : 7);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 18, attribution: '&copy; OpenStreetMap' }).addTo(map);
  const color = r => (isTrout(r) ? '#8a3b9e' : '#1f5f4a');
  const markers = [];
  for (const r of DB.reviry) {
    const c = revirCenter(r);
    if (!c) continue;
    markers.push(L.circleMarker([c.lat, c.lon], { radius: 4, weight: 1, color: '#fff', fillOpacity: 0.9, fillColor: color(r) })
      .addTo(map)
      .bindPopup(`<a href="#/revir/${encodeURIComponent(r.id)}">${esc(r.nazev)}</a><br>${esc(r.cislo ?? r.id)} · ${isTrout(r) ? 'pstruhový' : 'mimopstruhový'}`));
  }
  const resize = () => { const z = map.getZoom(); markers.forEach(m => m.setRadius(z < 9 ? 3 : z < 12 ? 5 : 7)); };
  map.on('zoomend', resize);
  resize();
  const showMe = pos => L.circleMarker([pos.lat, pos.lon], { radius: 8, color: '#1a73e8', fillOpacity: 1 }).addTo(map).bindPopup('Tady jsi');
  if (lastPos) showMe(lastPos);
  else getPosition().then(pos => { lastPos = pos; if (!map) return; showMe(pos); map.setView([pos.lat, pos.lon], 12); }).catch(() => {});

  // Při přiblížení dokreslí tvary revírů ve výřezu.
  const drawShapes = async () => {
    if (map.getZoom() < 12) return;
    const b = map.getBounds();
    const visible = DB.reviry.filter(r => r.bbox && r.bbox[2] >= b.getSouth() && r.bbox[0] <= b.getNorth() && r.bbox[3] >= b.getWest() && r.bbox[1] <= b.getEast());
    for (const r of visible.slice(0, 60)) {
      if (shapeLayers.has(r.id)) continue;
      shapeLayers.set(r.id, null);
      const d = await loadDetail(r.id);
      if (!d.casti || !map) continue;
      const style = { color: color(r), weight: r.geom === 'linie' ? 4 : 2, fillOpacity: 0.15 };
      const layer = r.geom === 'polygon' ? L.polygon(d.casti, style) : L.polyline(d.casti, style);
      layer.addTo(map).bindPopup(`<a href="#/revir/${encodeURIComponent(r.id)}">${esc(r.nazev)}</a><br>${esc(r.cislo ?? r.id)}`);
      shapeLayers.set(r.id, layer);
    }
  };
  map.on('moveend', drawShapes);
  drawShapes();
}

// ---------- Hledání ----------
function viewSearch() {
  if (!DB.reviry.length) { view.innerHTML = emptyData(); return; }
  view.innerHTML = `<div class="card"><input type="search" id="q" placeholder="Název, číslo revíru, MO nebo svaz…">
    <ul class="list" id="results"></ul></div>`;
  const q = document.getElementById('q');
  const out = document.getElementById('results');
  try { q.value = sessionStorage.getItem('q') ?? ''; } catch { /* soukromý režim */ }
  const run = () => {
    try { sessionStorage.setItem('q', q.value); } catch { /* soukromý režim */ }
    const res = searchReviry(DB.reviry, q.value);
    out.innerHTML = res.length ? res.map(r => revirListItem(r)).join('') : q.value ? '<li class="muted" style="padding:10px 0">Nic nenalezeno.</li>' : '';
  };
  q.oninput = run;
  run();
  q.focus();
}

// ---------- Router ----------
function route() {
  const h = location.hash || '#/';
  let tab = 'home';
  if (h.startsWith('#/revir/')) { tab = null; viewRevir(decodeURIComponent(h.slice(8))); }
  else if (h === '#/mapa') { tab = 'map'; renderToken++; viewMap(); }
  else if (h === '#/hledat') { tab = 'search'; renderToken++; viewSearch(); }
  else if (h === '#/novinky') { tab = 'news'; renderToken++; viewNovinky(); }
  else viewHome();
  document.querySelectorAll('.tabbar a').forEach(a => a.classList.toggle('active', a.dataset.tab === tab));
  window.scrollTo(0, 0);
}

async function init() {
  view.innerHTML = '<p class="loading">Načítám data…</p>';
  DB = await loadIndex();
  if (DB.meta.generated) document.getElementById('data-age').textContent = 'data: ' + fmtDate(DB.meta.generated);
  window.addEventListener('hashchange', route);
  route();
  updateNewsBadge();
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('sw.js').catch(() => {});
}

init();
