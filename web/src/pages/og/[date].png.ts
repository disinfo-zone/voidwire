import type { APIRoute } from 'astro';
import satori from 'satori';
import { Resvg } from '@resvg/resvg-js';
import { readFile, access } from 'node:fs/promises';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const API_URL = process.env.API_URL || import.meta.env.API_URL || 'http://voidwire-api:8000';

const WIDTH = 1200;
const HEIGHT = 630;

// --- Mini wheel SVG builder for OG images ---
const W = 460, WCX = W / 2, WCY = W / 2;
const R_OUTER = 210, R_SIGN_MID = 185, R_INNER = 160, R_PLANET = 135, R_ASPECT = 120;

const SIGN_COLORS: Record<string, string> = {
  Aries: '#ff8b7b', Taurus: '#e3c470', Gemini: '#f1ea86', Cancer: '#9fd2ff',
  Leo: '#ffcc6a', Virgo: '#bce68f', Libra: '#b9a3ff', Scorpio: '#df8fff',
  Sagittarius: '#ffad80', Capricorn: '#8ec5b8', Aquarius: '#90d0ff', Pisces: '#a0a6ff',
};

const ASPECT_STYLES: Record<string, { color: string; width: number; dash?: string }> = {
  conjunction: { color: '#d6c65a', width: 1.8 },
  trine: { color: '#5a8fd6', width: 1.5 },
  square: { color: '#d65a5a', width: 1.5 },
  opposition: { color: '#d6885a', width: 1.5 },
  sextile: { color: '#5ad67a', width: 1.2 },
  quincunx: { color: '#9a7ad6', width: 1.0, dash: '6 3' },
  semisquare: { color: '#d6a05a', width: 0.8, dash: '4 3' },
  sesquiquadrate: { color: '#d6a05a', width: 0.8, dash: '4 3' },
};

const SIGN_ORDER = [
  'Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
  'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces',
];

const PLANET_SIZES: Record<string, number> = {
  sun: 8, moon: 7, mercury: 5, venus: 6, mars: 6,
  jupiter: 7, saturn: 7, uranus: 5, neptune: 5, pluto: 4,
  'north node': 4, chiron: 4,
};

function toXY(longitude: number, radius: number) {
  const rad = (180 - longitude) * Math.PI / 180;
  return { x: WCX + radius * Math.cos(rad), y: WCY - radius * Math.sin(rad) };
}

function arcPath(cx: number, cy: number, r: number, startDeg: number, endDeg: number): string {
  const s = (180 - startDeg) * Math.PI / 180;
  const e = (180 - endDeg) * Math.PI / 180;
  const x1 = cx + r * Math.cos(s), y1 = cy - r * Math.sin(s);
  const x2 = cx + r * Math.cos(e), y2 = cy - r * Math.sin(e);
  const sweep = endDeg - startDeg <= 180 ? 0 : 1;
  return `M ${x1} ${y1} A ${r} ${r} 0 ${sweep} 1 ${x2} ${y2}`;
}

function normalizeSign(sign: string): string {
  const lower = sign.toLowerCase();
  return SIGN_ORDER.find(s => s.toLowerCase() === lower) || sign;
}

type EphemerisData = {
  positions?: Record<string, { sign: string; longitude: number; degree: number; retrograde: boolean }>;
  aspects?: Array<{ body1: string; body2: string; type?: string; aspect_type?: string; orb_degrees?: number; orb?: number }>;
};

function buildWheelSvg(ephemeris: EphemerisData): string {
  const positions = ephemeris.positions || {};
  const aspects = ephemeris.aspects || [];
  const BRASS = '#d6af72';

  let defs = '';
  let svg = '';

  // SVG defs: glow filter, planet glow, center gradient
  defs += `<filter id="glow"><feGaussianBlur stdDeviation="3" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>`;
  defs += `<filter id="softglow"><feGaussianBlur stdDeviation="5" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>`;
  defs += `<radialGradient id="centerglow" cx="50%" cy="50%" r="50%"><stop offset="0%" stop-color="${BRASS}" stop-opacity="0.06"/><stop offset="100%" stop-color="${BRASS}" stop-opacity="0"/></radialGradient>`;

  // Background glow
  svg += `<circle cx="${WCX}" cy="${WCY}" r="${R_INNER}" fill="url(#centerglow)"/>`;

  // Zodiac sign arcs — colored segments in the sign ring
  for (let i = 0; i < 12; i++) {
    const sign = SIGN_ORDER[i];
    const color = SIGN_COLORS[sign] || '#9aa6c0';
    const startDeg = i * 30;
    const endDeg = startDeg + 30;
    // Colored arc in the sign ring
    svg += `<path d="${arcPath(WCX, WCY, R_SIGN_MID, startDeg, endDeg)}" fill="none" stroke="${color}" stroke-width="22" opacity="0.12" stroke-linecap="butt"/>`;
    // Sign boundary radial line
    const p1 = toXY(startDeg, R_OUTER);
    const p2 = toXY(startDeg, R_INNER);
    svg += `<line x1="${p1.x}" y1="${p1.y}" x2="${p2.x}" y2="${p2.y}" stroke="${BRASS}" stroke-width="0.6" opacity="0.25"/>`;
    // Sign dot at midpoint
    const mid = toXY(startDeg + 15, R_SIGN_MID);
    svg += `<circle cx="${mid.x}" cy="${mid.y}" r="3" fill="${color}" opacity="0.5"/>`;
  }

  // Ring strokes
  svg += `<circle cx="${WCX}" cy="${WCY}" r="${R_OUTER}" fill="none" stroke="${BRASS}" stroke-width="1.2" opacity="0.4"/>`;
  svg += `<circle cx="${WCX}" cy="${WCY}" r="${R_INNER}" fill="none" stroke="${BRASS}" stroke-width="0.8" opacity="0.25"/>`;
  // Subtle inner ring
  svg += `<circle cx="${WCX}" cy="${WCY}" r="${R_ASPECT - 5}" fill="none" stroke="${BRASS}" stroke-width="0.3" opacity="0.1"/>`;

  // Aspect lines
  const posMap: Record<string, number> = {};
  for (const [name, pos] of Object.entries(positions)) {
    posMap[name.toLowerCase()] = pos.longitude;
  }
  for (const asp of aspects) {
    const type = (asp.type || asp.aspect_type || '').toLowerCase();
    const b1 = (asp.body1 || '').toLowerCase();
    const b2 = (asp.body2 || '').toLowerCase();
    const lng1 = posMap[b1];
    const lng2 = posMap[b2];
    if (lng1 == null || lng2 == null) continue;
    const style = ASPECT_STYLES[type] || { color: '#556', width: 0.8 };
    const orb = Math.abs(Number(asp.orb_degrees || asp.orb || 0));
    const opacity = Math.max(0.15, 0.7 * (1 - orb / 10));
    const p1 = toXY(lng1, R_ASPECT);
    const p2 = toXY(lng2, R_ASPECT);
    const dashAttr = style.dash ? ` stroke-dasharray="${style.dash}"` : '';
    svg += `<line x1="${p1.x}" y1="${p1.y}" x2="${p2.x}" y2="${p2.y}" stroke="${style.color}" stroke-width="${style.width}" opacity="${opacity.toFixed(2)}"${dashAttr}/>`;
  }

  // Planet markers — glowing colored dots with size based on body
  const sorted = Object.entries(positions)
    .map(([name, pos]) => ({ name, ...pos }))
    .sort((a, b) => a.longitude - b.longitude);

  // Collision avoidance — nudge clustered planets
  const displayAngles: number[] = sorted.map(p => p.longitude);
  for (let pass = 0; pass < 4; pass++) {
    for (let i = 1; i < displayAngles.length; i++) {
      let diff = displayAngles[i] - displayAngles[i - 1];
      if (diff < 0) diff += 360;
      if (diff < 8) {
        const nudge = (8 - diff) / 2;
        displayAngles[i - 1] -= nudge;
        displayAngles[i] += nudge;
      }
    }
  }

  for (let i = 0; i < sorted.length; i++) {
    const p = sorted[i];
    const sign = normalizeSign(p.sign);
    const color = SIGN_COLORS[sign] || BRASS;
    const angle = displayAngles[i];
    const r = PLANET_SIZES[p.name.toLowerCase()] || 5;
    const pt = toXY(angle, R_PLANET);
    // Outer glow
    svg += `<circle cx="${pt.x}" cy="${pt.y}" r="${r + 4}" fill="${color}" opacity="0.15" filter="url(#softglow)"/>`;
    // Dark background
    svg += `<circle cx="${pt.x}" cy="${pt.y}" r="${r}" fill="#0a0e1a" stroke="${color}" stroke-width="1.5" opacity="0.95"/>`;
    // Bright inner dot
    svg += `<circle cx="${pt.x}" cy="${pt.y}" r="${Math.max(2, r - 3)}" fill="${color}" opacity="0.85"/>`;
  }

  // Center dot
  svg += `<circle cx="${WCX}" cy="${WCY}" r="2.5" fill="${BRASS}" opacity="0.2"/>`;

  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${W}" width="${W}" height="${W}"><defs>${defs}</defs>${svg}</svg>`;
}

// Cached font buffers — loaded from bundled files (no network needed)
let interFont: Buffer | null = null;
let garamondFont: Buffer | null = null;

async function findFontDir(): Promise<string> {
  // Try multiple paths to handle different deployment layouts
  const candidates = [
    join(process.cwd(), 'dist', 'client', 'fonts'),
    join(process.cwd(), 'client', 'fonts'),
    join(dirname(fileURLToPath(import.meta.url)), '..', '..', 'client', 'fonts'),
    join(process.cwd(), 'public', 'fonts'),
  ];
  for (const dir of candidates) {
    try {
      await access(join(dir, 'Inter-400.woff'));
      return dir;
    } catch {}
  }
  throw new Error(`Fonts not found in any candidate path. cwd=${process.cwd()}, candidates=${candidates.join(', ')}`);
}

async function loadFonts(): Promise<{ inter: Buffer; garamond: Buffer }> {
  if (interFont && garamondFont) return { inter: interFont, garamond: garamondFont };

  const fontDir = await findFontDir();
  const [interBuf, garamondBuf] = await Promise.all([
    readFile(join(fontDir, 'Inter-400.woff')),
    readFile(join(fontDir, 'EBGaramond-400.woff')),
  ]);

  interFont = interBuf;
  garamondFont = garamondBuf;
  return { inter: interBuf, garamond: garamondBuf };
}

export const GET: APIRoute = async ({ params }) => {
  const dateStr = params.date;
  if (!dateStr) {
    return new Response('Not found', { status: 404 });
  }

  try {
    // Fetch reading + ephemeris + fonts in parallel
    const [readingRes, ephemRes, fonts] = await Promise.all([
      fetch(`${API_URL}/v1/reading/${dateStr}`).catch(() => null),
      fetch(`${API_URL}/v1/ephemeris/${dateStr}`).catch(() => null),
      loadFonts(),
    ]);

    const reading = readingRes?.ok ? await readingRes.json() : null;
    const ephemeris: EphemerisData = ephemRes?.ok ? await ephemRes.json() : {};

    const title = reading?.title || `Reading for ${dateStr}`;
    const subtitle = dateStr;

    // Build mini wheel as a base64 data URI for satori <img>
    const wheelSvgStr = buildWheelSvg(ephemeris);
    const wheelBase64 = `data:image/svg+xml;base64,${Buffer.from(wheelSvgStr).toString('base64')}`;

    // Satori renders virtual DOM to SVG
    const svg = await satori(
      {
        type: 'div',
        props: {
          style: {
            width: '100%',
            height: '100%',
            display: 'flex',
            background: '#060a16',
            fontFamily: 'Inter',
            position: 'relative',
          },
          children: [
            // Subtle inset border
            {
              type: 'div',
              props: {
                style: {
                  position: 'absolute',
                  top: '16px',
                  left: '16px',
                  right: '16px',
                  bottom: '16px',
                  border: '1px solid rgba(214, 175, 114, 0.12)',
                  borderRadius: '2px',
                },
              },
            },
            // Left: text content
            {
              type: 'div',
              props: {
                style: {
                  display: 'flex',
                  flexDirection: 'column' as const,
                  justifyContent: 'center',
                  padding: '60px 40px 60px 60px',
                  flex: '1',
                },
                children: [
                  {
                    type: 'div',
                    props: {
                      style: {
                        fontSize: '14px',
                        fontWeight: 400,
                        letterSpacing: '0.3em',
                        color: '#d6af72',
                        marginBottom: '24px',
                      },
                      children: 'voidwireastro.com',
                    },
                  },
                  {
                    type: 'div',
                    props: {
                      style: {
                        fontSize: '44px',
                        fontFamily: 'EB Garamond',
                        fontWeight: 400,
                        color: '#d9d4c9',
                        lineHeight: 1.2,
                        marginBottom: '20px',
                        maxWidth: '540px',
                      },
                      children: title,
                    },
                  },
                  {
                    type: 'div',
                    props: {
                      style: {
                        display: 'flex',
                        alignItems: 'center',
                        gap: '12px',
                        marginTop: '4px',
                      },
                      children: [
                        {
                          type: 'div',
                          props: {
                            style: {
                              width: '40px',
                              height: '1px',
                              background: 'rgba(214, 175, 114, 0.3)',
                            },
                          },
                        },
                        {
                          type: 'div',
                          props: {
                            style: {
                              fontSize: '13px',
                              fontWeight: 400,
                              letterSpacing: '0.2em',
                              color: '#6f6a62',
                            },
                            children: subtitle,
                          },
                        },
                      ],
                    },
                  },
                ],
              },
            },
            // Right: transit wheel
            {
              type: 'div',
              props: {
                style: {
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  width: '460px',
                  marginRight: '20px',
                },
                children: {
                  type: 'img',
                  props: {
                    src: wheelBase64,
                    width: 440,
                    height: 440,
                  },
                },
              },
            },
          ],
        },
      },
      {
        width: WIDTH,
        height: HEIGHT,
        fonts: [
          { name: 'Inter', data: fonts.inter, weight: 400, style: 'normal' as const },
          { name: 'EB Garamond', data: fonts.garamond, weight: 400, style: 'normal' as const },
        ],
      },
    );

    // SVG → PNG
    const resvg = new Resvg(svg, {
      fitTo: { mode: 'width', value: WIDTH },
    });
    const png = resvg.render().asPng();

    return new Response(png, {
      status: 200,
      headers: {
        'Content-Type': 'image/png',
        'Cache-Control': 'public, max-age=86400, s-maxage=86400',
      },
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    const stack = err instanceof Error ? err.stack : undefined;
    console.error('OG image generation failed:', message, stack);
    return new Response(JSON.stringify({ error: message }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    });
  }
};
