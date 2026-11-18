import tailwind from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [react(), tailwind()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    proxy: { '/api': process.env.PLACEMENT_API_PROXY ?? 'http://127.0.0.1:8000' },
  },
  build: { rollupOptions: { output: { manualChunks: {
    charts: ['recharts'],
    router: ['react-router', '@tanstack/react-query'],
  } } } },
  test: { environment: 'jsdom', setupFiles: './src/testSetup.ts' },
});
