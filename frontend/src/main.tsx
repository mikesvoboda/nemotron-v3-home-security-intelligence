import React from 'react';
import ReactDOM from 'react-dom/client';

import App from './App';
import { initRUM } from './services/rum';
import { initSentry } from './services/sentry';
import './styles/index.css';
import { isSecureContext, logWebCodecsStatus } from './utils/webcodecs';

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
