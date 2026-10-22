import { defineConfig } from 'vite';

export default defineConfig({
  base: '/monitor/',
  server: {
    port: 5174,
    proxy: {
      '/api': {
        target: 'http://116.203.75.114:8000',
        changeOrigin: true,
        ws: true,
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