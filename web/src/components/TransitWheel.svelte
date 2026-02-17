<script lang="ts">
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
  const VS15 = '\uFE0E';

  const SIGN_ORDER = [
    'Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
    'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces',
  ];

  const SIGN_GLYPHS: Record<string, string> = {
    Aries: '\u2648', Taurus: '\u2649', Gemini: '\u264A', Cancer: '\u264B',
    Leo: '\u264C', Virgo: '\u264D', Libra: '\u264E', Scorpio: '\u264F',
    Sagittarius: '\u2650', Capricorn: '\u2651', Aquarius: '\u2652', Pisces: '\u2653',
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

  const MAJOR_ASPECTS = new Set(['conjunction', 'opposition', 'square', 'trine']);
  const MODERATE_ASPECTS = new Set(['sextile', 'quincunx']);

  // --- SVG geometry ---
  const CX = 260, CY = 260;
  const R_OUTER = 250, R_SIGN_INNER = 218;
  const R_TICK = 213;
  const R_PLANET = 185;
  const R_ASPECT = 170;

  // --- Coordinate helpers ---
  function toXY(longitude: number, radius: number) {
    const rad = (180 - longitude) * Math.PI / 180;
    return { x: CX + radius * Math.cos(rad), y: CY - radius * Math.sin(rad) };
  }

  function toAngleRad(longitude: number) {
    return (180 - longitude) * Math.PI / 180;
  }

  // Arc path for zodiac segments
  function arcPath(r1: number, r2: number, startDeg: number, endDeg: number): string {
    const s1 = toXY(startDeg, r1);
    const e1 = toXY(endDeg, r1);
    const s2 = toXY(endDeg, r2);
    const e2 = toXY(startDeg, r2);
    // SVG arcs go clockwise; our longitude mapping is counter-clockwise visually
    // so sweep flags need care. We draw 30° arcs.
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

  // Normalize aspects
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

  // Build planet display data from positions dict
  type PlanetDisplay = {
    name: string;
    glyph: string;
    longitude: number;
    displayLongitude: number;
    sign: string;
    degree: number;
    speed: number;
    retrograde: boolean;
    color: string;
  };

  let planets: PlanetDisplay[] = [];
  $: {
    const raw: PlanetDisplay[] = [];
    for (const [name, pos] of Object.entries(positions || {})) {
      const normalized = normalizePlanet(name);
      const sign = normalizeSign(pos.sign);
      raw.push({
        name: normalized,
        glyph: PLANET_GLYPHS[normalized] || normalized.charAt(0),
        longitude: pos.longitude,
        displayLongitude: pos.longitude,
        sign,
        degree: pos.degree,
        speed: pos.speed_deg_day,
        retrograde: pos.retrograde,
        color: SIGN_COLORS[sign] || '#d6af72',
      });
    }
    // Sort by longitude for collision avoidance
    raw.sort((a, b) => a.longitude - b.longitude);

    // Multi-pass relaxation: nudge overlapping glyphs apart
    const MIN_SEP = 8; // minimum angular gap in degrees
    const items = raw.map((p) => ({ ...p }));
    for (let pass = 0; pass < 4; pass++) {
      for (let i = 0; i < items.length; i++) {
        for (let j = i + 1; j < items.length; j++) {
          let diff = items[j].displayLongitude - items[i].displayLongitude;
          // Wrap around 360
          if (diff < 0) diff += 360;
          if (diff > 180) continue; // too far apart
          if (diff < MIN_SEP) {
            const push = (MIN_SEP - diff) / 2;
            items[i].displayLongitude -= push;
            items[j].displayLongitude += push;
            // Normalize
            if (items[i].displayLongitude < 0) items[i].displayLongitude += 360;
            if (items[j].displayLongitude >= 360) items[j].displayLongitude -= 360;
          }
        }
      }
    }
    planets = items;
  }

  // Compute whether a planet was displaced enough to show a connecting line
  function isDisplaced(p: PlanetDisplay): boolean {
    let diff = Math.abs(p.displayLongitude - p.longitude);
    if (diff > 180) diff = 360 - diff;
    return diff > 0.5;
  }

  // --- Zodiac ring data ---
  type SignSegment = {
    sign: string;
    glyph: string;
    color: string;
    startDeg: number;
    path: string;
    glyphPos: { x: number; y: number };
  };

  let signSegments: SignSegment[] = [];
  $: signSegments = SIGN_ORDER.map((sign, i) => {
    const startDeg = i * 30;
    const midDeg = startDeg + 15;
    const glyphR = (R_OUTER + R_SIGN_INNER) / 2;
    return {
      sign,
      glyph: SIGN_GLYPHS[sign] || '',
      color: SIGN_COLORS[sign] || '#9aa6c0',
      startDeg,
      path: arcPath(R_OUTER, R_SIGN_INNER, startDeg, startDeg + 30),
      glyphPos: toXY(midDeg, glyphR),
    };
  });

  // Tick marks
  type Tick = { x1: number; y1: number; x2: number; y2: number; major: boolean };
  let ticks: Tick[] = [];
  $: {
    const t: Tick[] = [];
    for (let deg = 0; deg < 360; deg += 5) {
      const isMajor = deg % 10 === 0;
      const outerR = R_SIGN_INNER;
      const innerR = isMajor ? R_TICK - 3 : R_TICK;
      const p1 = toXY(deg, outerR);
      const p2 = toXY(deg, innerR);
      t.push({ ...p1, x2: p2.x, y2: p2.y, x1: p1.x, y1: p1.y, major: isMajor });
    }
    ticks = t;
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
  };

  let aspectLines: AspectLine[] = [];
  $: {
    const lines: AspectLine[] = [];
    const posMap: Record<string, number> = {};
    for (const p of planets) {
      posMap[p.name.toLowerCase()] = p.longitude; // true longitude for aspect anchoring
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
        dash: isMinor ? '4 3' : '',
        opacity: Math.max(0.25, 1 - asp.orb / 10),
        applying: asp.applying,
        aspect: asp,
      });
    }
    aspectLines = lines;
  }

  // --- Tooltip state ---
  let wrapperEl: HTMLDivElement | null = null;
  let tooltip = { visible: false, x: 0, y: 0, lines: [] as string[] };
  let tooltipPinned = false;

  function formatDegree(deg: number): string {
    const d = Math.floor(deg);
    const m = Math.round((deg - d) * 60);
    return `${d}\u00B0${String(m).padStart(2, '0')}'`;
  }

  function showPlanetTooltip(event: MouseEvent, planet: PlanetDisplay) {
    if (tooltipPinned) return;
    positionTooltip(event, buildPlanetLines(planet));
  }

  function buildPlanetLines(planet: PlanetDisplay): string[] {
    const lines = [
      planet.name,
      `${planet.sign} ${formatDegree(planet.degree)}`,
      `Speed: ${planet.speed.toFixed(3)}\u00B0/day${planet.retrograde ? ' (retrograde)' : ''}`,
    ];
    return lines;
  }

  function showAspectTooltip(event: MouseEvent, line: AspectLine) {
    if (tooltipPinned) return;
    const asp = line.aspect;
    const lines = [
      `${asp.body1} ${asp.aspect_type} ${asp.body2}`,
      `Orb: ${asp.orb.toFixed(2)}\u00B0 (${asp.applying ? 'applying' : 'separating'})`,
    ];
    if (asp.significance) lines.push(asp.significance.toUpperCase());
    if (asp.core_meaning) lines.push(asp.core_meaning);
    positionTooltip(event, lines);
  }

  function positionTooltip(event: MouseEvent, lines: string[]) {
    if (!wrapperEl) return;
    const rect = wrapperEl.getBoundingClientRect();
    tooltip = {
      visible: true,
      x: event.clientX - rect.left + 15,
      y: event.clientY - rect.top + 15,
      lines,
    };
  }

  function hideTooltip() {
    if (tooltipPinned) return;
    tooltip = { ...tooltip, visible: false };
  }

  // Mobile: tap toggles
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
      return;
    }
    tooltipPinned = true;
    const asp = line.aspect;
    const lines = [
      `${asp.body1} ${asp.aspect_type} ${asp.body2}`,
      `Orb: ${asp.orb.toFixed(2)}\u00B0 (${asp.applying ? 'applying' : 'separating'})`,
    ];
    if (asp.significance) lines.push(asp.significance.toUpperCase());
    if (asp.core_meaning) lines.push(asp.core_meaning);
    positionTooltip(event, lines);
  }

  function handleWrapperClick(event: MouseEvent) {
    // Dismiss pinned tooltip when tapping empty area
    const target = event.target as HTMLElement | SVGElement;
    if (tooltipPinned && !target.closest('.planet-group') && !target.closest('.aspect-hit')) {
      tooltipPinned = false;
      tooltip = { ...tooltip, visible: false };
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
      <!-- Zodiac sign ring segments -->
      {#each signSegments as seg}
        <path
          d={seg.path}
          fill="{seg.color}12"
          stroke="{seg.color}30"
          stroke-width="0.5"
        />
        <text
          x={seg.glyphPos.x}
          y={seg.glyphPos.y}
          text-anchor="middle"
          dominant-baseline="central"
          fill={seg.color}
          font-size="14"
          font-family='"Segoe UI Symbol", "EB Garamond", Georgia, serif'
        >{seg.glyph}</text>
      {/each}

      <!-- Sign boundary lines -->
      {#each boundaries as b}
        <line
          x1={b.x1} y1={b.y1} x2={b.x2} y2={b.y2}
          stroke="var(--tw-boundary)"
          stroke-width="0.8"
        />
      {/each}

      <!-- Outer and inner ring circles -->
      <circle cx={CX} cy={CY} r={R_OUTER} fill="none" stroke="var(--tw-ring)" stroke-width="1.5" />
      <circle cx={CX} cy={CY} r={R_SIGN_INNER} fill="none" stroke="var(--tw-ring)" stroke-width="1" />

      <!-- Tick marks -->
      {#each ticks as t}
        <line
          x1={t.x1} y1={t.y1} x2={t.x2} y2={t.y2}
          stroke="var(--tw-tick)"
          stroke-width={t.major ? 1 : 0.5}
          opacity={t.major ? 0.5 : 0.25}
        />
      {/each}

      <!-- Aspect lines -->
      {#each aspectLines as line}
        <!-- Invisible fat hit area -->
        <!-- svelte-ignore a11y-no-static-element-interactions -->
        <line
          class="aspect-hit"
          x1={line.x1} y1={line.y1} x2={line.x2} y2={line.y2}
          stroke="transparent"
          stroke-width="8"
          on:mouseenter={(e) => showAspectTooltip(e, line)}
          on:mouseleave={hideTooltip}
          on:click={(e) => handleAspectTap(e, line)}
          style="cursor: pointer;"
        />
        <!-- Visible aspect line -->
        <line
          x1={line.x1} y1={line.y1} x2={line.x2} y2={line.y2}
          stroke={line.color}
          stroke-width={line.width}
          stroke-dasharray={line.dash}
          opacity={line.opacity}
          class={line.applying ? 'applying' : ''}
          style="pointer-events: none;"
        />
      {/each}

      <!-- Planet orbit circle (faint reference) -->
      <circle cx={CX} cy={CY} r={R_PLANET} fill="none" stroke="var(--tw-orbit)" stroke-width="0.5" opacity="0.2" />

      <!-- Planet glyphs -->
      {#each planets as planet}
        {@const displayPos = toXY(planet.displayLongitude, R_PLANET)}
        {@const truePos = toXY(planet.longitude, R_PLANET)}
        {@const displaced = isDisplaced(planet)}

        <!-- Connecting line to true position if displaced -->
        {#if displaced}
          <line
            x1={displayPos.x} y1={displayPos.y}
            x2={truePos.x} y2={truePos.y}
            stroke="{planet.color}40"
            stroke-width="0.7"
            stroke-dasharray="2 2"
            style="pointer-events: none;"
          />
        {/if}

        <!-- svelte-ignore a11y-no-static-element-interactions -->
        <g
          class="planet-group"
          on:mouseenter={(e) => showPlanetTooltip(e, planet)}
          on:mouseleave={hideTooltip}
          on:click={(e) => handlePlanetTap(e, planet)}
          style="cursor: pointer;"
        >
          <!-- Glow behind glyph -->
          <circle
            cx={displayPos.x} cy={displayPos.y} r="12"
            fill="{planet.color}18"
            stroke="none"
          />
          <!-- Planet glyph -->
          <text
            x={displayPos.x}
            y={displayPos.y}
            text-anchor="middle"
            dominant-baseline="central"
            fill={planet.retrograde ? '#e06050' : planet.color}
            font-size="16"
            font-family='"Segoe UI Symbol", "EB Garamond", Georgia, serif'
          >{planet.glyph}</text>
          <!-- Retrograde "R" label -->
          {#if planet.retrograde}
            <text
              x={displayPos.x}
              y={displayPos.y + 12}
              text-anchor="middle"
              dominant-baseline="central"
              fill="#c04040"
              font-size="7"
              font-family='"Inter", sans-serif'
              font-weight="700"
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
    --tw-bg: #04070f;
    --tw-surface: #0b1118;
    --tw-ring: rgba(214, 175, 114, 0.35);
    --tw-boundary: rgba(214, 175, 114, 0.2);
    --tw-tick: rgba(214, 175, 114, 0.3);
    --tw-orbit: rgba(214, 175, 114, 0.15);
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
  }

  .svg-container {
    width: 100%;
    max-width: 520px;
    aspect-ratio: 1/1;
    border: 1px solid var(--tw-tooltip-border);
    padding: 1rem;
    background: var(--tw-surface);
    box-shadow: 0 20px 50px rgba(0,0,0,0.5);
  }

  svg {
    display: block;
    width: 100%;
    height: 100%;
  }

  .applying {
    animation: pulse 4s infinite ease-in-out;
  }

  @keyframes pulse {
    0%, 100% { opacity: 0.6; }
    50% { opacity: 1; }
  }

  @media (prefers-reduced-motion: reduce) {
    .applying {
      animation: none;
    }
  }

  .tooltip {
    position: absolute;
    background: var(--tw-tooltip-bg);
    backdrop-filter: blur(8px);
    border: 1px solid var(--tw-tooltip-border);
    color: var(--tw-primary);
    font-family: var(--font-body);
    font-size: 0.9rem;
    padding: 0.75rem 1rem;
    pointer-events: none;
    max-width: 22rem;
    z-index: 100;
    box-shadow: 0 10px 30px rgba(0,0,0,0.8);
  }

  .tooltip-line {
    line-height: 1.5;
  }

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
    .svg-container {
      max-width: 100%;
    }

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
