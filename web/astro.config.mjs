import { defineConfig } from 'astro/config';
import svelte from '@astrojs/svelte';

export default defineConfig({
  output: 'server',
  integrations: [svelte()],
  server: { port: 4321, host: '0.0.0.0' },
  vite: {
    server: {
      proxy: {
        '/v1': 'http://api:8000',
        '/health': 'http://api:8000',
      }
    }
  }
});
