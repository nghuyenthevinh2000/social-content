import legacy from '@vitejs/plugin-legacy';
import react from '@vitejs/plugin-react';
import { loadEnv } from 'vite';
import { defineConfig } from 'vitest/config';

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const firebaseAuthDomain = env.VITE_FIREBASE_AUTH_DOMAIN;

  return {
    plugins: [react(), legacy()],
    server: {
      host: '0.0.0.0',
      port: 8100,
      allowedHosts: true,
      proxy: {
        ...(firebaseAuthDomain
          ? {
              '/__/auth': {
                target: `https://${firebaseAuthDomain}`,
                changeOrigin: true,
              },
              '/__/firebase': {
                target: `https://${firebaseAuthDomain}`,
                changeOrigin: true,
              },
            }
          : {}),
        '/api': {
          target: 'http://127.0.0.1:8765',
          configure: (proxy) => {
            proxy.on('error', (_err, _req, res) => {
              if ('writeHead' in res && !res.headersSent) {
                res.writeHead(502, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ error: 'Backend chưa chạy (127.0.0.1:8765)' }));
              }
            });
          },
        },
      },
    },
    test: {
      environment: 'jsdom',
      setupFiles: './src/setupTests.ts',
      // Playwright e2e specs live in e2e/.
      include: ['src/**/*.test.{ts,tsx}'],
    },
  };
});
