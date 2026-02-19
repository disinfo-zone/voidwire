const BASE_URL = process.env.SMOKE_BASE_URL || 'http://127.0.0.1:4510';
const failures = [];

async function fetchText(path, init = {}) {
  const res = await fetch(`${BASE_URL}${path}`, init);
  const text = await res.text();
  return { res, text };
}

function expect(condition, message) {
  if (!condition) failures.push(message);
}

async function run() {
  {
    const { res, text } = await fetchText('/');
    expect(res.status === 200, `GET / expected 200, got ${res.status}`);
    expect(text.includes('VOIDWIRE'), 'GET / missing VOIDWIRE marker');
  }

  {
    const { res, text } = await fetchText('/dashboard');
    expect(res.status === 200, `GET /dashboard expected 200, got ${res.status}`);
    expect(!text.includes('id="dashboard-content" style="display: none;"'), 'Dashboard content is still hidden by default');
    expect(text.includes('selfNavGuarded'), 'Dashboard is missing nav self-link guard script');
  }

  {
    const { res, text } = await fetchText('/events');
    expect(res.status === 200, `GET /events expected 200, got ${res.status}`);
    expect(text.includes('Celestial Weather'), 'Events page missing title');
    const hasMoonOrFallback = text.includes('moon-disc-canvas') || text.includes('weather-fallback');
    expect(hasMoonOrFallback, 'Events page missing moon card and ephemeris fallback state');
    expect(text.includes('.site-nav a[href="/events"]'), 'Events page missing active-nav server-side style hook');
  }

  {
    const { res } = await fetchText('/readings/sdjlfhsdkljfhs');
    expect(res.status === 404, `/readings/<random> expected 404, got ${res.status}`);
  }

  {
    const { res } = await fetchText('/readings/2026-02-01', { redirect: 'manual' });
    expect(res.status === 308, `/readings/YYYY-MM-DD expected 308, got ${res.status}`);
    expect(res.headers.get('location') === '/reading/2026-02-01', 'Redirect location for /readings/YYYY-MM-DD is incorrect');
  }

  if (failures.length > 0) {
    console.error('Route smoke tests failed:');
    for (const failure of failures) console.error(`- ${failure}`);
    process.exit(1);
  }

  console.log(`Route smoke tests passed (${BASE_URL})`);
}

run().catch((err) => {
  console.error('Route smoke tests crashed:', err);
  process.exit(1);
});
