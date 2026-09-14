import React from 'react';
import ReactDOM from 'react-dom/client';

import App from './App';
import { initializeErrorReporting } from './services/errorReporting';
import { initRUM } from './services/rum';
import { initSentry } from './services/sentry';
import { registerServiceWorker } from './services/serviceWorkerRegistration';
import './styles/index.css';
import { isSecureContext, logWebCodecsStatus } from './utils/webcodecs';

// Initialize global error reporting first, before anything else (NEM-2726)
// This captures uncaught exceptions and unhandled promise rejections
// and reports them to the backend with rate limiting and noise filtering
initializeErrorReporting();

// Initialize Sentry error tracking early, before the app renders
// Sentry will only be active if VITE_SENTRY_DSN is configured
initSentry();

// Initialize Real User Monitoring (RUM) for Core Web Vitals tracking (NEM-1635)
// Collects LCP, INP, CLS, TTFB, FCP metrics from real users and sends to backend
initRUM();

// Log WebCodecs availability status on startup (development aide)
// Only logs a warning if not in secure context to help diagnose feature availability
if (!isSecureContext()) {
  logWebCodecsStatus('warn');
}

const rootElement = document.getElementById('root');
if (!rootElement) throw new Error('Failed to find the root element');

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

// Register PWA service worker for offline caching (NEM-3675)
// Uses Workbox under the hood via vite-plugin-pwa
void registerServiceWorker({
  onError: (error) => {
    console.warn('Service worker registration failed:', error.message);
  },
});
