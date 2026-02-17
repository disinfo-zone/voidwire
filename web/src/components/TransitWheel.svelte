<script lang="ts">
  import { onMount } from 'svelte';

  type PlanetPosition = {
    sign: string;
    degree: number;
    longitude: number;
    speed_deg_day: number;
    retrograde: boolean;
  };

  type AspectInput = {
    body1?: string;
    body2?: string;
    aspect_type?: string;
    type?: string;
    orb?: number;
    orb_degrees?: number;
    applying?: boolean;
    significance?: string;
    core_meaning?: string;
    perfects_at?: string | null;
  };

  type AspectNormalized = {
    body1: string;
    body2: string;
    aspect_type: string;
    orb: number;
    applying: boolean;
    significance: string;
    core_meaning: string;
    perfects_at: string | null;
  };

  export let positions: Record<string, PlanetPosition> = {};
  export let aspects: AspectInput[] = [];

  // --- Constants (aligned with dashboard.astro) ---
  // VS15 forces text presentation (not emoji) for Unicode symbols
  const VS15 = '\uFE0E';
  const BRASS = '#d6af72';

  const SIGN_ORDER = [
    'Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
    'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces',
  ];

  const SIGN_ABBR: Record<string, string> = {
    Aries: 'ARI', Taurus: 'TAU', Gemini: 'GEM', Cancer: 'CAN',
    Leo: 'LEO', Virgo: 'VIR', Libra: 'LIB', Scorpio: 'SCO',
    Sagittarius: 'SAG', Capricorn: 'CAP', Aquarius: 'AQU', Pisces: 'PIS',
  };

  const SIGN_GLYPHS: Record<string, string> = {
    Aries: `\u2648${VS15}`, Taurus: `\u2649${VS15}`, Gemini: `\u264A${VS15}`, Cancer: `\u264B${VS15}`,
    Leo: `\u264C${VS15}`, Virgo: `\u264D${VS15}`, Libra: `\u264E${VS15}`, Scorpio: `\u264F${VS15}`,
    Sagittarius: `\u2650${VS15}`, Capricorn: `\u2651${VS15}`, Aquarius: `\u2652${VS15}`, Pisces: `\u2653${VS15}`,
  };

  const SIGN_COLORS: Record<string, string> = {
    Aries: '#ff8b7b', Taurus: '#e3c470', Gemini: '#f1ea86', Cancer: '#9fd2ff',
    Leo: '#ffcc6a', Virgo: '#bce68f', Libra: '#b9a3ff', Scorpio: '#df8fff',
    Sagittarius: '#ffad80', Capricorn: '#8ec5b8', Aquarius: '#90d0ff', Pisces: '#a0a6ff',
  };

  const PLANET_GLYPHS: Record<string, string> = {
    Sun: `\u2609${VS15}`, Moon: `\u263D${VS15}`, Mercury: `\u263F${VS15}`, Venus: `\u2640${VS15}`,
    Mars: `\u2642${VS15}`, Jupiter: `\u2643${VS15}`, Saturn: `\u2644${VS15}`, Uranus: `\u2645${VS15}`,
    Neptune: `\u2646${VS15}`, Pluto: `\u2647${VS15}`, Chiron: `\u26B7${VS15}`, 'North Node': `\u260A${VS15}`,
    'Part Of Fortune': `\u2297${VS15}`,
  };

  const ASPECT_COLORS: Record<string, string> = {
    conjunction: '#c8ba32',
    trine: '#4a7ab5',
    square: '#b54a4a',
    opposition: '#c87832',
    sextile: '#4ab56a',
    quincunx: '#8a6ab5',
    semisquare: '#b5804a',
    sesquiquadrate: '#b5804a',
  };

  const ASPECT_GLYPHS: Record<string, string> = {
    conjunction: `\u260C${VS15}`,
    opposition: `\u260D${VS15}`,
    trine: '\u25B3',
    square: '\u25A1',
    sextile: `\u26B9${VS15}`,
    quincunx: 'Qx',
    semisquare: '\u2220',
    sesquiquadrate: '\u2220\u00BD',
  };

  const MAJOR_ASPECTS = new Set(['conjunction', 'opposition', 'square', 'trine']);
  const MODERATE_ASPECTS = new Set(['sextile', 'quincunx']);

  // --- SVG geometry ---
  const CX = 260, CY = 260;
  const R_OUTER = 218;
  const R_SIGN_INNER = 185;
  const R_INNER = 122;
  const R_ASPECT = R_INNER - 5;
  const R_LABEL = 243;

  // Planet marker sizing
  const MARKER_R = 10;
  const GLYPH_PX = 14;
  const BASE_ORBIT = 160;
  const ORBIT_STEP = 22;
  const MIN_DEG_SEP = 12;

  // Mobile detection
  let isTouchDevice = false;
  onMount(() => {
    isTouchDevice = 'ontouchstart' in window || navigator.maxTouchPoints > 0;
  });

  // --- Coordinate helpers ---
  function toXY(longitude: number, radius: number) {
    const rad = (180 - longitude) * Math.PI / 180;
    return { x: CX + radius * Math.cos(rad), y: CY - radius * Math.sin(rad) };
  }

  function arcPath(r1: number, r2: number, startDeg: number, endDeg: number): string {
    const s1 = toXY(startDeg, r1);
    const e1 = toXY(endDeg, r1);
    const s2 = toXY(endDeg, r2);
    const e2 = toXY(startDeg, r2);
    return `M ${s1.x} ${s1.y} A ${r1} ${r1} 0 0 1 ${e1.x} ${e1.y} L ${s2.x} ${s2.y} A ${r2} ${r2} 0 0 0 ${e2.x} ${e2.y} Z`;
  }

  // --- Normalize helpers ---
  const PLANET_CASE: Record<string, string> = {};
  for (const key of Object.keys(PLANET_GLYPHS)) {
    PLANET_CASE[key.toLowerCase()] = key;
  }

  function normalizePlanet(value: unknown): string {
    const raw = String(value ?? '').trim();
    if (!raw) return '';
    return PLANET_CASE[raw.toLowerCase()] || raw;
  }

  function normalizeSign(sign: unknown): string {
    const raw = String(sign || '').trim().toLowerCase();
    return SIGN_ORDER.find((s) => s.toLowerCase() === raw) || String(sign || '').trim();
  }

  function normalizeAspectType(value: unknown): string {
    return String(value ?? '').trim().toLowerCase();
  }

  function normalizeOrb(value: unknown): number {
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) return 0;
    return Math.abs(parsed);
  }

  // --- Reactive data ---

  let normalizedAspects: AspectNormalized[] = [];
  $: normalizedAspects = (aspects || [])
    .map((a): AspectNormalized => ({
      body1: normalizePlanet(a.body1),
      body2: normalizePlanet(a.body2),
      aspect_type: normalizeAspectType(a.aspect_type ?? a.type),
      orb: normalizeOrb(a.orb ?? a.orb_degrees),
      applying: Boolean(a.applying),
      significance: String(a.significance ?? '').trim(),
      core_meaning: String(a.core_meaning ?? '').trim(),
      perfects_at: a.perfects_at ?? null,
    }))
    .filter((a) => a.body1 && a.body2 && a.aspect_type);

  // Planet display data with radial fan-out collision avoidance
  type PlanetDisplay = {
    name: string;
    glyph: string;
    longitude: number;
    sign: string;
    degree: number;
    speed: number;
    retrograde: boolean;
    color: string;
    orbitR: number;
    pos: { x: number; y: number };
  };

  let planets: PlanetDisplay[] = [];
  $: {
    const raw: { name: string; glyph: string; longitude: number; sign: string; degree: number; speed: number; retrograde: boolean; color: string }[] = [];
    for (const [name, pos] of Object.entries(positions || {})) {
      const normalized = normalizePlanet(name);
      const sign = normalizeSign(pos.sign);
      raw.push({
        name: normalized,
        glyph: PLANET_GLYPHS[normalized] || normalized.charAt(0),
        longitude: pos.longitude,
        sign,
        degree: pos.degree,
        speed: pos.speed_deg_day,
        retrograde: pos.retrograde,
        color: SIGN_COLORS[sign] || BRASS,
      });
    }
    raw.sort((a, b) => a.longitude - b.longitude);

    const displayed: PlanetDisplay[] = raw.map((p, idx) => {
      let clusterDepth = 0;
      for (let j = 0; j < idx; j++) {
        const diff = Math.abs(p.longitude - raw[j].longitude);
        if (Math.min(diff, 360 - diff) < MIN_DEG_SEP) clusterDepth++;
      }
      const orbitR = BASE_ORBIT + clusterDepth * ORBIT_STEP;
      const pos = toXY(p.longitude, orbitR);
      return { ...p, orbitR, pos };
    });
    planets = displayed;
  }

  // --- Sacred geometry ---
  type GeoLine = { x1: number; y1: number; x2: number; y2: number };

  let sacredTriangles: string[] = [];
  $: {
    const tris: string[] = [];
    const sacredR = R_INNER * 0.88;
    for (let k = 0; k < 2; k++) {
      let path = '';
      for (let i = 0; i < 3; i++) {
        const a = ((i * 120 + k * 60) * Math.PI) / 180;
        const x = CX + Math.cos(a) * sacredR;
        const y = CY + Math.sin(a) * sacredR;
        path += i === 0 ? `M ${x} ${y}` : ` L ${x} ${y}`;
      }
      path += ' Z';
      tris.push(path);
    }
    sacredTriangles = tris;
  }

  let goldenCircles: number[] = [];
  $: {
    const phi = 1.618033988749;
    const circles: number[] = [];
    for (let i = 1; i <= 4; i++) {
      const r = R_INNER * 0.15 * Math.pow(phi, i);
      if (r < R_OUTER) circles.push(r);
    }
    goldenCircles = circles;
  }

  let sacredRadials: GeoLine[] = [];
  $: {
    const lines: GeoLine[] = [];
    for (let deg = 0; deg < 360; deg += 15) {
      const a = (deg * Math.PI) / 180;
      lines.push({
        x1: CX + Math.cos(a) * R_INNER * 0.3,
        y1: CY + Math.sin(a) * R_INNER * 0.3,
        x2: CX + Math.cos(a) * R_INNER * 0.85,
        y2: CY + Math.sin(a) * R_INNER * 0.85,
      });
    }
    sacredRadials = lines;
  }

  // --- Zodiac ring data ---
  type SignSegment = {
    sign: string;
    glyph: string;
    abbr: string;
    color: string;
    startDeg: number;
    path: string;
    glyphPos: { x: number; y: number };
    labelPos: { x: number; y: number };
  };

  let signSegments: SignSegment[] = [];
  $: signSegments = SIGN_ORDER.map((sign, i) => {
    const startDeg = i * 30;
    const midDeg = startDeg + 15;
    const glyphR = (R_OUTER + R_SIGN_INNER) / 2;
    return {
      sign,
      glyph: SIGN_GLYPHS[sign] || '',
      abbr: SIGN_ABBR[sign] || sign.slice(0, 3).toUpperCase(),
      color: SIGN_COLORS[sign] || '#9aa6c0',
      startDeg,
      path: arcPath(R_OUTER, R_SIGN_INNER, startDeg, startDeg + 30),
      glyphPos: toXY(midDeg, glyphR),
      labelPos: toXY(midDeg, R_LABEL),
    };
  });

  // Fine tick marks
  type Tick = { x1: number; y1: number; x2: number; y2: number; weight: 'major' | 'minor' | 'fine' };

  let innerTicks: Tick[] = [];
  $: {
    const t: Tick[] = [];
    for (let deg = 0; deg < 360; deg++) {
      const isMaj = deg % 10 === 0;
      const isMin = deg % 5 === 0;
      const tickLen = isMaj ? 4 : isMin ? 2.5 : 1;
      const p1 = toXY(deg, R_SIGN_INNER);
      const p2 = toXY(deg, R_SIGN_INNER - tickLen);
      t.push({
        x1: p1.x, y1: p1.y, x2: p2.x, y2: p2.y,
        weight: isMaj ? 'major' : isMin ? 'minor' : 'fine',
      });
    }
    innerTicks = t;
  }

  let outerTicks: Tick[] = [];
  $: {
    const t: Tick[] = [];
    for (let deg = 0; deg < 360; deg++) {
      const isMaj = deg % 10 === 0;
      const isMin = deg % 5 === 0;
      const tickLen = isMaj ? 3.5 : isMin ? 2 : 1;
      const p1 = toXY(deg, R_OUTER);
      const p2 = toXY(deg, R_OUTER + tickLen);
      t.push({
        x1: p1.x, y1: p1.y, x2: p2.x, y2: p2.y,
        weight: isMaj ? 'major' : isMin ? 'minor' : 'fine',
      });
    }
    outerTicks = t;
  }

  // Sign boundary lines
  type BoundaryLine = { x1: number; y1: number; x2: number; y2: number };
  let boundaries: BoundaryLine[] = [];
  $: boundaries = SIGN_ORDER.map((_, i) => {
    const deg = i * 30;
    const p1 = toXY(deg, R_OUTER);
    const p2 = toXY(deg, R_SIGN_INNER);
    return { x1: p1.x, y1: p1.y, x2: p2.x, y2: p2.y };
  });

  // Aspect lines
  type AspectLine = {
    x1: number; y1: number; x2: number; y2: number;
    color: string;
    width: number;
    dash: string;
    opacity: number;
    applying: boolean;
    aspect: AspectNormalized;
    id: string;
  };

  let aspectLines: AspectLine[] = [];
  $: {
    const lines: AspectLine[] = [];
    const posMap: Record<string, number> = {};
    for (const p of planets) {
      posMap[p.name.toLowerCase()] = p.longitude;
    }
    for (const asp of normalizedAspects) {
      const lng1 = posMap[asp.body1.toLowerCase()];
      const lng2 = posMap[asp.body2.toLowerCase()];
      if (lng1 == null || lng2 == null) continue;
      const p1 = toXY(lng1, R_ASPECT);
      const p2 = toXY(lng2, R_ASPECT);
      const isMajor = MAJOR_ASPECTS.has(asp.aspect_type);
      const isModerate = MODERATE_ASPECTS.has(asp.aspect_type);
      const isMinor = !isMajor && !isModerate;
      lines.push({
        x1: p1.x, y1: p1.y, x2: p2.x, y2: p2.y,
        color: ASPECT_COLORS[asp.aspect_type] || '#555',
        width: isMajor ? 1.5 : isModerate ? 1 : 0.7,
        dash: isMinor ? '4 3' : (asp.applying ? '' : '6 4'),
        opacity: Math.max(0.15, 0.7 * (1 - asp.orb / 10)),
        applying: asp.applying,
        aspect: asp,
        id: `${asp.body1}-${asp.aspect_type}-${asp.body2}`,
      });
    }
    aspectLines = lines;
  }

  // --- Tooltip + hover state ---
  let wrapperEl: HTMLDivElement | null = null;
  let tooltip = { visible: false, x: 0, y: 0, lines: [] as string[] };
  let tooltipPinned = false;
  let hoveredAspectId: string | null = null;

  function formatDegree(deg: number): string {
    const d = Math.floor(deg);
    const m = Math.round((deg - d) * 60);
    return `${d}\u00B0${String(m).padStart(2, '0')}'`;
  }

  function buildPlanetLines(planet: PlanetDisplay): string[] {
    const signGlyph = SIGN_GLYPHS[planet.sign] || '';
    return [
      planet.name,
      `${signGlyph} ${planet.sign} ${formatDegree(planet.degree)}`,
      `Speed: ${planet.speed.toFixed(3)}\u00B0/day${planet.retrograde ? ' \u00B7 Retrograde' : ''}`,
    ];
  }

  function buildAspectLines(asp: AspectNormalized): string[] {
    const glyph = ASPECT_GLYPHS[asp.aspect_type] || '';
    const label = asp.aspect_type.charAt(0).toUpperCase() + asp.aspect_type.slice(1);
    const lines = [
      `${asp.body1} ${glyph} ${label} ${asp.body2}`,
      `Orb: ${asp.orb.toFixed(2)}\u00B0 (${asp.applying ? 'applying' : 'separating'})`,
    ];
    if (asp.significance) lines.push(asp.significance.toUpperCase());
    if (asp.core_meaning) lines.push(asp.core_meaning);
    return lines;
  }

  function positionTooltip(event: MouseEvent | Touch, lines: string[]) {
    if (!wrapperEl) return;
    const rect = wrapperEl.getBoundingClientRect();
    const clientX = event.clientX;
    const clientY = event.clientY;
    tooltip = {
      visible: true,
      x: clientX - rect.left + 15,
      y: clientY - rect.top + 15,
      lines,
    };
  }

  function hideTooltip() {
    if (tooltipPinned) return;
    tooltip = { ...tooltip, visible: false };
    hoveredAspectId = null;
  }

  // Desktop: hover
  function showPlanetTooltip(event: MouseEvent, planet: PlanetDisplay) {
    if (tooltipPinned) return;
    positionTooltip(event, buildPlanetLines(planet));
  }

  function showAspectTooltip(event: MouseEvent, line: AspectLine) {
    if (tooltipPinned) return;
    hoveredAspectId = line.id;
    positionTooltip(event, buildAspectLines(line.aspect));
  }

  function onAspectLeave() {
    hoveredAspectId = null;
    hideTooltip();
  }

  // Mobile + desktop: tap/click toggles pinned tooltip
  function handlePlanetTap(event: MouseEvent, planet: PlanetDisplay) {
    if (tooltipPinned) {
      tooltipPinned = false;
      tooltip = { ...tooltip, visible: false };
      return;
    }
    tooltipPinned = true;
    positionTooltip(event, buildPlanetLines(planet));
  }

  function handleAspectTap(event: MouseEvent, line: AspectLine) {
    if (tooltipPinned) {
      tooltipPinned = false;
      tooltip = { ...tooltip, visible: false };
      hoveredAspectId = null;
      return;
    }
    tooltipPinned = true;
    hoveredAspectId = line.id;
    positionTooltip(event, buildAspectLines(line.aspect));
  }

  // Mobile: touchstart shows tooltip immediately (before click fires)
  function handlePlanetTouch(event: TouchEvent, planet: PlanetDisplay) {
    if (!isTouchDevice) return;
    event.preventDefault();
    const touch = event.touches[0];
    if (!touch) return;
    if (tooltipPinned) {
      tooltipPinned = false;
      tooltip = { ...tooltip, visible: false };
      return;
    }
    tooltipPinned = true;
    positionTooltip(touch, buildPlanetLines(planet));
  }

  function handleAspectTouch(event: TouchEvent, line: AspectLine) {
    if (!isTouchDevice) return;
    event.preventDefault();
    const touch = event.touches[0];
    if (!touch) return;
    if (tooltipPinned) {
      tooltipPinned = false;
      tooltip = { ...tooltip, visible: false };
      hoveredAspectId = null;
      return;
    }
    tooltipPinned = true;
    hoveredAspectId = line.id;
    positionTooltip(touch, buildAspectLines(line.aspect));
  }

  function handleWrapperClick(event: MouseEvent) {
    const target = event.target as HTMLElement | SVGElement;
    if (tooltipPinned && !target.closest('.planet-group') && !target.closest('.aspect-hit')) {
      tooltipPinned = false;
      tooltip = { ...tooltip, visible: false };
      hoveredAspectId = null;
    }
  }
</script>

<!-- svelte-ignore a11y-click-events-have-key-events -->
<!-- svelte-ignore a11y-no-static-element-interactions -->
<div class="transit-wheel-wrapper" bind:this={wrapperEl} on:click={handleWrapperClick}>
  <div class="svg-container">
    <svg
      width="100%"
      height="100%"
      viewBox="0 0 520 520"
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <clipPath id="tw-circle-clip">
          <circle cx={CX} cy={CY} r={R_OUTER + 1} />
        </clipPath>

        <radialGradient id="tw-bg-grad" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stop-color="#0a1228" />
          <stop offset="80%" stop-color="#080510" />
          <stop offset="100%" stop-color="#06040d" />
        </radialGradient>

        <radialGradient id="tw-nebula-1" cx="35%" cy="40%" r="55%">
          <stop offset="0%" stop-color="rgba(70, 110, 180, 0.12)" />
          <stop offset="50%" stop-color="rgba(70, 110, 180, 0.04)" />
          <stop offset="100%" stop-color="rgba(0,0,0,0)" />
        </radialGradient>
        <radialGradient id="tw-nebula-2" cx="65%" cy="55%" r="50%">
          <stop offset="0%" stop-color="rgba(180, 145, 80, 0.10)" />
          <stop offset="50%" stop-color="rgba(180, 145, 80, 0.03)" />
          <stop offset="100%" stop-color="rgba(0,0,0,0)" />
        </radialGradient>
        <radialGradient id="tw-nebula-3" cx="45%" cy="65%" r="50%">
          <stop offset="0%" stop-color="rgba(90, 50, 130, 0.10)" />
          <stop offset="50%" stop-color="rgba(90, 50, 130, 0.03)" />
          <stop offset="100%" stop-color="rgba(0,0,0,0)" />
        </radialGradient>

        <radialGradient id="tw-ambient-glow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stop-color="rgba(100, 130, 200, 0.08)" />
          <stop offset="60%" stop-color="rgba(214, 175, 114, 0.04)" />
          <stop offset="100%" stop-color="rgba(0,0,0,0)" />
        </radialGradient>
      </defs>

      <!-- Ambient glow halo -->
      <circle cx={CX} cy={CY} r={R_OUTER + 40} fill="url(#tw-ambient-glow)" />

      <!-- Interior atmosphere, clipped to ring -->
      <g clip-path="url(#tw-circle-clip)">
        <rect width="520" height="520" fill="url(#tw-bg-grad)" />
        <rect width="520" height="520" fill="url(#tw-nebula-1)" />
        <rect width="520" height="520" fill="url(#tw-nebula-2)" />
        <rect width="520" height="520" fill="url(#tw-nebula-3)" />
      </g>

      <!-- Sacred geometry (slow rotation adds living feel) -->
      <g class="sacred-geometry" opacity="0.055" stroke="{BRASS}" fill="none" stroke-width="0.5">
        {#each sacredTriangles as path}
          <path d={path} />
        {/each}
        {#each goldenCircles as r}
          <circle cx={CX} cy={CY} {r} />
        {/each}
        {#each sacredRadials as line}
          <line x1={line.x1} y1={line.y1} x2={line.x2} y2={line.y2} />
        {/each}
      </g>

      <!-- Wheel structure rings -->
      <circle cx={CX} cy={CY} r={R_INNER} fill="none" stroke="{BRASS}" stroke-width="1" opacity="0.4" />
      <circle cx={CX} cy={CY} r={R_SIGN_INNER} fill="none" stroke="{BRASS}" stroke-width="0.8" opacity="0.35" />
      <circle cx={CX} cy={CY} r={R_OUTER} fill="none" stroke="{BRASS}" stroke-width="1.2" opacity="0.5" />

      <!-- Zodiac sign ring segments -->
      {#each signSegments as seg}
        <path d={seg.path} fill="{seg.color}10" stroke="none" />
        <text
          x={seg.glyphPos.x} y={seg.glyphPos.y}
          text-anchor="middle" dominant-baseline="central"
          fill={seg.color} font-size="16"
          font-family='"Segoe UI Symbol", "EB Garamond", Georgia, serif'
          opacity="0.9"
        >{seg.glyph}</text>
        <text
          x={seg.labelPos.x} y={seg.labelPos.y}
          text-anchor="middle" dominant-baseline="central"
          fill={seg.color} font-size="8"
          font-family='"Inter", sans-serif' font-weight="600"
          opacity="0.5"
        >{seg.abbr}</text>
      {/each}

      <!-- Sign boundary lines -->
      {#each boundaries as b}
        <line x1={b.x1} y1={b.y1} x2={b.x2} y2={b.y2}
          stroke="{BRASS}" stroke-width="0.5" opacity="0.2" />
      {/each}

      <!-- Inner tick marks -->
      {#each innerTicks as t}
        <line x1={t.x1} y1={t.y1} x2={t.x2} y2={t.y2}
          stroke="{BRASS}"
          stroke-width={t.weight === 'major' ? 0.8 : t.weight === 'minor' ? 0.5 : 0.3}
          opacity={t.weight === 'major' ? 0.3 : t.weight === 'minor' ? 0.15 : 0.08}
        />
      {/each}

      <!-- Outer tick marks -->
      {#each outerTicks as t}
        <line x1={t.x1} y1={t.y1} x2={t.x2} y2={t.y2}
          stroke="{BRASS}"
          stroke-width={t.weight === 'major' ? 0.7 : t.weight === 'minor' ? 0.4 : 0.25}
          opacity={t.weight === 'major' ? 0.25 : t.weight === 'minor' ? 0.12 : 0.06}
        />
      {/each}

      <!-- Aspect web -->
      {#each aspectLines as line}
        <!-- svelte-ignore a11y-no-static-element-interactions -->
        <line
          class="aspect-hit"
          x1={line.x1} y1={line.y1} x2={line.x2} y2={line.y2}
          stroke="transparent" stroke-width="10"
          on:mouseenter={(e) => showAspectTooltip(e, line)}
          on:mouseleave={onAspectLeave}
          on:click={(e) => handleAspectTap(e, line)}
          on:touchstart={(e) => handleAspectTouch(e, line)}
          style="cursor: pointer;"
        />
        <line
          class="aspect-line {line.applying ? 'applying' : ''}"
          x1={line.x1} y1={line.y1} x2={line.x2} y2={line.y2}
          stroke={line.color}
          stroke-width={hoveredAspectId === line.id ? line.width + 1 : line.width}
          stroke-dasharray={line.dash}
          opacity={hoveredAspectId === line.id ? Math.min(1, line.opacity + 0.3) : line.opacity}
          style="pointer-events: none; transition: opacity 0.2s ease, stroke-width 0.2s ease;"
        />
      {/each}

      <!-- Planet markers -->
      {#each planets as planet}
        {@const innerPt = toXY(planet.longitude, R_INNER)}

        <!-- Tick line from inner ring to marker -->
        <line
          x1={innerPt.x} y1={innerPt.y} x2={planet.pos.x} y2={planet.pos.y}
          stroke="{planet.color}" stroke-width="0.5" opacity="0.3"
          style="pointer-events: none;"
        />

        <!-- svelte-ignore a11y-no-static-element-interactions -->
        <g
          class="planet-group"
          on:mouseenter={(e) => showPlanetTooltip(e, planet)}
          on:mouseleave={hideTooltip}
          on:click={(e) => handlePlanetTap(e, planet)}
          on:touchstart={(e) => handlePlanetTouch(e, planet)}
          style="cursor: pointer;"
        >
          <!-- Larger invisible hit area for touch -->
          <circle
            cx={planet.pos.x} cy={planet.pos.y} r={MARKER_R + 8}
            fill="transparent"
          />
          <!-- Soft glow halo -->
          <circle
            cx={planet.pos.x} cy={planet.pos.y} r={MARKER_R + 6}
            fill="{planet.color}" opacity="0.1"
          />
          <!-- Marker circle background -->
          <circle
            cx={planet.pos.x} cy={planet.pos.y} r={MARKER_R}
            fill="#080c16"
          />
          <!-- Marker circle border -->
          <circle
            class="marker-ring"
            cx={planet.pos.x} cy={planet.pos.y} r={MARKER_R}
            fill="none" stroke={planet.color} stroke-width="1.2"
          />
          <!-- Planet glyph -->
          <text
            x={planet.pos.x} y={planet.pos.y}
            text-anchor="middle" dominant-baseline="central"
            fill={planet.color} font-size={GLYPH_PX}
            font-family='"Segoe UI Symbol", "EB Garamond", Georgia, serif'
          >{planet.glyph}</text>

          <!-- Retrograde badge -->
          {#if planet.retrograde}
            <circle
              cx={planet.pos.x + MARKER_R + 3} cy={planet.pos.y - MARKER_R + 1}
              r="4.5" fill="#c04040"
            />
            <text
              x={planet.pos.x + MARKER_R + 3} y={planet.pos.y - MARKER_R + 1}
              text-anchor="middle" dominant-baseline="central"
              fill="#f0e8e0" font-size="6"
              font-family='"Inter", sans-serif' font-weight="700"
            >R</text>
          {/if}
        </g>
      {/each}
    </svg>
  </div>

  {#if tooltip.visible}
    <div
      class="tooltip"
      style="left: {tooltip.x}px; top: {tooltip.y}px;"
    >
      {#each tooltip.lines as line, i}
        <div class="tooltip-line" class:header={i === 0} class:sub={i === 1} class:meta={i === 2}>
          {line}
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .transit-wheel-wrapper {
    --tw-tooltip-bg: rgba(6, 8, 14, 0.95);
    --tw-tooltip-border: #2a323f;
    --tw-primary: #d9d4c9;
    --tw-secondary: #a9a39a;
    --tw-accent: #d6af72;
    --tw-muted: #737d8c;
    color-scheme: dark;
    forced-color-adjust: none;
    position: relative;
    display: flex;
    justify-content: center;
    padding: 3rem 0;
    width: 100%;
    animation: tw-reveal 1.2s ease-out both;
  }

  @keyframes tw-reveal {
    from { opacity: 0; transform: scale(0.92); }
    to { opacity: 1; transform: scale(1); }
  }

  .svg-container {
    width: 100%;
    max-width: 520px;
    aspect-ratio: 1/1;
  }

  svg {
    display: block;
    width: 100%;
    height: 100%;
    overflow: visible;
    -webkit-tap-highlight-color: transparent;
  }

  /* Sacred geometry slow rotation */
  .sacred-geometry {
    transform-origin: 260px 260px;
    animation: tw-sacred-rotate 120s linear infinite;
  }

  @keyframes tw-sacred-rotate {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }

  /* Planet hover */
  .planet-group {
    transition: filter 0.2s ease;
  }

  .planet-group:hover {
    filter: brightness(1.3);
  }

  /* Aspect pulse */
  .applying {
    animation: pulse 4s infinite ease-in-out;
  }

  @keyframes pulse {
    0%, 100% { opacity: 0.5; }
    50% { opacity: 1; }
  }

  @media (prefers-reduced-motion: reduce) {
    .applying { animation: none; }
    .transit-wheel-wrapper { animation: none; }
    .sacred-geometry { animation: none; }
  }

  /* Tooltip */
  .tooltip {
    position: absolute;
    background: var(--tw-tooltip-bg);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid var(--tw-tooltip-border);
    border-radius: 4px;
    color: var(--tw-primary);
    font-family: var(--font-body);
    font-size: 0.9rem;
    padding: 0.75rem 1rem;
    pointer-events: none;
    max-width: 22rem;
    z-index: 100;
    box-shadow:
      0 4px 20px rgba(0, 0, 0, 0.6),
      0 0 40px rgba(100, 130, 200, 0.06);
    animation: tw-tooltip-in 0.15s ease-out;
  }

  @keyframes tw-tooltip-in {
    from { opacity: 0; transform: translateY(4px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .tooltip-line { line-height: 1.5; }

  .tooltip-line.header {
    color: var(--tw-accent);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-weight: 500;
    margin-bottom: 0.25rem;
    border-bottom: 1px solid var(--tw-tooltip-border);
    padding-bottom: 0.25rem;
  }

  .tooltip-line.sub {
    font-family: var(--font-mono);
    font-size: 0.7rem;
    color: var(--tw-muted);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 0.5rem;
  }

  .tooltip-line.meta {
    font-size: 0.75rem;
    color: var(--tw-accent);
    letter-spacing: 0.05em;
    margin-bottom: 0.5rem;
    font-style: italic;
  }

  .tooltip-line + .tooltip-line:not(.sub):not(.meta) {
    margin-top: 0.5rem;
    color: var(--tw-secondary);
  }

  @media (max-width: 600px) {
    .svg-container { max-width: 100%; }

    .tooltip {
      position: fixed;
      bottom: 1rem;
      left: 1rem;
      right: 1rem;
      max-width: none;
      top: auto !important;
      left: auto !important;
    }
  }
</style>
