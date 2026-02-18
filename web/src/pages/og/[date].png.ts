import type { APIRoute } from 'astro';
import satori from 'satori';
import { Resvg } from '@resvg/resvg-js';
import { readFile, access } from 'node:fs/promises';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const API_URL = process.env.API_URL || import.meta.env.API_URL || 'http://voidwire-api:8000';

const WIDTH = 1200;
const HEIGHT = 630;

// --- Wheel SVG builder (matches TransitWheel.svelte visual language) ---
const W = 520, CX = W / 2, CY = W / 2;
const R_OUTER = 218, R_SIGN_INNER = 185, R_INNER = 122;
const R_ASPECT = R_INNER - 5;
const BASE_ORBIT = 160, ORBIT_STEP = 22, MIN_DEG_SEP = 12;
const BRASS = '#d6af72';
const PHI = 1.618033988749;

const SIGN_ORDER = [
  'Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
  'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces',
];

const SIGN_COLORS: Record<string, string> = {
  Aries: '#ff8b7b', Taurus: '#e3c470', Gemini: '#f1ea86', Cancer: '#9fd2ff',
  Leo: '#ffcc6a', Virgo: '#bce68f', Libra: '#b9a3ff', Scorpio: '#df8fff',
  Sagittarius: '#ffad80', Capricorn: '#8ec5b8', Aquarius: '#90d0ff', Pisces: '#a0a6ff',
};

const ASPECT_COLORS: Record<string, string> = {
  conjunction: '#c8ba32', trine: '#4a7ab5', square: '#b54a4a', opposition: '#c87832',
  sextile: '#4ab56a', quincunx: '#8a6ab5', semisquare: '#b5804a', sesquiquadrate: '#b5804a',
};

const MAJOR_ASPECTS = new Set(['conjunction', 'opposition', 'square', 'trine']);
const MODERATE_ASPECTS = new Set(['sextile', 'quincunx']);

// SVG path data for zodiac sign glyphs (designed at ~24px centered on 0,0)
const SIGN_GLYPH_PATHS: Record<string, string> = {
  Aries: 'M -6 6 C -6 -1 -2 -8 0 -2 C 2 -8 6 -1 6 6',
  Taurus: 'M -6 -3 Q -6 -8 0 -8 Q 6 -8 6 -3 M 0 -3 A 5 5 0 1 1 0 7 A 5 5 0 1 1 0 -3',
  Gemini: 'M -6 -7 L 6 -7 M -6 7 L 6 7 M -3 -7 L -3 7 M 3 -7 L 3 7',
  Cancer: 'M 6 -2 A 5 5 0 1 0 -4 -2 M -6 2 A 5 5 0 1 0 4 2',
  Leo: 'M -5 4 A 4 4 0 1 1 -1 0 Q 2 -4 5 -6 M 5 -6 A 2 2 0 1 1 5 -2',
  Virgo: 'M -6 6 L -6 -4 Q -6 -8 -3 -4 L -3 6 M -3 -4 Q -3 -8 0 -4 L 0 6 M 0 -4 Q 0 -8 3 -4 L 3 2 Q 6 2 6 6',
  Libra: 'M -7 4 L 7 4 M -5 0 Q -5 -6 0 -6 Q 5 -6 5 0',
  Scorpio: 'M -6 6 L -6 -4 Q -6 -8 -3 -4 L -3 6 M -3 -4 Q -3 -8 0 -4 L 0 6 M 0 -4 Q 0 -8 3 -4 L 3 6 L 6 3',
  Sagittarius: 'M -5 7 L 6 -6 M 6 -6 L 1 -6 M 6 -6 L 6 -1 M -3 3 L 3 -3',
  Capricorn: 'M -6 -4 L -6 6 Q -2 6 0 2 Q 2 -2 4 0 A 3 3 0 1 1 4 6',
  Aquarius: 'M -7 -2 L -4 -5 L -1 -2 L 2 -5 L 5 -2 M -7 3 L -4 0 L -1 3 L 2 0 L 5 3',
  Pisces: 'M -7 0 L 7 0 M -5 -7 A 6 7 0 0 1 -5 7 M 5 -7 A 6 7 0 0 0 5 7',
};

// SVG path data for planet glyphs (designed at ~20px centered on 0,0)
const PLANET_GLYPH_PATHS: Record<string, string> = {
  Sun: 'M 0 0 m -7 0 a 7 7 0 1 0 14 0 a 7 7 0 1 0 -14 0 M 0 -2 a 2 2 0 1 0 0.01 0',
  Moon: 'M 3 -7 A 7 7 0 1 0 3 7 A 5.5 5.5 0 0 1 3 -7',
  Mercury: 'M 0 -2 m -5 0 a 5 5 0 1 0 10 0 a 5 5 0 1 0 -10 0 M 0 3 L 0 9 M -3 6 L 3 6 M -3 -7 A 3 2 0 0 1 3 -7',
  Venus: 'M 0 -3 m -5 0 a 5 5 0 1 0 10 0 a 5 5 0 1 0 -10 0 M 0 2 L 0 9 M -3 6 L 3 6',
  Mars: 'M -2 2 m -5 0 a 5 5 0 1 0 10 0 a 5 5 0 1 0 -10 0 M 2 -2 L 7 -7 M 3 -7 L 7 -7 L 7 -3',
  Jupiter: 'M -2 0 L 7 0 M 3 -8 L 3 8 M -6 -3 Q 0 -8 3 0',
  Saturn: 'M -2 -8 L 4 -8 M 1 -8 L 1 0 Q 6 0 4 5 Q 2 8 -2 6 M -4 -4 L 4 -4',
  Uranus: 'M 0 -1 m -4 0 a 4 4 0 1 0 8 0 a 4 4 0 1 0 -8 0 M 0 -5 L 0 -9 M 0 -9 L -3 -7 M 0 -9 L 3 -7 M -5 -1 L -8 -1 M 5 -1 L 8 -1 M 0 3 L 0 7',
  Neptune: 'M 0 -8 L 0 8 M -4 5 L 4 5 M -6 -5 Q -3 -9 0 -5 Q 3 -9 6 -5',
  Pluto: 'M 0 -2 m -5 0 a 5 5 0 1 0 10 0 a 5 5 0 1 0 -10 0 M -2 -7 A 5 5 0 0 1 2 -7 M 0 3 L 0 9 M -3 6 L 3 6',
  'North Node': 'M -5 5 L -5 -2 A 5 5 0 0 1 5 -2 L 5 5 M 0 -7 A 7 7 0 0 0 0 7',
  Chiron: 'M 0 -8 L 0 8 M -4 -4 L 0 -1 L 4 -4 M 0 2 m -4 0 a 4 4 0 1 0 8 0 a 4 4 0 1 0 -8 0',
};

type EphemerisData = {
  positions?: Record<string, { sign: string; longitude: number; degree: number; retrograde: boolean }>;
  aspects?: Array<{ body1: string; body2: string; type?: string; aspect_type?: string; orb_degrees?: number; orb?: number }>;
};

function toXY(deg: number, r: number) {
  const rad = (180 - deg) * Math.PI / 180;
  return { x: CX + r * Math.cos(rad), y: CY - r * Math.sin(rad) };
}

function arcPath(r1: number, r2: number, startDeg: number, endDeg: number): string {
  const s1 = toXY(startDeg, r1), e1 = toXY(endDeg, r1);
  const s2 = toXY(endDeg, r2), e2 = toXY(startDeg, r2);
  return `M ${s1.x} ${s1.y} A ${r1} ${r1} 0 0 1 ${e1.x} ${e1.y} L ${s2.x} ${s2.y} A ${r2} ${r2} 0 0 0 ${e2.x} ${e2.y} Z`;
}

function normalizeSign(sign: string): string {
  return SIGN_ORDER.find(s => s.toLowerCase() === sign.toLowerCase()) || sign;
}

function buildWheelSvg(ephemeris: EphemerisData): string {
  const positions = ephemeris.positions || {};
  const aspects = ephemeris.aspects || [];

  let defs = '';
  let svg = '';

  // --- Defs: gradients and filters matching TransitWheel.svelte ---
  defs += `<clipPath id="wc"><circle cx="${CX}" cy="${CY}" r="${R_OUTER + 1}"/></clipPath>`;
  defs += `<radialGradient id="bg" cx="50%" cy="50%" r="50%"><stop offset="0%" stop-color="#0a1228"/><stop offset="80%" stop-color="#080510"/><stop offset="100%" stop-color="#06040d"/></radialGradient>`;
  defs += `<radialGradient id="n1" cx="35%" cy="40%" r="55%"><stop offset="0%" stop-color="rgba(70,110,180,0.12)"/><stop offset="50%" stop-color="rgba(70,110,180,0.04)"/><stop offset="100%" stop-color="rgba(0,0,0,0)"/></radialGradient>`;
  defs += `<radialGradient id="n2" cx="65%" cy="55%" r="50%"><stop offset="0%" stop-color="rgba(180,145,80,0.10)"/><stop offset="50%" stop-color="rgba(180,145,80,0.03)"/><stop offset="100%" stop-color="rgba(0,0,0,0)"/></radialGradient>`;
  defs += `<radialGradient id="n3" cx="45%" cy="65%" r="50%"><stop offset="0%" stop-color="rgba(90,50,130,0.10)"/><stop offset="50%" stop-color="rgba(90,50,130,0.03)"/><stop offset="100%" stop-color="rgba(0,0,0,0)"/></radialGradient>`;
  defs += `<radialGradient id="glow" cx="50%" cy="50%" r="50%"><stop offset="0%" stop-color="rgba(100,130,200,0.08)"/><stop offset="60%" stop-color="rgba(214,175,114,0.04)"/><stop offset="100%" stop-color="rgba(0,0,0,0)"/></radialGradient>`;

  // --- Ambient glow halo ---
  svg += `<circle cx="${CX}" cy="${CY}" r="${R_OUTER + 40}" fill="url(#glow)"/>`;

  // --- Interior atmosphere (clipped) ---
  svg += `<g clip-path="url(#wc)">`;
  svg += `<circle cx="${CX}" cy="${CY}" r="${R_OUTER}" fill="url(#bg)"/>`;
  svg += `<circle cx="${CX}" cy="${CY}" r="${R_OUTER}" fill="url(#n1)"/>`;
  svg += `<circle cx="${CX}" cy="${CY}" r="${R_OUTER}" fill="url(#n2)"/>`;
  svg += `<circle cx="${CX}" cy="${CY}" r="${R_OUTER}" fill="url(#n3)"/>`;
  svg += `</g>`;

  // --- Sacred geometry (matching TransitWheel) ---
  svg += `<g opacity="0.055" stroke="${BRASS}" fill="none" stroke-width="0.5">`;
  // Interlocking triangles
  for (const offset of [0, 30]) {
    const pts = [0, 1, 2].map(i => toXY(offset + i * 120, R_INNER * 0.88));
    svg += `<polygon points="${pts.map(p => `${p.x},${p.y}`).join(' ')}"/>`;
  }
  // Golden ratio circles
  for (let i = 1; i <= 4; i++) {
    const r = R_INNER * 0.15 * Math.pow(PHI, i);
    if (r < R_OUTER) svg += `<circle cx="${CX}" cy="${CY}" r="${r}"/>`;
  }
  // Radial lines
  for (let deg = 0; deg < 360; deg += 30) {
    const a = deg * Math.PI / 180;
    svg += `<line x1="${CX + Math.cos(a) * R_INNER * 0.3}" y1="${CY + Math.sin(a) * R_INNER * 0.3}" x2="${CX + Math.cos(a) * R_INNER * 0.85}" y2="${CY + Math.sin(a) * R_INNER * 0.85}"/>`;
  }
  svg += `</g>`;

  // --- Wheel rings ---
  svg += `<circle cx="${CX}" cy="${CY}" r="${R_INNER}" fill="none" stroke="${BRASS}" stroke-width="1" opacity="0.4"/>`;
  svg += `<circle cx="${CX}" cy="${CY}" r="${R_SIGN_INNER}" fill="none" stroke="${BRASS}" stroke-width="0.8" opacity="0.35"/>`;
  svg += `<circle cx="${CX}" cy="${CY}" r="${R_OUTER}" fill="none" stroke="${BRASS}" stroke-width="1.2" opacity="0.5"/>`;

  // --- Zodiac sign segments ---
  for (let i = 0; i < 12; i++) {
    const sign = SIGN_ORDER[i];
    const color = SIGN_COLORS[sign] || '#9aa6c0';
    const startDeg = i * 30;
    // Colored fill segment
    svg += `<path d="${arcPath(R_OUTER, R_SIGN_INNER, startDeg, startDeg + 30)}" fill="${color}" opacity="0.06" stroke="none"/>`;
    // Boundary line
    const b1 = toXY(startDeg, R_OUTER), b2 = toXY(startDeg, R_SIGN_INNER);
    svg += `<line x1="${b1.x}" y1="${b1.y}" x2="${b2.x}" y2="${b2.y}" stroke="${BRASS}" stroke-width="0.5" opacity="0.2"/>`;
    // Sign glyph (SVG path) centered in segment
    const glyphR = (R_OUTER + R_SIGN_INNER) / 2;
    const gp = toXY(startDeg + 15, glyphR);
    const glyphPath = SIGN_GLYPH_PATHS[sign];
    if (glyphPath) {
      svg += `<g transform="translate(${gp.x},${gp.y}) scale(0.65)" opacity="0.8"><path d="${glyphPath}" fill="none" stroke="${color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></g>`;
    }
  }

  // --- Tick marks ---
  for (let d = 0; d < 360; d += 5) {
    if (d % 30 === 0) continue;
    const isMajor = d % 10 === 0;
    const len = isMajor ? 5 : 3;
    const opacity = isMajor ? 0.2 : 0.1;
    const t1 = toXY(d, R_SIGN_INNER), t2 = toXY(d, R_SIGN_INNER + len);
    svg += `<line x1="${t1.x}" y1="${t1.y}" x2="${t2.x}" y2="${t2.y}" stroke="${BRASS}" stroke-width="0.4" opacity="${opacity}"/>`;
  }

  // --- Aspect lines ---
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
    const baseOpacity = isMajor ? 0.5 : isModerate ? 0.35 : 0.2;
    const opacity = Math.max(0.1, baseOpacity * (1 - orb / 10));
    const width = isMajor ? 1.5 : isModerate ? 1.0 : 0.7;
    const dash = (!isMajor && !isModerate) ? ' stroke-dasharray="4 3"' : '';
    const p1 = toXY(lng1, R_ASPECT), p2 = toXY(lng2, R_ASPECT);
    svg += `<line x1="${p1.x}" y1="${p1.y}" x2="${p2.x}" y2="${p2.y}" stroke="${color}" stroke-width="${width}" opacity="${opacity.toFixed(2)}"${dash}/>`;
  }

  // --- Planet markers (matching TransitWheel: connector + circle + glyph) ---
  const sorted = Object.entries(positions)
    .map(([name, pos]) => ({ name, ...pos }))
    .sort((a, b) => a.longitude - b.longitude);

  // Collision avoidance — multi-pass relaxation
  const displayAngles: number[] = sorted.map(p => p.longitude);
  for (let pass = 0; pass < 8; pass++) {
    for (let i = 1; i < displayAngles.length; i++) {
      let diff = displayAngles[i] - displayAngles[i - 1];
      if (diff < 0) diff += 360;
      if (diff < MIN_DEG_SEP) {
        const nudge = (MIN_DEG_SEP - diff) / 2;
        displayAngles[i - 1] -= nudge;
        displayAngles[i] += nudge;
      }
    }
  }

  const MARKER_R = 10;
  for (let i = 0; i < sorted.length; i++) {
    const p = sorted[i];
    const sign = normalizeSign(p.sign);
    const color = SIGN_COLORS[sign] || BRASS;
    const angle = displayAngles[i];
    // Stack orbit like TransitWheel
    let clusterDepth = 0;
    for (let j = 0; j < i; j++) {
      const diff = Math.abs(displayAngles[i] - displayAngles[j]);
      if (Math.min(diff, 360 - diff) < MIN_DEG_SEP) clusterDepth++;
    }
    const orbitR = BASE_ORBIT + clusterDepth * ORBIT_STEP;
    const pt = toXY(angle, orbitR);
    const innerPt = toXY(p.longitude, R_INNER);

    // Connector line from inner ring to planet
    svg += `<line x1="${innerPt.x}" y1="${innerPt.y}" x2="${pt.x}" y2="${pt.y}" stroke="${color}" stroke-width="0.5" opacity="0.15"/>`;
    // Dark background circle
    svg += `<circle cx="${pt.x}" cy="${pt.y}" r="${MARKER_R}" fill="#080c16" stroke="${color}" stroke-width="1.2" opacity="0.9"/>`;
    // Planet glyph (SVG path)
    const nameKey = p.name.charAt(0).toUpperCase() + p.name.slice(1).toLowerCase();
    const glyphPath = PLANET_GLYPH_PATHS[nameKey] || PLANET_GLYPH_PATHS[p.name];
    if (glyphPath) {
      svg += `<g transform="translate(${pt.x},${pt.y}) scale(0.55)"><path d="${glyphPath}" fill="none" stroke="${color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></g>`;
    } else {
      // Fallback: simple dot
      svg += `<circle cx="${pt.x}" cy="${pt.y}" r="3" fill="${color}" opacity="0.8"/>`;
    }
    // Retrograde indicator
    if (p.retrograde) {
      svg += `<circle cx="${pt.x}" cy="${pt.y}" r="${MARKER_R}" fill="none" stroke="#ff6b6b" stroke-width="0.6" opacity="0.4"/>`;
    }
  }

  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${W}" width="${W}" height="${W}"><defs>${defs}</defs>${svg}</svg>`;
}

// --- Font loading ---
let interFont: Buffer | null = null;
let garamondFont: Buffer | null = null;

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

async function loadFonts(): Promise<{ inter: Buffer; garamond: Buffer }> {
  if (interFont && garamondFont) return { inter: interFont, garamond: garamondFont };
  const dir = await findFontDir();
  const [i, g] = await Promise.all([readFile(join(dir, 'Inter-400.woff')), readFile(join(dir, 'EBGaramond-400.woff'))]);
  interFont = i; garamondFont = g;
  return { inter: i, garamond: g };
}

// --- Route handler ---
export const GET: APIRoute = async ({ params }) => {
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

    // Dynamic title size
    const len = title.length;
    const titleSize = len <= 25 ? 50 : len <= 40 ? 44 : len <= 55 ? 38 : 32;

    const wheelSvg = buildWheelSvg(ephemeris);
    const wheelUri = `data:image/svg+xml;base64,${Buffer.from(wheelSvg).toString('base64')}`;

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
                  { type: 'div', props: { style: { fontSize: '12px', fontWeight: 400, letterSpacing: '0.25em', color: '#d6af72', marginBottom: '28px' }, children: 'VOIDWIREASTRO.COM' } },
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
            // Right wheel
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
