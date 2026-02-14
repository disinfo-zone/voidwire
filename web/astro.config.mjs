import { defineConfig } from 'astro/config';
import node from '@astrojs/node';
import svelte from '@astrojs/svelte';

export default defineConfig({
  output: 'server',
  adapter: node({
    mode: 'standalone',
  }),
  integrations: [svelte()],
  server: { port: 4321, host: '0.0.0.0' },
  vite: {
    server: {
      proxy: {
        '/v1': 'http://localhost:8000',
        '/health': 'http://localhost:8000',
      }
    }
  }
});
