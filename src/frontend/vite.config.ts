import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

export default defineConfig({
  plugins: [svelte()],
  server: {
    port: 5174,
    proxy: {
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          const normalized = id.replace(/\\/g, '/');
          if (normalized.includes('/node_modules/@codemirror/lang-')) {
            return 'codemirror-languages';
          }
          if (normalized.includes('/node_modules/@codemirror/') || normalized.includes('/node_modules/codemirror/')) {
            return 'codemirror-core';
          }
          if (
            normalized.includes('/node_modules/highlight.js/') ||
            normalized.includes('/node_modules/marked/') ||
            normalized.includes('/node_modules/papaparse/')
          ) {
            return 'viewer-vendors';
          }
          if (normalized.includes('/node_modules/lucide-svelte/')) {
            return 'icons';
          }
          if (normalized.includes('/node_modules/svelte/') || normalized.includes('/node_modules/svelte-spa-router/')) {
            return 'svelte-vendors';
          }
        },
      },
    },
  },
});
