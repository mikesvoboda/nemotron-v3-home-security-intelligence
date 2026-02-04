import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

/**
 * Vite configuration for E2E tests.
 *
 * This configuration disables the API proxy, allowing Playwright's page.route()
 * to intercept API requests directly. Without this, Vite's proxy would try to
 * forward requests to localhost:8000 (the backend) before Playwright could
 * intercept them, causing ECONNREFUSED errors in CI where no backend is running.
 */
export default defineConfig({
  plugins: [react()],
  cacheDir: '.vitest',
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 8444,
    strictPort: true,
    // Use HTTP for E2E tests - HTTPS is not required since:
    // 1. API requests are intercepted by Playwright's page.route()
    // 2. No real TLS termination is needed for test environment
    // 3. Avoids TLS handshake issues with auto-generated certificates
    https: false,
    // No proxy configuration - API requests will be intercepted by Playwright
    // The frontend will make requests to localhost:8444/api/* which Vite will
    // return a 404 for, but Playwright's route() will intercept before that happens
  },
});
