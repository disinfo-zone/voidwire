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

  const PARTICLE_COUNT = 60;
  let particles: Particle[] = [];
  let width = 0;
  let height = 0;
  let time = 0;

  function createParticle(): Particle {
    const isBright = Math.random() > 0.95;
    return {
      x: Math.random() * width,
      y: Math.random() * height,
      vx: (Math.random() - 0.5) * 0.05,
      vy: Math.random() * 0.08 + 0.01,
      size: isBright ? Math.random() * 1.5 + 1.0 : Math.random() * 1.0 + 0.5,
      opacity: isBright ? Math.random() * 0.25 + 0.1 : Math.random() * 0.12 + 0.04,
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

    time += 0.005;
    ctx.clearRect(0, 0, width, height);
    
    // Breathing ambient light - more pronounced
    const breath = Math.sin(time) * 0.04 + 0.05;
    const grad = ctx.createRadialGradient(width/2, height/2, 0, width/2, height/2, width);
    grad.addColorStop(0, `rgba(20, 20, 30, ${breath})`);
    grad.addColorStop(1, 'rgba(3, 3, 5, 0)');
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

      // Subtle sparkle
      const sparkle = Math.sin(time * 2 + p.x) * 0.02;
      
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
      
      const glow = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.size * 2.5);
      glow.addColorStop(0, `rgba(200, 186, 168, ${Math.max(0, p.opacity + sparkle)})`);
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
