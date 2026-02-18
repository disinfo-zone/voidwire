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
const W = 500, CX = W / 2, CY = W / 2;
const R_OUTER = 230, R_INNER = 195, R_PLANET = 165, R_ASPECT = 130;
const R_SACRED_OUTER = 125, R_SACRED_MID = 85, R_SACRED_INNER = 45;

const SIGN_COLORS: Record<string, string> = {
  Aries: '#ff8b7b', Taurus: '#e3c470', Gemini: '#f1ea86', Cancer: '#9fd2ff',
  Leo: '#ffcc6a', Virgo: '#bce68f', Libra: '#b9a3ff', Scorpio: '#df8fff',
  Sagittarius: '#ffad80', Capricorn: '#8ec5b8', Aquarius: '#90d0ff', Pisces: '#a0a6ff',
};

const ASPECT_STYLES: Record<string, { color: string; width: number; dash?: string }> = {
  conjunction: { color: '#d6c65a', width: 1.6 },
  trine: { color: '#5a8fd6', width: 1.4 },
  square: { color: '#d65a5a', width: 1.4 },
  opposition: { color: '#d6885a', width: 1.4 },
  sextile: { color: '#5ad67a', width: 1.0 },
  quincunx: { color: '#9a7ad6', width: 0.8, dash: '5 3' },
  semisquare: { color: '#d6a05a', width: 0.6, dash: '3 3' },
  sesquiquadrate: { color: '#d6a05a', width: 0.6, dash: '3 3' },
};

const SIGN_ORDER = [
  'Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
  'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces',
];

// Planet marker sizes (radius) — luminaries largest, outer bodies smaller
const PLANET_SIZES: Record<string, number> = {
  sun: 9, moon: 8, mercury: 5.5, venus: 6.5, mars: 6.5,
  jupiter: 7.5, saturn: 7, uranus: 5.5, neptune: 5.5, pluto: 4.5,
  'north node': 4.5, chiron: 4.5,
};

function xy(longitude: number, radius: number) {
  const rad = (180 - longitude) * Math.PI / 180;
  return { x: CX + radius * Math.cos(rad), y: CY - radius * Math.sin(rad) };
}

function arcD(r: number, startDeg: number, endDeg: number): string {
  const s = (180 - startDeg) * Math.PI / 180;
  const e = (180 - endDeg) * Math.PI / 180;
  const x1 = CX + r * Math.cos(s), y1 = CY - r * Math.sin(s);
  const x2 = CX + r * Math.cos(e), y2 = CY - r * Math.sin(e);
  return `M ${x1} ${y1} A ${r} ${r} 0 0 1 ${x2} ${y2}`;
}

function normalizeSign(sign: string): string {
  return SIGN_ORDER.find(s => s.toLowerCase() === sign.toLowerCase()) || sign;
}

type EphemerisData = {
  positions?: Record<string, { sign: string; longitude: number; degree: number; retrograde: boolean }>;
  aspects?: Array<{ body1: string; body2: string; type?: string; aspect_type?: string; orb_degrees?: number; orb?: number }>;
};

// Simple SVG path glyphs for planets (designed for ~10-18px display)
function planetGlyph(name: string, cx: number, cy: number, color: string, r: number): string {
  const s = r * 0.55; // scale factor
  switch (name.toLowerCase()) {
    case 'sun':
      // Circle with central dot and 4 small rays
      return `<circle cx="${cx}" cy="${cy}" r="${s * 1.3}" fill="none" stroke="${color}" stroke-width="1.5"/>`
        + `<circle cx="${cx}" cy="${cy}" r="${s * 0.35}" fill="${color}"/>`
        + [0, 90, 180, 270].map(a => {
            const rad = a * Math.PI / 180;
            const ix = cx + Math.cos(rad) * s * 1.3, iy = cy - Math.sin(rad) * s * 1.3;
            const ox = cx + Math.cos(rad) * s * 1.9, oy = cy - Math.sin(rad) * s * 1.9;
            return `<line x1="${ix}" y1="${iy}" x2="${ox}" y2="${oy}" stroke="${color}" stroke-width="1" opacity="0.7"/>`;
          }).join('');
    case 'moon':
      // Crescent
      return `<circle cx="${cx - s * 0.25}" cy="${cy}" r="${s * 1.2}" fill="none" stroke="${color}" stroke-width="1.5"/>`
        + `<circle cx="${cx + s * 0.5}" cy="${cy}" r="${s * 1.0}" fill="#060a16" stroke="none"/>`;
    case 'venus':
      // Circle with cross below
      return `<circle cx="${cx}" cy="${cy - s * 0.4}" r="${s * 0.9}" fill="none" stroke="${color}" stroke-width="1.3"/>`
        + `<line x1="${cx}" y1="${cy + s * 0.5}" x2="${cx}" y2="${cy + s * 1.6}" stroke="${color}" stroke-width="1.2"/>`
        + `<line x1="${cx - s * 0.55}" y1="${cy + s * 1.1}" x2="${cx + s * 0.55}" y2="${cy + s * 1.1}" stroke="${color}" stroke-width="1.2"/>`;
    case 'mars':
      // Circle with arrow upper-right
      return `<circle cx="${cx - s * 0.2}" cy="${cy + s * 0.2}" r="${s * 0.9}" fill="none" stroke="${color}" stroke-width="1.3"/>`
        + `<line x1="${cx + s * 0.4}" y1="${cy - s * 0.4}" x2="${cx + s * 1.4}" y2="${cy - s * 1.4}" stroke="${color}" stroke-width="1.2"/>`
        + `<line x1="${cx + s * 0.7}" y1="${cy - s * 1.4}" x2="${cx + s * 1.4}" y2="${cy - s * 1.4}" stroke="${color}" stroke-width="1.2"/>`
        + `<line x1="${cx + s * 1.4}" y1="${cy - s * 0.7}" x2="${cx + s * 1.4}" y2="${cy - s * 1.4}" stroke="${color}" stroke-width="1.2"/>`;
    case 'jupiter':
      // Stylized "2" with cross
      return `<path d="M ${cx - s * 0.8} ${cy - s * 0.2} Q ${cx + s * 0.3} ${cy - s * 1.4} ${cx + s * 0.8} ${cy - s * 0.2} L ${cx - s * 1.0} ${cy - s * 0.2}" fill="none" stroke="${color}" stroke-width="1.3"/>`
        + `<line x1="${cx - s * 0.2}" y1="${cy - s * 1.0}" x2="${cx - s * 0.2}" y2="${cy + s * 1.2}" stroke="${color}" stroke-width="1.2"/>`
        + `<line x1="${cx - s * 0.8}" y1="${cy + s * 0.5}" x2="${cx + s * 0.4}" y2="${cy + s * 0.5}" stroke="${color}" stroke-width="1.0"/>`;
    case 'saturn':
      // Stylized "h" with cross
      return `<line x1="${cx - s * 0.3}" y1="${cy - s * 1.3}" x2="${cx - s * 0.3}" y2="${cy + s * 0.5}" stroke="${color}" stroke-width="1.3"/>`
        + `<path d="M ${cx - s * 0.3} ${cy - s * 0.3} Q ${cx + s * 1.0} ${cy - s * 0.6} ${cx + s * 0.5} ${cy + s * 0.8}" fill="none" stroke="${color}" stroke-width="1.3"/>`
        + `<line x1="${cx - s * 0.8}" y1="${cy - s * 0.9}" x2="${cx + s * 0.3}" y2="${cy - s * 0.9}" stroke="${color}" stroke-width="1.0"/>`;
    case 'mercury':
      // Circle with cross below and crescent on top
      return `<circle cx="${cx}" cy="${cy}" r="${s * 0.7}" fill="none" stroke="${color}" stroke-width="1.2"/>`
        + `<line x1="${cx}" y1="${cy + s * 0.7}" x2="${cx}" y2="${cy + s * 1.5}" stroke="${color}" stroke-width="1.1"/>`
        + `<line x1="${cx - s * 0.45}" y1="${cy + s * 1.1}" x2="${cx + s * 0.45}" y2="${cy + s * 1.1}" stroke="${color}" stroke-width="1.1"/>`
        + `<path d="M ${cx - s * 0.6} ${cy - s * 0.9} A ${s * 0.5} ${s * 0.4} 0 0 1 ${cx + s * 0.6} ${cy - s * 0.9}" fill="none" stroke="${color}" stroke-width="1.0"/>`;
    default:
      // Generic: filled circle
      return `<circle cx="${cx}" cy="${cy}" r="${s * 0.9}" fill="none" stroke="${color}" stroke-width="1.3"/>`
        + `<circle cx="${cx}" cy="${cy}" r="${s * 0.35}" fill="${color}"/>`;
  }
}

function buildWheelSvg(ephemeris: EphemerisData): string {
  const positions = ephemeris.positions || {};
  const aspects = ephemeris.aspects || [];
  const BRASS = '#d6af72';

  let defs = '';
  let svg = '';

  // Defs: glow filters
  defs += `<filter id="glow"><feGaussianBlur stdDeviation="2.5" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>`;
  defs += `<filter id="softglow"><feGaussianBlur stdDeviation="6" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>`;
  defs += `<radialGradient id="cg" cx="50%" cy="50%" r="50%"><stop offset="0%" stop-color="${BRASS}" stop-opacity="0.08"/><stop offset="60%" stop-color="${BRASS}" stop-opacity="0.03"/><stop offset="100%" stop-color="${BRASS}" stop-opacity="0"/></radialGradient>`;

  // --- Sacred geometry (innermost layer) ---
  // Center glow
  svg += `<circle cx="${CX}" cy="${CY}" r="${R_SACRED_OUTER}" fill="url(#cg)"/>`;

  // Grand cross — cardinal axis lines
  for (const deg of [0, 90, 180, 270]) {
    const p1 = xy(deg, R_SACRED_OUTER);
    const p2 = xy(deg + 180, R_SACRED_OUTER);
    svg += `<line x1="${p1.x}" y1="${p1.y}" x2="${p2.x}" y2="${p2.y}" stroke="${BRASS}" stroke-width="0.4" opacity="0.12"/>`;
  }

  // Hexagram — two interlocking triangles (Star of David / sextile pattern)
  for (const offset of [0, 30]) {
    const pts = [0, 1, 2].map(i => xy(offset + i * 120, R_SACRED_OUTER));
    svg += `<polygon points="${pts.map(p => `${p.x},${p.y}`).join(' ')}" fill="none" stroke="${BRASS}" stroke-width="0.5" opacity="0.1"/>`;
  }

  // Inner sacred circles
  svg += `<circle cx="${CX}" cy="${CY}" r="${R_SACRED_MID}" fill="none" stroke="${BRASS}" stroke-width="0.4" opacity="0.1"/>`;
  svg += `<circle cx="${CX}" cy="${CY}" r="${R_SACRED_INNER}" fill="none" stroke="${BRASS}" stroke-width="0.3" opacity="0.08"/>`;

  // 12-point star (connecting every 5th point on dodecagon)
  for (let i = 0; i < 12; i++) {
    const p1 = xy(i * 30, R_SACRED_MID);
    const p2 = xy(((i + 5) % 12) * 30, R_SACRED_MID);
    svg += `<line x1="${p1.x}" y1="${p1.y}" x2="${p2.x}" y2="${p2.y}" stroke="${BRASS}" stroke-width="0.3" opacity="0.06"/>`;
  }

  // Center point
  svg += `<circle cx="${CX}" cy="${CY}" r="2" fill="${BRASS}" opacity="0.25"/>`;

  // --- Zodiac ring ---
  // Subtle colored arcs per sign
  for (let i = 0; i < 12; i++) {
    const sign = SIGN_ORDER[i];
    const color = SIGN_COLORS[sign] || '#9aa6c0';
    const startDeg = i * 30;
    const endDeg = startDeg + 30;
    svg += `<path d="${arcD((R_OUTER + R_INNER) / 2, startDeg, endDeg)}" fill="none" stroke="${color}" stroke-width="${R_OUTER - R_INNER}" opacity="0.07" stroke-linecap="butt"/>`;
    // Boundary line
    const p1 = xy(startDeg, R_OUTER + 2);
    const p2 = xy(startDeg, R_INNER - 2);
    svg += `<line x1="${p1.x}" y1="${p1.y}" x2="${p2.x}" y2="${p2.y}" stroke="${BRASS}" stroke-width="0.5" opacity="0.2"/>`;
    // Sign indicator — bright dot at midpoint
    const mid = xy(startDeg + 15, (R_OUTER + R_INNER) / 2);
    svg += `<circle cx="${mid.x}" cy="${mid.y}" r="2.5" fill="${color}" opacity="0.6"/>`;
  }

  // Ring strokes
  svg += `<circle cx="${CX}" cy="${CY}" r="${R_OUTER}" fill="none" stroke="${BRASS}" stroke-width="1" opacity="0.35"/>`;
  svg += `<circle cx="${CX}" cy="${CY}" r="${R_INNER}" fill="none" stroke="${BRASS}" stroke-width="0.7" opacity="0.2"/>`;

  // Tick marks at 10° intervals around inner ring
  for (let d = 0; d < 360; d += 10) {
    const isMajor = d % 30 === 0;
    if (isMajor) continue; // already drawn as sign boundary
    const p1 = xy(d, R_INNER);
    const p2 = xy(d, R_INNER - 4);
    svg += `<line x1="${p1.x}" y1="${p1.y}" x2="${p2.x}" y2="${p2.y}" stroke="${BRASS}" stroke-width="0.3" opacity="0.12"/>`;
  }

  // --- Aspect lines ---
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
    const style = ASPECT_STYLES[type] || { color: '#556', width: 0.6 };
    const orb = Math.abs(Number(asp.orb_degrees || asp.orb || 0));
    const opacity = Math.max(0.12, 0.6 * (1 - orb / 10));
    const p1 = xy(lng1, R_ASPECT);
    const p2 = xy(lng2, R_ASPECT);
    const dashAttr = style.dash ? ` stroke-dasharray="${style.dash}"` : '';
    svg += `<line x1="${p1.x}" y1="${p1.y}" x2="${p2.x}" y2="${p2.y}" stroke="${style.color}" stroke-width="${style.width}" opacity="${opacity.toFixed(2)}"${dashAttr}/>`;
  }

  // --- Planet markers with glyphs ---
  const sorted = Object.entries(positions)
    .map(([name, pos]) => ({ name, ...pos }))
    .sort((a, b) => a.longitude - b.longitude);

  // Collision avoidance — multi-pass relaxation with wider gap
  const displayAngles: number[] = sorted.map(p => p.longitude);
  const MIN_GAP = 14; // degrees — must be wide enough for glyph legibility
  for (let pass = 0; pass < 8; pass++) {
    for (let i = 1; i < displayAngles.length; i++) {
      let diff = displayAngles[i] - displayAngles[i - 1];
      if (diff < 0) diff += 360;
      if (diff < MIN_GAP) {
        const nudge = (MIN_GAP - diff) / 2;
        displayAngles[i - 1] -= nudge * 0.6;
        displayAngles[i] += nudge * 0.6;
      }
    }
    // Wrap-around check (last to first)
    if (displayAngles.length > 1) {
      let diff = (displayAngles[0] + 360) - displayAngles[displayAngles.length - 1];
      if (diff < MIN_GAP) {
        const nudge = (MIN_GAP - diff) / 2;
        displayAngles[displayAngles.length - 1] -= nudge * 0.6;
        displayAngles[0] += nudge * 0.6;
      }
    }
  }

  for (let i = 0; i < sorted.length; i++) {
    const p = sorted[i];
    const sign = normalizeSign(p.sign);
    const color = SIGN_COLORS[sign] || BRASS;
    const angle = displayAngles[i];
    const r = PLANET_SIZES[p.name.toLowerCase()] || 5;
    const pt = xy(angle, R_PLANET);

    // Soft glow behind glyph
    svg += `<circle cx="${pt.x}" cy="${pt.y}" r="${r + 5}" fill="${color}" opacity="0.1" filter="url(#softglow)"/>`;
    // Glyph
    svg += planetGlyph(p.name, pt.x, pt.y, color, r);

    // Connecting line from display position to true position if nudged
    const trueAngle = p.longitude;
    const angleDiff = Math.abs(angle - trueAngle);
    if (angleDiff > 1.5) {
      const truePt = xy(trueAngle, R_INNER - 3);
      svg += `<line x1="${pt.x}" y1="${pt.y}" x2="${truePt.x}" y2="${truePt.y}" stroke="${color}" stroke-width="0.4" opacity="0.2"/>`;
    }
  }

  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${W}" width="${W}" height="${W}"><defs>${defs}</defs>${svg}</svg>`;
}

// Cached font buffers
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
    try {
      await access(join(dir, 'Inter-400.woff'));
      return dir;
    } catch {}
  }
  throw new Error(`Fonts not found. cwd=${process.cwd()}, tried=${candidates.join(', ')}`);
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
    const [readingRes, ephemRes, fonts] = await Promise.all([
      fetch(`${API_URL}/v1/reading/${dateStr}`).catch(() => null),
      fetch(`${API_URL}/v1/ephemeris/${dateStr}`).catch(() => null),
      loadFonts(),
    ]);

    const reading = readingRes?.ok ? await readingRes.json() : null;
    const ephemeris: EphemerisData = ephemRes?.ok ? await ephemRes.json() : {};

    const title = reading?.title || `Reading for ${dateStr}`;
    const subtitle = dateStr;

    // Dynamic title font size based on length
    const titleLen = title.length;
    const titleFontSize = titleLen <= 25 ? 50 : titleLen <= 40 ? 44 : titleLen <= 55 ? 38 : 32;

    const wheelSvgStr = buildWheelSvg(ephemeris);
    const wheelBase64 = `data:image/svg+xml;base64,${Buffer.from(wheelSvgStr).toString('base64')}`;

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
            // Inset border
            {
              type: 'div',
              props: {
                style: {
                  position: 'absolute',
                  top: '16px',
                  left: '16px',
                  right: '16px',
                  bottom: '16px',
                  border: '1px solid rgba(214, 175, 114, 0.1)',
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
                  padding: '60px 20px 60px 60px',
                  flex: '1',
                },
                children: [
                  {
                    type: 'div',
                    props: {
                      style: {
                        fontSize: '12px',
                        fontWeight: 400,
                        letterSpacing: '0.25em',
                        textTransform: 'uppercase' as const,
                        color: '#d6af72',
                        marginBottom: '28px',
                      },
                      children: 'VOIDWIREASTRO.COM',
                    },
                  },
                  {
                    type: 'div',
                    props: {
                      style: {
                        fontSize: `${titleFontSize}px`,
                        fontFamily: 'EB Garamond',
                        fontWeight: 400,
                        color: '#d9d4c9',
                        lineHeight: 1.2,
                        marginBottom: '24px',
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
                  width: '480px',
                  marginRight: '10px',
                },
                children: {
                  type: 'img',
                  props: {
                    src: wheelBase64,
                    width: 470,
                    height: 470,
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
