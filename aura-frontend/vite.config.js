import { defineConfig } from 'vite';

export default defineConfig({
  base: '/monitor/',
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_AURA_API_URL || 'http://116.203.75.114:8080',
        changeOrigin: true,
      },
      '/ws': {
        target: process.env.VITE_AURA_WS_URL || 'ws://116.203.75.114:8080',
        ws: true,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: (id) => {
          if (id.includes('lightweight-charts')) return 'lightweight-charts';
        },
      },
    },
  },
});
