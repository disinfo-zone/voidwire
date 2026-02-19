import type { APIRoute } from 'astro';
import satori from 'satori';
import { Resvg } from '@resvg/resvg-js';
import { readFile, access } from 'node:fs/promises';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const API_URL = process.env.API_URL || import.meta.env.API_URL || 'http://voidwire-api:8000';

const WIDTH = 1200;
const HEIGHT = 630;

// --- Wheel geometry (matches TransitWheel.svelte exactly) ---
const W = 520, CX = W / 2, CY = W / 2;
const R_OUTER = 218, R_SIGN_INNER = 185, R_INNER = 122;
const R_ASPECT = R_INNER - 5;
const BASE_ORBIT = 160, ORBIT_STEP = 22, MIN_DEG_SEP = 12;
const MARKER_R = 10;
const BRASS = '#d6af72';
const PHI = 1.618033988749;
const GLYPH_FONT = 'Noto Sans Symbols';
const GLYPH_FONT_2 = 'Noto Sans Symbols 2';

const SIGN_ORDER = [
  'Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
  'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces',
];

const SIGN_COLORS: Record<string, string> = {
  Aries: '#ff8b7b', Taurus: '#e3c470', Gemini: '#f1ea86', Cancer: '#9fd2ff',
  Leo: '#ffcc6a', Virgo: '#bce68f', Libra: '#b9a3ff', Scorpio: '#df8fff',
  Sagittarius: '#ffad80', Capricorn: '#8ec5b8', Aquarius: '#90d0ff', Pisces: '#a0a6ff',
};

// Unicode glyphs — identical to TransitWheel.svelte
const SIGN_GLYPHS: Record<string, string> = {
  Aries: '\u2648', Taurus: '\u2649', Gemini: '\u264A', Cancer: '\u264B',
  Leo: '\u264C', Virgo: '\u264D', Libra: '\u264E', Scorpio: '\u264F',
  Sagittarius: '\u2650', Capricorn: '\u2651', Aquarius: '\u2652', Pisces: '\u2653',
};

const PLANET_GLYPHS: Record<string, { char: string; font: string }> = {
  Sun: { char: '\u2609', font: GLYPH_FONT_2 },
  Moon: { char: '\u263D', font: GLYPH_FONT },
  Mercury: { char: '\u263F', font: GLYPH_FONT },
  Venus: { char: '\u2640', font: GLYPH_FONT },
  Mars: { char: '\u2642', font: GLYPH_FONT },
  Jupiter: { char: '\u2643', font: GLYPH_FONT },
  Saturn: { char: '\u2644', font: GLYPH_FONT },
  Uranus: { char: '\u2645', font: GLYPH_FONT },
  Neptune: { char: '\u2646', font: GLYPH_FONT },
  Pluto: { char: '\u2647', font: GLYPH_FONT },
  'North Node': { char: '\u260A', font: GLYPH_FONT },
  Chiron: { char: '\u26B7', font: GLYPH_FONT },
  'Part Of Fortune': { char: '\u2297', font: GLYPH_FONT_2 },
};

const ASPECT_COLORS: Record<string, string> = {
  conjunction: '#c8ba32', trine: '#4a7ab5', square: '#b54a4a', opposition: '#c87832',
  sextile: '#4ab56a', quincunx: '#8a6ab5', semisquare: '#b5804a', sesquiquadrate: '#b5804a',
};

const MAJOR_ASPECTS = new Set(['conjunction', 'opposition', 'square', 'trine']);
const MODERATE_ASPECTS = new Set(['sextile', 'quincunx']);

const PLANET_CASE: Record<string, string> = {};
for (const key of Object.keys(PLANET_GLYPHS)) PLANET_CASE[key.toLowerCase()] = key;

type EphemerisData = {
  positions?: Record<string, { sign: string; longitude: number; degree: number; retrograde: boolean }>;
  aspects?: Array<{ body1: string; body2: string; type?: string; aspect_type?: string; orb_degrees?: number; orb?: number; applying?: boolean }>;
};

function displayBrandHost(originUrl: URL): string {
  const host = String(originUrl.hostname || '').trim().replace(/^www\./i, '');
  return (host || 'voidwire.app').toUpperCase();
}

function toXY(deg: number, r: number) {
  const rad = (180 - deg) * Math.PI / 180;
  return { x: CX + r * Math.cos(rad), y: CY + r * Math.sin(rad) };
}

function arcPath(r1: number, r2: number, startDeg: number, endDeg: number): string {
  const s1 = toXY(startDeg, r1), e1 = toXY(endDeg, r1);
  const s2 = toXY(endDeg, r2), e2 = toXY(startDeg, r2);
  return `M ${s1.x} ${s1.y} A ${r1} ${r1} 0 0 0 ${e1.x} ${e1.y} L ${s2.x} ${s2.y} A ${r2} ${r2} 0 0 1 ${e2.x} ${e2.y} Z`;
}

function normalizeSign(sign: string): string {
  return SIGN_ORDER.find(s => s.toLowerCase() === sign.toLowerCase()) || sign;
}

function normalizePlanet(name: string): string {
  return PLANET_CASE[name.toLowerCase()] || name;
}

function buildWheelSvg(ephemeris: EphemerisData): string {
  const positions = ephemeris.positions || {};
  const aspects = ephemeris.aspects || [];
  let defs = '';
  let svg = '';

  // --- Defs ---
  defs += `<clipPath id="wc"><circle cx="${CX}" cy="${CY}" r="${R_OUTER + 1}"/></clipPath>`;
  defs += `<radialGradient id="bg" cx="50%" cy="50%" r="50%"><stop offset="0%" stop-color="#0a1228"/><stop offset="80%" stop-color="#080510"/><stop offset="100%" stop-color="#06040d"/></radialGradient>`;
  defs += `<radialGradient id="n1" cx="35%" cy="40%" r="55%"><stop offset="0%" stop-color="rgba(70,110,180,0.12)"/><stop offset="50%" stop-color="rgba(70,110,180,0.04)"/><stop offset="100%" stop-color="rgba(0,0,0,0)"/></radialGradient>`;
  defs += `<radialGradient id="n2" cx="65%" cy="55%" r="50%"><stop offset="0%" stop-color="rgba(180,145,80,0.10)"/><stop offset="50%" stop-color="rgba(180,145,80,0.03)"/><stop offset="100%" stop-color="rgba(0,0,0,0)"/></radialGradient>`;
  defs += `<radialGradient id="n3" cx="45%" cy="65%" r="50%"><stop offset="0%" stop-color="rgba(90,50,130,0.10)"/><stop offset="50%" stop-color="rgba(90,50,130,0.03)"/><stop offset="100%" stop-color="rgba(0,0,0,0)"/></radialGradient>`;
  defs += `<radialGradient id="glow" cx="50%" cy="50%" r="50%"><stop offset="0%" stop-color="rgba(100,130,200,0.08)"/><stop offset="60%" stop-color="rgba(214,175,114,0.04)"/><stop offset="100%" stop-color="rgba(0,0,0,0)"/></radialGradient>`;

  // --- Ambient glow ---
  svg += `<circle cx="${CX}" cy="${CY}" r="${R_OUTER + 40}" fill="url(#glow)"/>`;

  // --- Interior atmosphere (clipped) ---
  svg += `<g clip-path="url(#wc)"><circle cx="${CX}" cy="${CY}" r="${R_OUTER}" fill="url(#bg)"/><circle cx="${CX}" cy="${CY}" r="${R_OUTER}" fill="url(#n1)"/><circle cx="${CX}" cy="${CY}" r="${R_OUTER}" fill="url(#n2)"/><circle cx="${CX}" cy="${CY}" r="${R_OUTER}" fill="url(#n3)"/></g>`;

  // --- Sacred geometry (matching TransitWheel: hexagram, PHI circles, radials every 15°) ---
  svg += `<g opacity="0.055" stroke="${BRASS}" fill="none" stroke-width="0.5">`;
  for (const offset of [0, 60]) {
    const pts = [0, 1, 2].map(i => {
      const a = (i * 120 + offset) * Math.PI / 180;
      return { x: CX + Math.cos(a) * R_INNER * 0.88, y: CY + Math.sin(a) * R_INNER * 0.88 };
    });
    svg += `<polygon points="${pts.map(p => `${p.x},${p.y}`).join(' ')}"/>`;
  }
  for (let i = 1; i <= 4; i++) {
    const r = R_INNER * 0.15 * Math.pow(PHI, i);
    if (r < R_OUTER) svg += `<circle cx="${CX}" cy="${CY}" r="${r}"/>`;
  }
  for (let deg = 0; deg < 360; deg += 15) {
    const a = deg * Math.PI / 180;
    svg += `<line x1="${CX + Math.cos(a) * R_INNER * 0.3}" y1="${CY + Math.sin(a) * R_INNER * 0.3}" x2="${CX + Math.cos(a) * R_INNER * 0.85}" y2="${CY + Math.sin(a) * R_INNER * 0.85}"/>`;
  }
  svg += `</g>`;

  // --- Wheel rings ---
  svg += `<circle cx="${CX}" cy="${CY}" r="${R_INNER}" fill="none" stroke="${BRASS}" stroke-width="1" opacity="0.4"/>`;
  svg += `<circle cx="${CX}" cy="${CY}" r="${R_SIGN_INNER}" fill="none" stroke="${BRASS}" stroke-width="0.8" opacity="0.35"/>`;
  svg += `<circle cx="${CX}" cy="${CY}" r="${R_OUTER}" fill="none" stroke="${BRASS}" stroke-width="1.2" opacity="0.5"/>`;

  // --- Zodiac sign segments ---
  const glyphR = (R_OUTER + R_SIGN_INNER) / 2;
  for (let i = 0; i < 12; i++) {
    const sign = SIGN_ORDER[i];
    const color = SIGN_COLORS[sign] || '#9aa6c0';
    const startDeg = i * 30;
    svg += `<path d="${arcPath(R_OUTER, R_SIGN_INNER, startDeg, startDeg + 30)}" fill="${color}" opacity="0.06" stroke="none"/>`;
    const b1 = toXY(startDeg, R_OUTER), b2 = toXY(startDeg, R_SIGN_INNER);
    svg += `<line x1="${b1.x}" y1="${b1.y}" x2="${b2.x}" y2="${b2.y}" stroke="${BRASS}" stroke-width="0.5" opacity="0.2"/>`;
    // Unicode sign glyph
    const gp = toXY(startDeg + 15, glyphR);
    svg += `<text x="${gp.x}" y="${gp.y}" text-anchor="middle" dominant-baseline="central" fill="${color}" font-size="16" font-family="${GLYPH_FONT}" opacity="0.9">${SIGN_GLYPHS[sign] || ''}</text>`;
  }

  // --- Tick marks ---
  for (let d = 0; d < 360; d += 5) {
    if (d % 30 === 0) continue;
    const isMajor = d % 10 === 0;
    const t1 = toXY(d, R_SIGN_INNER), t2 = toXY(d, R_SIGN_INNER + (isMajor ? 5 : 3));
    svg += `<line x1="${t1.x}" y1="${t1.y}" x2="${t2.x}" y2="${t2.y}" stroke="${BRASS}" stroke-width="0.4" opacity="${isMajor ? 0.2 : 0.1}"/>`;
  }

  // --- Aspect lines (matching TransitWheel opacity/dash logic) ---
  const posMap: Record<string, number> = {};
  for (const [name, pos] of Object.entries(positions)) posMap[name.toLowerCase()] = pos.longitude;

  for (const asp of aspects) {
    const type = (asp.type || asp.aspect_type || '').toLowerCase();
    const lng1 = posMap[(asp.body1 || '').toLowerCase()];
    const lng2 = posMap[(asp.body2 || '').toLowerCase()];
    if (lng1 == null || lng2 == null) continue;
    const color = ASPECT_COLORS[type] || '#555';
    const orb = Math.abs(Number(asp.orb_degrees || asp.orb || 0));
    const isMajor = MAJOR_ASPECTS.has(type);
    const isModerate = MODERATE_ASPECTS.has(type);
    const isMinor = !isMajor && !isModerate;
    const applying = Boolean(asp.applying);
    const opacity = Math.max(0.15, 0.7 * (1 - orb / 10));
    const width = isMajor ? 1.5 : isModerate ? 1.0 : 0.7;
    let dash = '';
    if (isMinor) dash = ' stroke-dasharray="4 3"';
    else if (!applying) dash = ' stroke-dasharray="6 4"';
    const p1 = toXY(lng1, R_ASPECT), p2 = toXY(lng2, R_ASPECT);
    svg += `<line x1="${p1.x}" y1="${p1.y}" x2="${p2.x}" y2="${p2.y}" stroke="${color}" stroke-width="${width}" opacity="${opacity.toFixed(2)}"${dash}/>`;
    // Endpoint dots (matching TransitWheel)
    const dotOp = (opacity * 0.6).toFixed(2);
    svg += `<circle cx="${p1.x}" cy="${p1.y}" r="1.5" fill="${color}" opacity="${dotOp}"/>`;
    svg += `<circle cx="${p2.x}" cy="${p2.y}" r="1.5" fill="${color}" opacity="${dotOp}"/>`;
  }

  // --- Planet markers (orbit stacking, no angle nudging — matches TransitWheel) ---
  const sorted = Object.entries(positions)
    .map(([name, pos]) => ({ name: normalizePlanet(name), ...pos }))
    .sort((a, b) => a.longitude - b.longitude);

  for (let i = 0; i < sorted.length; i++) {
    const p = sorted[i];
    const sign = normalizeSign(p.sign);
    const color = SIGN_COLORS[sign] || BRASS;
    let clusterDepth = 0;
    for (let j = 0; j < i; j++) {
      const diff = Math.abs(p.longitude - sorted[j].longitude);
      if (Math.min(diff, 360 - diff) < MIN_DEG_SEP) clusterDepth++;
    }
    const orbitR = BASE_ORBIT + clusterDepth * ORBIT_STEP;
    const pt = toXY(p.longitude, orbitR);
    const innerPt = toXY(p.longitude, R_INNER);

    // Dashed connector (matching TransitWheel)
    svg += `<line x1="${innerPt.x}" y1="${innerPt.y}" x2="${pt.x}" y2="${pt.y}" stroke="${color}" stroke-width="0.6" opacity="0.25" stroke-dasharray="2 2"/>`;
    // Dark background circle + colored ring
    svg += `<circle cx="${pt.x}" cy="${pt.y}" r="${MARKER_R}" fill="#080c16"/>`;
    svg += `<circle cx="${pt.x}" cy="${pt.y}" r="${MARKER_R}" fill="none" stroke="${color}" stroke-width="1.2"/>`;
    // Unicode planet glyph
    const glyphInfo = PLANET_GLYPHS[p.name];
    if (glyphInfo) {
      svg += `<text x="${pt.x}" y="${pt.y}" text-anchor="middle" dominant-baseline="central" fill="${color}" font-size="14" font-family="${glyphInfo.font}">${glyphInfo.char}</text>`;
    }
    // Retrograde: red outer ring
    if (p.retrograde) {
      svg += `<circle cx="${pt.x}" cy="${pt.y}" r="${MARKER_R + 2}" fill="none" stroke="#ff6b6b" stroke-width="1" opacity="0.5"/>`;
    }
  }

  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${W}" width="${W}" height="${W}"><defs>${defs}</defs>${svg}</svg>`;
}

// --- Font loading ---
let fontCache: { dir: string; inter: Buffer; garamond: Buffer } | null = null;

async function findFontDir(): Promise<string> {
  const candidates = [
    join(process.cwd(), 'dist', 'client', 'fonts'),
    join(process.cwd(), 'client', 'fonts'),
    join(dirname(fileURLToPath(import.meta.url)), '..', '..', 'client', 'fonts'),
    join(process.cwd(), 'public', 'fonts'),
  ];
  for (const dir of candidates) {
    try { await access(join(dir, 'Inter-400.woff')); return dir; } catch {}
  }
  throw new Error(`Fonts not found. cwd=${process.cwd()}`);
}

async function loadFonts(): Promise<{ dir: string; inter: Buffer; garamond: Buffer }> {
  if (fontCache) return fontCache;
  const dir = await findFontDir();
  const [inter, garamond] = await Promise.all([
    readFile(join(dir, 'Inter-400.woff')),
    readFile(join(dir, 'EBGaramond-400.woff')),
  ]);
  fontCache = { dir, inter, garamond };
  return fontCache;
}

// --- Route handler ---
export const GET: APIRoute = async ({ params, url }) => {
  const dateStr = params.date;
  if (!dateStr) return new Response('Not found', { status: 404 });

  try {
    const [readingRes, ephemRes, fonts] = await Promise.all([
      fetch(`${API_URL}/v1/reading/${dateStr}`).catch(() => null),
      fetch(`${API_URL}/v1/ephemeris/${dateStr}`).catch(() => null),
      loadFonts(),
    ]);

    const reading = readingRes?.ok ? await readingRes.json() : null;
    const ephemeris: EphemerisData = ephemRes?.ok ? await ephemRes.json() : {};
    const title = reading?.title || `Reading for ${dateStr}`;

    const len = title.length;
    const brandHost = displayBrandHost(url);
    const titleSize = len <= 25 ? 50 : len <= 40 ? 44 : len <= 55 ? 38 : 32;

    // Build wheel SVG with Unicode text glyphs
    const wheelSvg = buildWheelSvg(ephemeris);

    // Pre-render wheel to PNG with symbol fonts (so Unicode glyphs render correctly)
    const symbolFont1 = join(fonts.dir, 'NotoSansSymbols.ttf');
    const symbolFont2 = join(fonts.dir, 'NotoSansSymbols2.ttf');
    const wheelResvg = new Resvg(wheelSvg, {
      fitTo: { mode: 'width', value: 490 },
      font: {
        fontFiles: [symbolFont1, symbolFont2],
        defaultFontFamily: GLYPH_FONT,
        loadSystemFonts: false,
      },
    });
    const wheelPng = wheelResvg.render().asPng();
    const wheelUri = `data:image/png;base64,${Buffer.from(wheelPng).toString('base64')}`;

    const svg = await satori(
      {
        type: 'div',
        props: {
          style: { width: '100%', height: '100%', display: 'flex', background: '#060a16', fontFamily: 'Inter', position: 'relative' },
          children: [
            // Inset border
            { type: 'div', props: { style: { position: 'absolute', top: '16px', left: '16px', right: '16px', bottom: '16px', border: '1px solid rgba(214,175,114,0.1)', borderRadius: '2px' } } },
            // Left text
            {
              type: 'div',
              props: {
                style: { display: 'flex', flexDirection: 'column' as const, justifyContent: 'center', padding: '60px 20px 60px 60px', flex: '1' },
                children: [
                  { type: 'div', props: { style: { fontSize: '12px', fontWeight: 400, letterSpacing: '0.25em', color: '#d6af72', marginBottom: '28px' }, children: brandHost } },
                  { type: 'div', props: { style: { fontSize: `${titleSize}px`, fontFamily: 'EB Garamond', fontWeight: 400, color: '#d9d4c9', lineHeight: 1.2, marginBottom: '24px' }, children: title } },
                  {
                    type: 'div',
                    props: {
                      style: { display: 'flex', alignItems: 'center', gap: '12px', marginTop: '4px' },
                      children: [
                        { type: 'div', props: { style: { width: '40px', height: '1px', background: 'rgba(214,175,114,0.3)' } } },
                        { type: 'div', props: { style: { fontSize: '13px', fontWeight: 400, letterSpacing: '0.2em', color: '#6f6a62' }, children: dateStr } },
                      ],
                    },
                  },
                ],
              },
            },
            // Right: pre-rendered wheel PNG
            {
              type: 'div',
              props: {
                style: { display: 'flex', alignItems: 'center', justifyContent: 'center', width: '500px', marginRight: '10px' },
                children: { type: 'img', props: { src: wheelUri, width: 490, height: 490 } },
              },
            },
          ],
        },
      },
      { width: WIDTH, height: HEIGHT, fonts: [
        { name: 'Inter', data: fonts.inter, weight: 400, style: 'normal' as const },
        { name: 'EB Garamond', data: fonts.garamond, weight: 400, style: 'normal' as const },
      ] },
    );

    const resvg = new Resvg(svg, { fitTo: { mode: 'width', value: WIDTH } });
    const png = resvg.render().asPng();

    return new Response(png, {
      status: 200,
      headers: { 'Content-Type': 'image/png', 'Cache-Control': 'public, max-age=86400, s-maxage=86400' },
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    console.error('OG image generation failed:', message, err instanceof Error ? err.stack : undefined);
    return new Response(JSON.stringify({ error: message }), { status: 500, headers: { 'Content-Type': 'application/json' } });
  }
};
