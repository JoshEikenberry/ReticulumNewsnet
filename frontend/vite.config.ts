import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import { VitePWA } from 'vite-plugin-pwa';

export default defineConfig({
  plugins: [
    svelte(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: false,  // We provide our own manifest.json in public/
      workbox: {
        // Cache app shell (JS/CSS/HTML) — cache-first
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
        // Network-first for all /api/* routes — never serve from cache
        runtimeCaching: [
          {
            urlPattern: /^\/api\//,
            handler: 'NetworkOnly',
          },
          {
            urlPattern: /^\/ws/,
            handler: 'NetworkOnly',
          },
        ],
      },
    }),
  ],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
});
