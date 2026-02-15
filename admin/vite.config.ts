import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  base: '/admin/',
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      '/admin': 'http://localhost:8000',
      '/setup': 'http://localhost:8000',
      '/v1': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
  },
});
