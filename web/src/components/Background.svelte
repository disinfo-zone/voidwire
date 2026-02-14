<script lang="ts">
  import { onMount, onDestroy } from 'svelte';

  let canvas: HTMLCanvasElement;
  let animationId: number;
  let reducedMotion = false;

  interface Particle {
    x: number;
    y: number;
    vx: number;
    vy: number;
    size: number;
    baseOpacity: number;
    age: number;
    lifespan: number;
  }

  const PARTICLE_COUNT = 42;
  let particles: Particle[] = [];
  let width = 0;
  let height = 0;
  let time = 0;
  let dpr = 1;
  let lastFrameTs = 0;

  function createParticle(seedAge = true): Particle {
    const isBright = Math.random() > 0.975;
    const lifespan = 24 + Math.random() * 22;
    return {
      x: Math.random() * width,
      y: Math.random() * height,
      vx: (Math.random() - 0.5) * 4.5,
      vy: Math.random() * 8 + 2,
      size: isBright ? Math.random() * 1.1 + 0.9 : Math.random() * 0.65 + 0.35,
      baseOpacity: isBright ? Math.random() * 0.045 + 0.03 : Math.random() * 0.025 + 0.008,
      age: seedAge ? Math.random() * lifespan : 0,
      lifespan,
    };
  }

  function setCanvasSize() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
  }

  function initParticles() {
    setCanvasSize();
    particles = Array.from({ length: PARTICLE_COUNT }, createParticle);
  }

  function draw() {
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const now = performance.now();
    const dt = Math.min((now - (lastFrameTs || now)) / 1000, 0.05);
    lastFrameTs = now;
    time += dt;

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);
    
    // Slow ambient wash.
    const breath = 0.014 + Math.sin(time * 0.22) * 0.006;
    const grad = ctx.createRadialGradient(width/2, height/2, 0, width/2, height/2, width);
    grad.addColorStop(0, `rgba(200, 186, 168, ${breath})`);
    grad.addColorStop(1, 'rgba(200, 186, 168, 0)');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, width, height);

    for (let i = 0; i < particles.length; i += 1) {
      const p = particles[i];
      p.age += dt;
      if (p.age >= p.lifespan) {
        particles[i] = createParticle(false);
        continue;
      }

      p.x += p.vx * dt;
      p.y += p.vy * dt;
      if (p.y > height + 12) p.y = -12;
      if (p.x < -12) p.x = width + 12;
      if (p.x > width + 12) p.x = -12;

      // Smooth per-particle fade curve (no hard flashes).
      const phase = p.age / p.lifespan;
      const envelope = Math.sin(Math.PI * phase);
      const alpha = p.baseOpacity * Math.max(envelope, 0);

      ctx.beginPath();
      ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
      
      const glow = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.size * 2.3);
      glow.addColorStop(0, `rgba(200, 186, 168, ${alpha})`);
      glow.addColorStop(1, `rgba(200, 186, 168, 0)`);
      
      ctx.fillStyle = glow;
      ctx.fill();
    }

    animationId = requestAnimationFrame(draw);
  }

  function handleResize() {
    setCanvasSize();
  }

  onMount(() => {
    reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (reducedMotion) return;

    initParticles();
    lastFrameTs = performance.now();
    draw();

    window.addEventListener('resize', handleResize);
  });

  onDestroy(() => {
    if (animationId) {
      cancelAnimationFrame(animationId);
    }
    if (typeof window !== 'undefined') {
      window.removeEventListener('resize', handleResize);
    }
  });
</script>

{#if !reducedMotion}
  <canvas bind:this={canvas} class="background-canvas"></canvas>
{/if}

<style>
  .background-canvas {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    z-index: 0;
    opacity: 0.85;
    pointer-events: none;
  }
</style>
