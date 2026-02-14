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
    opacity: number;
  }

  const PARTICLE_COUNT = 80;
  let particles: Particle[] = [];
  let width = 0;
  let height = 0;

  function createParticle(): Particle {
    const isBright = Math.random() > 0.9;
    return {
      x: Math.random() * width,
      y: Math.random() * height,
      vx: (Math.random() - 0.5) * 0.1,
      vy: Math.random() * 0.15 + 0.02,
      size: isBright ? Math.random() * 1.5 + 1 : Math.random() * 1 + 0.5,
      opacity: isBright ? Math.random() * 0.2 + 0.1 : Math.random() * 0.08 + 0.02,
    };
  }

  function initParticles() {
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = width;
    canvas.height = height;
    particles = Array.from({ length: PARTICLE_COUNT }, createParticle);
  }

  function draw() {
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.clearRect(0, 0, width, height);
    
    // Add a very subtle gradient for depth
    const grad = ctx.createRadialGradient(width/2, height/2, 0, width/2, height/2, width);
    grad.addColorStop(0, 'rgba(10, 10, 12, 0)');
    grad.addColorStop(1, 'rgba(5, 5, 5, 1)');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, width, height);

    for (const p of particles) {
      p.x += p.vx;
      p.y += p.vy;

      // Wrap around edges
      if (p.y > height + 5) {
        p.y = -5;
        p.x = Math.random() * width;
      }
      if (p.x < -5) p.x = width + 5;
      if (p.x > width + 5) p.x = -5;

      ctx.beginPath();
      ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
      
      const glow = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.size * 2);
      glow.addColorStop(0, `rgba(200, 186, 168, ${p.opacity})`);
      glow.addColorStop(1, `rgba(200, 186, 168, 0)`);
      
      ctx.fillStyle = glow;
      ctx.fill();
    }

    animationId = requestAnimationFrame(draw);
  }

  function handleResize() {
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = width;
    canvas.height = height;
  }

  onMount(() => {
    reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (reducedMotion) return;

    initParticles();
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
    z-index: -1;
    pointer-events: none;
  }
</style>
