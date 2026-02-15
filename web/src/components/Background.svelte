<div class="bg-root" aria-hidden="true">
  <div class="bg-base"></div>
  <div class="bg-nebula nebula-a"></div>
  <div class="bg-nebula nebula-b"></div>
  <div class="bg-nebula nebula-c"></div>
  <div class="bg-fractal"></div>
  <div class="bg-stars"></div>
  <div class="bg-vignette"></div>
</div>

<style>
  .bg-root {
    position: fixed;
    inset: 0;
    z-index: 0;
    pointer-events: none;
    overflow: hidden;
    isolation: isolate;
  }

  .bg-root > div {
    position: absolute;
    inset: 0;
  }

  .bg-base {
    background:
      radial-gradient(112% 72% at 12% 22%, rgba(66, 88, 128, 0.32), transparent 68%),
      radial-gradient(96% 64% at 84% 14%, rgba(80, 48, 118, 0.24), transparent 72%),
      radial-gradient(90% 70% at 56% 88%, rgba(38, 68, 102, 0.28), transparent 76%),
      linear-gradient(165deg, #03050f 0%, #050814 52%, #03050c 100%);
  }

  .bg-nebula {
    filter: blur(46px) saturate(118%);
    mix-blend-mode: screen;
    opacity: 0.31;
    will-change: transform;
  }

  .nebula-a {
    background:
      radial-gradient(58% 48% at 18% 30%, rgba(132, 164, 226, 0.38), transparent 76%),
      radial-gradient(54% 44% at 62% 20%, rgba(70, 122, 172, 0.31), transparent 74%),
      radial-gradient(62% 52% at 50% 78%, rgba(109, 76, 157, 0.24), transparent 78%);
    transform: translate(-4%, -3%) scale(1.16);
    animation: cloudDriftA 82s ease-in-out infinite;
  }

  .nebula-b {
    background:
      radial-gradient(62% 46% at 74% 34%, rgba(180, 136, 84, 0.24), transparent 74%),
      radial-gradient(66% 56% at 36% 66%, rgba(93, 76, 143, 0.28), transparent 78%),
      radial-gradient(56% 40% at 14% 82%, rgba(64, 116, 132, 0.22), transparent 78%);
    transform: translate(3%, 2%) scale(1.14);
    animation: cloudDriftB 98s ease-in-out infinite;
  }

  .nebula-c {
    background:
      radial-gradient(74% 58% at 50% 42%, rgba(15, 20, 38, 0.78), transparent 82%),
      radial-gradient(48% 40% at 82% 70%, rgba(18, 26, 50, 0.66), transparent 80%);
    mix-blend-mode: multiply;
    opacity: 0.42;
    transform: scale(1.2);
    animation: cloudDriftC 110s ease-in-out infinite;
  }

  .bg-fractal {
    opacity: 0.17;
    mix-blend-mode: soft-light;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='960' height='960' viewBox='0 0 960 960'%3E%3Cfilter id='f'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.62' numOctaves='3'/%3E%3C/filter%3E%3Crect width='960' height='960' filter='url(%23f)' opacity='0.8'/%3E%3C/svg%3E");
    background-size: cover;
    background-position: center;
    background-repeat: no-repeat;
    filter: contrast(126%) brightness(56%);
    transform: scale(1.06);
    animation: noiseDrift 44s linear infinite;
    will-change: transform;
  }

  .bg-stars {
    opacity: 0.2;
    background:
      radial-gradient(circle at 9% 22%, rgba(212, 221, 255, 0.44) 0 1px, transparent 1.5px),
      radial-gradient(circle at 18% 71%, rgba(234, 210, 170, 0.28) 0 1.1px, transparent 1.6px),
      radial-gradient(circle at 31% 42%, rgba(214, 221, 255, 0.34) 0 0.9px, transparent 1.5px),
      radial-gradient(circle at 44% 84%, rgba(224, 198, 154, 0.26) 0 1px, transparent 1.5px),
      radial-gradient(circle at 56% 16%, rgba(202, 214, 255, 0.38) 0 0.9px, transparent 1.4px),
      radial-gradient(circle at 63% 58%, rgba(224, 190, 138, 0.24) 0 1px, transparent 1.5px),
      radial-gradient(circle at 74% 31%, rgba(209, 220, 255, 0.34) 0 0.9px, transparent 1.5px),
      radial-gradient(circle at 82% 76%, rgba(226, 194, 146, 0.24) 0 1px, transparent 1.5px),
      radial-gradient(circle at 92% 48%, rgba(210, 220, 255, 0.32) 0 0.9px, transparent 1.5px);
  }

  .bg-vignette {
    background: radial-gradient(circle at center, rgba(6, 10, 20, 0) 30%, rgba(2, 4, 10, 0.76) 100%);
  }

  @keyframes cloudDriftA {
    0%, 100% { transform: translate(-4%, -3%) scale(1.16); }
    50% { transform: translate(5%, 6%) scale(1.2); }
  }

  @keyframes cloudDriftB {
    0%, 100% { transform: translate(3%, 2%) scale(1.14); }
    50% { transform: translate(-6%, -4%) scale(1.2); }
  }

  @keyframes cloudDriftC {
    0%, 100% { transform: translate(0, 0) scale(1.2); }
    50% { transform: translate(2%, -3%) scale(1.24); }
  }

  @keyframes noiseDrift {
    0%, 100% { transform: translate(-1.2%, -1%) scale(1.06); }
    50% { transform: translate(1.6%, 1.4%) scale(1.08); }
  }

  @media (max-width: 900px) {
    .bg-nebula {
      filter: blur(34px) saturate(110%);
      opacity: 0.24;
    }

    .nebula-c {
      display: none;
    }

    .bg-fractal {
      animation: none;
      opacity: 0.12;
      filter: contrast(120%) brightness(58%);
    }

    .bg-stars {
      opacity: 0.14;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .bg-nebula,
    .bg-fractal {
      animation: none !important;
    }
  }
</style>
