import type { APIRoute } from 'astro';
import satori from 'satori';
import { Resvg } from '@resvg/resvg-js';
import { readFile } from 'node:fs/promises';
import { join } from 'node:path';

const API_URL = process.env.API_URL || import.meta.env.API_URL || 'http://voidwire-api:8000';

const WIDTH = 1200;
const HEIGHT = 630;

// --- Mini wheel SVG builder ---
const WCX = 200, WCY = 200, WR = 170, WR_INNER = 115;

const SIGN_COLORS: Record<string, string> = {
  Aries: '#ff8b7b', Taurus: '#e3c470', Gemini: '#f1ea86', Cancer: '#9fd2ff',
  Leo: '#ffcc6a', Virgo: '#bce68f', Libra: '#b9a3ff', Scorpio: '#df8fff',
  Sagittarius: '#ffad80', Capricorn: '#8ec5b8', Aquarius: '#90d0ff', Pisces: '#a0a6ff',
};

const ASPECT_COLORS: Record<string, string> = {
  conjunction: '#c8ba32', trine: '#4a7ab5', square: '#b54a4a', opposition: '#c87832',
  sextile: '#4ab56a', quincunx: '#8a6ab5', semisquare: '#b5804a', sesquiquadrate: '#b5804a',
};

const SIGN_ORDER = [
  'Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
  'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces',
];

function toXY(longitude: number, radius: number) {
  const rad = (180 - longitude) * Math.PI / 180;
  return { x: WCX + radius * Math.cos(rad), y: WCY - radius * Math.sin(rad) };
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

  let svg = '';

  // Outer and inner rings
  svg += `<circle cx="${WCX}" cy="${WCY}" r="${WR}" fill="none" stroke="${BRASS}" stroke-width="1" opacity="0.35"/>`;
  svg += `<circle cx="${WCX}" cy="${WCY}" r="${WR_INNER}" fill="none" stroke="${BRASS}" stroke-width="0.6" opacity="0.2"/>`;

  // Sign boundaries and midpoint markers
  for (let i = 0; i < 12; i++) {
    const startDeg = i * 30;
    const sign = SIGN_ORDER[i];
    const color = SIGN_COLORS[sign] || '#9aa6c0';
    const p1 = toXY(startDeg, WR);
    const p2 = toXY(startDeg, WR_INNER);
    svg += `<line x1="${p1.x}" y1="${p1.y}" x2="${p2.x}" y2="${p2.y}" stroke="${BRASS}" stroke-width="0.4" opacity="0.15"/>`;
    const mid = toXY(startDeg + 15, (WR + WR_INNER) / 2);
    svg += `<circle cx="${mid.x}" cy="${mid.y}" r="2" fill="${color}" opacity="0.3"/>`;
  }

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
    const color = ASPECT_COLORS[type] || '#555';
    const orb = Math.abs(Number(asp.orb_degrees || asp.orb || 0));
    const opacity = Math.max(0.1, 0.5 * (1 - orb / 10));
    const p1 = toXY(lng1, WR_INNER - 5);
    const p2 = toXY(lng2, WR_INNER - 5);
    svg += `<line x1="${p1.x}" y1="${p1.y}" x2="${p2.x}" y2="${p2.y}" stroke="${color}" stroke-width="0.8" opacity="${opacity.toFixed(2)}"/>`;
  }

  // Planet markers
  const sorted = Object.entries(positions)
    .map(([name, pos]) => ({ name, ...pos }))
    .sort((a, b) => a.longitude - b.longitude);

  for (let i = 0; i < sorted.length; i++) {
    const p = sorted[i];
    const sign = normalizeSign(p.sign);
    const color = SIGN_COLORS[sign] || BRASS;
    let clusterDepth = 0;
    for (let j = 0; j < i; j++) {
      const diff = Math.abs(p.longitude - sorted[j].longitude);
      if (Math.min(diff, 360 - diff) < 12) clusterDepth++;
    }
    const orbitR = 148 + clusterDepth * 16;
    const pt = toXY(p.longitude, orbitR);
    svg += `<circle cx="${pt.x}" cy="${pt.y}" r="5" fill="#080c16" stroke="${color}" stroke-width="0.8"/>`;
    svg += `<circle cx="${pt.x}" cy="${pt.y}" r="2" fill="${color}" opacity="0.7"/>`;
  }

  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400" width="400" height="400">${svg}</svg>`;
}

// Cached font buffers — loaded from bundled files (no network needed)
let interFont: Buffer | null = null;
let garamondFont: Buffer | null = null;

async function loadFonts(): Promise<{ inter: Buffer; garamond: Buffer }> {
  if (interFont && garamondFont) return { inter: interFont, garamond: garamondFont };

  // Fonts are bundled in public/fonts/ → built to dist/client/fonts/
  const clientDir = join(process.cwd(), 'dist', 'client', 'fonts');
  const [interBuf, garamondBuf] = await Promise.all([
    readFile(join(clientDir, 'Inter-400-latin.woff2')),
    readFile(join(clientDir, 'EBGaramond-400-latin.woff2')),
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
                      children: 'VOIDWIRE',
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
                  width: '420px',
                  marginRight: '30px',
                },
                children: {
                  type: 'img',
                  props: {
                    src: wheelBase64,
                    width: 380,
                    height: 380,
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
    console.error('OG image generation failed:', err);
    // Return a 1x1 transparent PNG as fallback
    return new Response(null, { status: 500 });
  }
};
