// Počasí z Open-Meteo (zdarma, bez klíče, povoluje CORS – volá se přímo z mobilu).

const WMO = {
  0: ['☀️', 'jasno'], 1: ['🌤️', 'skoro jasno'], 2: ['⛅', 'polojasno'], 3: ['☁️', 'zataženo'],
  45: ['🌫️', 'mlha'], 48: ['🌫️', 'námraza'],
  51: ['🌦️', 'mrholení'], 53: ['🌦️', 'mrholení'], 55: ['🌦️', 'mrholení'],
  61: ['🌧️', 'slabý déšť'], 63: ['🌧️', 'déšť'], 65: ['🌧️', 'silný déšť'],
  66: ['🌧️', 'mrznoucí déšť'], 67: ['🌧️', 'mrznoucí déšť'],
  71: ['🌨️', 'slabé sněžení'], 73: ['🌨️', 'sněžení'], 75: ['❄️', 'silné sněžení'], 77: ['🌨️', 'sněhová zrna'],
  80: ['🌦️', 'přeháňky'], 81: ['🌧️', 'přeháňky'], 82: ['⛈️', 'silné přeháňky'],
  85: ['🌨️', 'sněhové přeháňky'], 86: ['🌨️', 'sněhové přeháňky'],
  95: ['⛈️', 'bouřka'], 96: ['⛈️', 'bouřka s kroupami'], 99: ['⛈️', 'bouřka s kroupami'],
};

export function describeCode(code) {
  return WMO[code] ?? ['❔', 'neznámo'];
}

export async function fetchWeather({ lat, lon }) {
  const url = new URL('https://api.open-meteo.com/v1/forecast');
  url.search = new URLSearchParams({
    latitude: lat.toFixed(4),
    longitude: lon.toFixed(4),
    hourly: 'temperature_2m,pressure_msl,precipitation,wind_speed_10m,cloud_cover',
    daily: 'weather_code,temperature_2m_max,temperature_2m_min,temperature_2m_mean,precipitation_sum,wind_speed_10m_max,sunrise,sunset',
    current: 'temperature_2m,pressure_msl,wind_speed_10m,wind_direction_10m,cloud_cover,weather_code,precipitation',
    past_days: '5',
    forecast_days: '4',
    timezone: 'Europe/Prague',
    wind_speed_unit: 'ms',
  });
  const r = await fetch(url);
  if (!r.ok) throw new Error(`Open-Meteo ${r.status}`);
  return analyze(await r.json());
}

function analyze(w) {
  const now = new Date();
  const times = w.hourly.time.map(t => new Date(t));
  let idx = times.findIndex(t => t > now) - 1;
  if (idx < 0) idx = times.length - 1;
  const p = w.hourly.pressure_msl;
  const pressureNow = w.current?.pressure_msl ?? p[idx];
  const pressure24hAgo = p[Math.max(0, idx - 24)];
  const pressureIn12h = p[Math.min(p.length - 1, idx + 12)];

  const todayStr = w.current?.time?.slice(0, 10) ?? now.toISOString().slice(0, 10);
  const todayIdx = Math.max(0, w.daily.time.indexOf(todayStr));
  const pastMeans = w.daily.temperature_2m_mean.slice(Math.max(0, todayIdx - 5), todayIdx + 1).filter(v => v != null);
  const rainLast3d = w.daily.precipitation_sum.slice(Math.max(0, todayIdx - 3), todayIdx + 1).reduce((s, v) => s + (v ?? 0), 0);

  return {
    current: {
      temp: w.current?.temperature_2m,
      pressure: pressureNow,
      wind: w.current?.wind_speed_10m,
      windDir: w.current?.wind_direction_10m,
      cloud: w.current?.cloud_cover,
      code: w.current?.weather_code,
      precip: w.current?.precipitation,
    },
    pressureTrend24h: pressureNow - pressure24hAgo,
    pressureNext12h: pressureIn12h - pressureNow,
    airMean5d: pastMeans.length ? pastMeans.reduce((s, v) => s + v, 0) / pastMeans.length : null,
    rainLast3d,
    days: w.daily.time.slice(todayIdx, todayIdx + 4).map((d, i) => ({
      date: d,
      code: w.daily.weather_code[todayIdx + i],
      tmax: w.daily.temperature_2m_max[todayIdx + i],
      tmin: w.daily.temperature_2m_min[todayIdx + i],
      rain: w.daily.precipitation_sum[todayIdx + i],
      wind: w.daily.wind_speed_10m_max[todayIdx + i],
      sunrise: w.daily.sunrise[todayIdx + i],
      sunset: w.daily.sunset[todayIdx + i],
    })),
  };
}

// Fáze měsíce 0..1 (0 = nov, 0.5 = úplněk) – výpočet z délky synodického měsíce.
export function moonPhase(date = new Date()) {
  const knownNew = Date.UTC(2000, 0, 6, 18, 14);
  const synodic = 29.530588853;
  const days = (date.getTime() - knownNew) / 86400000;
  return (((days / synodic) % 1) + 1) % 1;
}

export function moonLabel(phase) {
  if (phase < 0.03 || phase > 0.97) return '🌑 nov';
  if (phase < 0.22) return '🌒 dorůstá';
  if (phase < 0.28) return '🌓 první čtvrť';
  if (phase < 0.47) return '🌔 dorůstá';
  if (phase < 0.53) return '🌕 úplněk';
  if (phase < 0.72) return '🌖 couvá';
  if (phase < 0.78) return '🌗 poslední čtvrť';
  return '🌘 couvá';
}
