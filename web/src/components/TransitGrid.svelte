<script lang="ts">
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

  export let aspects: AspectInput[] = [];

  const PLANET_GLYPHS: Record<string, string> = {
    Sun: '\u2609',
    Moon: '\u263D',
    Mercury: '\u263F',
    Venus: '\u2640',
    Mars: '\u2642',
    Jupiter: '\u2643',
    Saturn: '\u2644',
    Uranus: '\u2645',
    Neptune: '\u2646',
    Pluto: '\u2647',
  };

  const ASPECT_COLORS: Record<string, string> = {
    conjunction: '#c8ba32',
    trine: '#4a7ab5',
    square: '#b54a4a',
    opposition: '#c87832',
    sextile: '#4ab56a',
  };

  const PLANETS = Object.keys(PLANET_GLYPHS);
  const CELL_SIZE = 48;
  const LABEL_SIZE = 40;
  const GRID_SIZE = PLANETS.length * CELL_SIZE + LABEL_SIZE;

  const PLANET_CASE: Record<string, string> = PLANETS.reduce((acc, planet) => {
    acc[planet.toLowerCase()] = planet;
    return acc;
  }, {} as Record<string, string>);

  function normalizePlanet(value: unknown): string {
    const raw = String(value ?? '').trim();
    if (!raw) return '';
    return PLANET_CASE[raw.toLowerCase()] || raw;
  }

  function normalizeAspectType(value: unknown): string {
    return String(value ?? '').trim().toLowerCase();
  }

  function normalizeOrb(value: unknown): number {
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) return 0;
    return Math.abs(parsed);
  }

  let normalizedAspects: AspectNormalized[] = [];
  $: normalizedAspects = (aspects || [])
    .map(
      (aspect): AspectNormalized => ({
        body1: normalizePlanet(aspect.body1),
        body2: normalizePlanet(aspect.body2),
        aspect_type: normalizeAspectType(aspect.aspect_type ?? aspect.type),
        orb: normalizeOrb(aspect.orb ?? aspect.orb_degrees),
        applying: Boolean(aspect.applying),
        significance: String(aspect.significance ?? '').trim(),
        core_meaning: String(aspect.core_meaning ?? '').trim(),
        perfects_at: aspect.perfects_at ?? null,
      })
    )
    .filter((aspect) => aspect.body1 && aspect.body2 && aspect.aspect_type);

  function getAspect(p1: string, p2: string) {
    return normalizedAspects.find(
      (a) =>
        (a.body1 === p1 && a.body2 === p2) ||
        (a.body1 === p2 && a.body2 === p1)
    );
  }

  function getCellColor(p1: string, p2: string): string {
    const aspect = getAspect(p1, p2);
    if (!aspect) return 'transparent';
    return ASPECT_COLORS[aspect.aspect_type] || '#555';
  }

  function getCellOpacity(p1: string, p2: string): number {
    const aspect = getAspect(p1, p2);
    if (!aspect) return 0;
    // Tighter orb = more opaque
    const maxOrb = 10;
    return Math.max(0.3, 1 - aspect.orb / maxOrb);
  }

  let wrapperEl: HTMLDivElement | null = null;
  let tooltip = { visible: false, x: 0, y: 0, lines: [] as string[] };

  function showTooltip(event: MouseEvent, p1: string, p2: string) {
    const aspect = getAspect(p1, p2);
    if (!aspect || !wrapperEl) return;
    const rect = wrapperEl.getBoundingClientRect();
    const lines = [
      `${aspect.body1} ${aspect.aspect_type} ${aspect.body2}`,
      `Orb: ${aspect.orb.toFixed(2)}\u00B0 (${aspect.applying ? 'applying' : 'separating'})`,
    ];
    if (aspect.significance) {
      lines.push(`${aspect.significance.toUpperCase()}`);
    }
    if (aspect.core_meaning) {
      lines.push(aspect.core_meaning);
    }
    tooltip = {
      visible: true,
      x: event.clientX - rect.left + 15,
      y: event.clientY - rect.top + 15,
      lines,
    };
  }

  function hideTooltip() {
    tooltip = { ...tooltip, visible: false };
  }
</script>

<div class="transit-grid-wrapper" bind:this={wrapperEl}>
  <div class="svg-container">
    <svg
      width="100%"
      height="100%"
      viewBox="0 0 {GRID_SIZE} {GRID_SIZE}"
      xmlns="http://www.w3.org/2000/svg"
    >
      <!-- Background -->
      <rect width={GRID_SIZE} height={GRID_SIZE} fill="var(--void)" />
      
      <!-- Column labels (top) -->
      {#each PLANETS as planet, i}
        <text
          x={LABEL_SIZE + i * CELL_SIZE + CELL_SIZE / 2}
          y={LABEL_SIZE / 2 + 5}
          text-anchor="middle"
          fill="var(--text-muted)"
          font-size="20"
          font-family="var(--font-body)"
        >
          {PLANET_GLYPHS[planet]}
        </text>
      {/each}

      <!-- Row labels (left) -->
      {#each PLANETS as planet, j}
        <text
          x={LABEL_SIZE / 2}
          y={LABEL_SIZE + j * CELL_SIZE + CELL_SIZE / 2 + 6}
          text-anchor="middle"
          fill="var(--text-muted)"
          font-size="20"
          font-family="var(--font-body)"
        >
          {PLANET_GLYPHS[planet]}
        </text>
      {/each}

      <!-- Grid cells -->
      {#each PLANETS as rowPlanet, j}
        {#each PLANETS as colPlanet, i}
          {#if i !== j}
            {@const aspect = getAspect(rowPlanet, colPlanet)}
            <!-- svelte-ignore a11y-no-static-element-interactions -->
            <rect
              x={LABEL_SIZE + i * CELL_SIZE + 2}
              y={LABEL_SIZE + j * CELL_SIZE + 2}
              width={CELL_SIZE - 4}
              height={CELL_SIZE - 4}
              fill={getCellColor(rowPlanet, colPlanet)}
              opacity={getCellOpacity(rowPlanet, colPlanet)}
              rx="1"
              on:mouseenter={(e) => showTooltip(e, rowPlanet, colPlanet)}
              on:mouseleave={hideTooltip}
              style="cursor: {aspect ? 'pointer' : 'default'}; transition: all 0.3s ease;"
              class={aspect?.applying ? 'applying' : ''}
            />
          {:else}
            <rect
              x={LABEL_SIZE + i * CELL_SIZE + 2}
              y={LABEL_SIZE + j * CELL_SIZE + 2}
              width={CELL_SIZE - 4}
              height={CELL_SIZE - 4}
              fill="var(--surface)"
              rx="1"
            />
          {/if}
        {/each}
      {/each}

      <!-- Grid lines -->
      {#each Array(PLANETS.length + 1) as _, i}
        <line
          x1={LABEL_SIZE + i * CELL_SIZE}
          y1={LABEL_SIZE}
          x2={LABEL_SIZE + i * CELL_SIZE}
          y2={GRID_SIZE}
          stroke="var(--text-ghost)"
          stroke-width="0.5"
          opacity="0.3"
        />
        <line
          x1={LABEL_SIZE}
          y1={LABEL_SIZE + i * CELL_SIZE}
          x2={GRID_SIZE}
          y2={LABEL_SIZE + i * CELL_SIZE}
          stroke="var(--text-ghost)"
          stroke-width="0.5"
          opacity="0.3"
        />
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
  .transit-grid-wrapper {
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
    border: 1px solid var(--text-ghost);
    padding: 1rem;
    background: var(--surface);
    box-shadow: 0 20px 50px rgba(0,0,0,0.5);
  }

  svg {
    display: block;
    width: 100%;
    height: 100%;
  }

  .applying {
    filter: drop-shadow(0 0 2px var(--accent-glow));
    animation: pulse 4s infinite ease-in-out;
  }

  @keyframes pulse {
    0%, 100% { opacity: 0.8; }
    50% { opacity: 1; }
  }

  .tooltip {
    position: absolute;
    background: rgba(10, 10, 10, 0.95);
    backdrop-filter: blur(8px);
    border: 1px solid var(--text-ghost);
    color: var(--text-primary);
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
    color: var(--accent);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-weight: 500;
    margin-bottom: 0.25rem;
    border-bottom: 1px solid var(--text-ghost);
    padding-bottom: 0.25rem;
  }

  .tooltip-line.sub {
    font-family: var(--font-mono);
    font-size: 0.7rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 0.5rem;
  }

  .tooltip-line.meta {
    font-size: 0.75rem;
    color: var(--accent);
    letter-spacing: 0.05em;
    margin-bottom: 0.5rem;
    font-style: italic;
  }

  .tooltip-line + .tooltip-line:not(.sub):not(.meta) {
    margin-top: 0.5rem;
    color: var(--text-secondary);
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
