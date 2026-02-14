/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        void: 'var(--color-void)',
        surface: 'var(--color-surface)',
        'surface-raised': 'var(--color-surface-raised)',
        accent: 'var(--color-accent)',
        'text-primary': 'var(--color-text-primary)',
        'text-secondary': 'var(--color-text-secondary)',
        'text-muted': 'var(--color-text-muted)',
        'text-ghost': 'var(--color-text-ghost)',
      },
    },
  },
  plugins: [],
};
