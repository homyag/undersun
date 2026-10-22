import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

export default defineConfig(({ command }) => ({
  plugins: [vue()],
  base: command === 'build' ? '/static/arealisting-app/' : '/',
  server: {
    host: '127.0.0.1',
    port: 5174,
    strictPort: true,
    cors: { origin: [/^http:\/\/(localhost|127\.0\.0\.1):8000$/] },
  },
  build: {
    outDir: '../../static/arealisting-app',
    emptyOutDir: true,
    manifest: 'manifest.json',
    rollupOptions: { input: 'src/main.ts' },
  },
}));
