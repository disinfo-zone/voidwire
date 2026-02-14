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
    conjunction: '#c8a832',
    trine: '#4a7ab5',
    square: '#b54a4a',
    opposition: '#c87832',
    sextile: '#4ab56a',
  };

  const PLANETS = Object.keys(PLANET_GLYPHS);
  const CELL_SIZE = 44;
  const LABEL_SIZE = 36;
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
    return Math.max(0.2, 1 - aspect.orb / maxOrb);
  }

  let wrapperEl: HTMLDivElement | null = null;
  let tooltip = { visible: false, x: 0, y: 0, lines: [] as string[] };

  function showTooltip(event: MouseEvent, p1: string, p2: string) {
    const aspect = getAspect(p1, p2);
    if (!aspect || !wrapperEl) return;
    const rect = wrapperEl.getBoundingClientRect();
    const lines = [
      `${aspect.body1} ${aspect.aspect_type} ${aspect.body2}`,
      `Orb: ${aspect.orb.toFixed(1)}\u00B0 (${aspect.applying ? 'applying' : 'separating'})`,
    ];
    if (aspect.significance) {
      lines.push(`Significance: ${aspect.significance}`);
    }
    if (aspect.core_meaning) {
      lines.push(aspect.core_meaning);
    }
    if (aspect.perfects_at) {
      const perfecting = new Date(aspect.perfects_at);
      if (!Number.isNaN(perfecting.getTime())) {
        lines.push(`Perfects: ${perfecting.toLocaleString()}`);
      }
    }
    tooltip = {
      visible: true,
      x: event.clientX - rect.left + 12,
      y: event.clientY - rect.top + 12,
      lines,
    };
  }

  function hideTooltip() {
    tooltip = { ...tooltip, visible: false };
  }
</script>

<div class="transit-grid-wrapper" bind:this={wrapperEl}>
  <svg
    width={GRID_SIZE}
    height={GRID_SIZE}
    viewBox="0 0 {GRID_SIZE} {GRID_SIZE}"
    xmlns="http://www.w3.org/2000/svg"
  >
    <!-- Column labels (top) -->
    {#each PLANETS as planet, i}
      <text
        x={LABEL_SIZE + i * CELL_SIZE + CELL_SIZE / 2}
        y={LABEL_SIZE / 2 + 4}
        text-anchor="middle"
        fill="#7a756d"
        font-size="16"
        font-family="serif"
      >
        {PLANET_GLYPHS[planet]}
      </text>
    {/each}

    <!-- Row labels (left) -->
    {#each PLANETS as planet, j}
      <text
        x={LABEL_SIZE / 2}
        y={LABEL_SIZE + j * CELL_SIZE + CELL_SIZE / 2 + 5}
        text-anchor="middle"
        fill="#7a756d"
        font-size="16"
        font-family="serif"
      >
        {PLANET_GLYPHS[planet]}
      </text>
    {/each}

    <!-- Grid cells -->
    {#each PLANETS as rowPlanet, j}
      {#each PLANETS as colPlanet, i}
        {#if i !== j}
          <!-- svelte-ignore a11y-no-static-element-interactions -->
          <rect
            x={LABEL_SIZE + i * CELL_SIZE + 1}
            y={LABEL_SIZE + j * CELL_SIZE + 1}
            width={CELL_SIZE - 2}
            height={CELL_SIZE - 2}
            fill={getCellColor(rowPlanet, colPlanet)}
            opacity={getCellOpacity(rowPlanet, colPlanet)}
            rx="2"
            on:mouseenter={(e) => showTooltip(e, rowPlanet, colPlanet)}
            on:mouseleave={hideTooltip}
            style="cursor: {getAspect(rowPlanet, colPlanet) ? 'pointer' : 'default'}"
          />
        {:else}
          <rect
            x={LABEL_SIZE + i * CELL_SIZE + 1}
            y={LABEL_SIZE + j * CELL_SIZE + 1}
            width={CELL_SIZE - 2}
            height={CELL_SIZE - 2}
            fill="#0a0a0a"
            rx="2"
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
        stroke="#1a1a1a"
        stroke-width="0.5"
      />
      <line
        x1={LABEL_SIZE}
        y1={LABEL_SIZE + i * CELL_SIZE}
        x2={GRID_SIZE}
        y2={LABEL_SIZE + i * CELL_SIZE}
        stroke="#1a1a1a"
        stroke-width="0.5"
      />
    {/each}
  </svg>

  {#if tooltip.visible}
    <div
      class="tooltip"
      style="left: {tooltip.x}px; top: {tooltip.y}px;"
    >
      {#each tooltip.lines as line}
        <div class="tooltip-line">{line}</div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .transit-grid-wrapper {
    position: relative;
    display: flex;
    justify-content: center;
    padding: 2rem 0;
    overflow-x: auto;
  }

  svg {
    display: block;
  }

  .tooltip {
    position: absolute;
    background: #0a0a0a;
    border: 1px solid #1a1a1a;
    color: #d4d0c8;
    font-family: 'EB Garamond', Georgia, serif;
    font-size: 0.85rem;
    padding: 0.4rem 0.75rem;
    border-radius: 3px;
    pointer-events: none;
    white-space: normal;
    max-width: 20rem;
    z-index: 10;
    letter-spacing: 0.03em;
  }

  .tooltip-line + .tooltip-line {
    margin-top: 0.2rem;
  }
</style>
