/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        void: '#050505',
        surface: '#0a0a09',
        'surface-raised': '#141413',
        accent: '#c8baa8',
        'text-primary': '#c0b0a0',
        'text-secondary': '#9a8a7a',
        'text-muted': '#555550',
        'text-ghost': '#302e2a',
      },
    },
  },
  plugins: [],
};
