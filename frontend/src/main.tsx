import React from 'react';
import ReactDOM from 'react-dom/client';

import App from './App';
import './styles/index.css';
import { isSecureContext, logWebCodecsStatus } from './utils/webcodecs';

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
