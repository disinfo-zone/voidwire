import type { APIRoute } from 'astro';
import { Resvg } from '@resvg/resvg-js';
import { moonIllumination, moonIsWaxing, normalizePhasePct } from '../../../utils/lunar';

function clampInt(value: number, min: number, max: number, fallback: number): number {
  if (!Number.isFinite(value)) return fallback;
  return Math.max(min, Math.min(max, Math.round(value)));
}

function phaseLabel(phasePct: number): string {
  const p = normalizePhasePct(phasePct);
  if (p < 0.0625 || p >= 0.9375) return 'New Moon';
  if (p < 0.1875) return 'Waxing Crescent';
  if (p < 0.3125) return 'First Quarter';
  if (p < 0.4375) return 'Waxing Gibbous';
  if (p < 0.5625) return 'Full Moon';
  if (p < 0.6875) return 'Waning Gibbous';
  if (p < 0.8125) return 'Last Quarter';
  return 'Waning Crescent';
}

export const GET: APIRoute = async ({ params, url }) => {
  const phaseRaw = Number.parseFloat(String(params.phase || '0'));
  const phasePct = normalizePhasePct(Number.isFinite(phaseRaw) ? phaseRaw : 0);
  const illuminationPct = Math.round(moonIllumination(phasePct) * 100);
  const waxing = moonIsWaxing(phasePct);

  const width = clampInt(Number.parseInt(url.searchParams.get('width') || '390', 10), 320, 430, 390);
  const height = clampInt(width * 0.56, 176, 260, 218);
  const moonSize = clampInt(width * 0.23, 64, 96, 84);
  const moonR = moonSize / 2;
  const moonCx = clampInt(width * 0.2, 56, 90, 78);
  const moonCy = Math.round(height / 2);
  const d = Math.cos(phasePct * 2 * Math.PI) * moonR;
  const litCx = waxing ? moonCx + d : moonCx - d;

  const titleX = moonCx + moonR + 24;
  const titleY = moonCy - 12;
  const detailY = moonCy + 14;
  const footerY = height - 18;
  const cardRadius = 10;

  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
      <defs>
        <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#0f1731" />
          <stop offset="100%" stop-color="#080c1c" />
        </linearGradient>
        <radialGradient id="moonGlow" cx="42%" cy="34%" r="65%">
          <stop offset="0%" stop-color="#e6ecf5" />
          <stop offset="100%" stop-color="#cad6e8" />
        </radialGradient>
        <clipPath id="moonClip">
          <circle cx="${moonCx}" cy="${moonCy}" r="${moonR}" />
        </clipPath>
      </defs>

      <rect x="0" y="0" width="${width}" height="${height}" rx="${cardRadius}" fill="url(#bg)" />
      <rect x="0.5" y="0.5" width="${width - 1}" height="${height - 1}" rx="${cardRadius - 0.5}" fill="none" stroke="rgba(214,175,114,0.25)" />

      <circle cx="${moonCx}" cy="${moonCy}" r="${moonR}" fill="#050913" />
      <g clip-path="url(#moonClip)">
        <circle cx="${litCx}" cy="${moonCy}" r="${moonR}" fill="url(#moonGlow)" />
      </g>
      <circle cx="${moonCx}" cy="${moonCy}" r="${moonR}" fill="none" stroke="rgba(255,255,255,0.26)" />

      <text x="${titleX}" y="${titleY}" fill="#d9d4c9" font-family="Inter, sans-serif" font-size="14" letter-spacing="0.08em" text-transform="uppercase">
        ${phaseLabel(phasePct)}
      </text>
      <text x="${titleX}" y="${detailY}" fill="#a9a39a" font-family="Inter, sans-serif" font-size="12">
        ${illuminationPct}% illuminated · ${waxing ? 'Waxing' : 'Waning'}
      </text>
      <text x="${titleX}" y="${footerY}" fill="#6f6a62" font-family="JetBrains Mono, monospace" font-size="10" letter-spacing="0.08em" text-transform="uppercase">
        mobile ${width}px snapshot
      </text>
    </svg>
  `;

  const png = new Resvg(svg, {
    fitTo: { mode: 'width', value: width },
  }).render().asPng();

  return new Response(png, {
    status: 200,
    headers: {
      'Content-Type': 'image/png',
      'Cache-Control': 'public, max-age=3600',
    },
  });
};
