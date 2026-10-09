#!/usr/bin/env node
// B1.4 real-tier fixed-target relay (owner ruling 22, step 4).
//
// The backend dials ONE url — http://vlm-proxy:8098 — and this relay dials the engine.
// `agent-gpu run` publishes the engine on a fresh host port from the 18100-18199 pool on
// every admission, so the pool port lives only here. Taking the engine away from the
// readiness probe is `printf off > /run/b14/mode`: the listener closes and live sockets
// die, which the backend's probe sees as exactly what a stopped engine looks like —
// ECONNREFUSED on the URL it dials (reason: "ai-vlm service connection refused",
// backend/api/routes/system.py:934). Re-admission on a new port is
// `printf %s <newport> > /run/b14/target`, then `printf on > /run/b14/mode`.
//
// No dependencies, no writes; mode/target are read by polling /run/b14, which the run binds
// from its own state directory (b14run/<project>/state — never a live path, removed by step D).
// A tmpfs would have been tidier but is wiped on container restart: measured here, a restarted
// proxy booted with no mode file, fell back to on, and silently undid a running check.

import net from 'node:net';
import fs from 'node:fs';

const PORT = Number(process.env.PORT || 8098);
const STATE_DIR = process.env.VLMPROXY_STATE_DIR || '/run/b14';
const MODE_FILE = `${STATE_DIR}/mode`;
const TARGET_FILE = `${STATE_DIR}/target`;

function readOr(path, fallback) {
  try {
    const v = fs.readFileSync(path, 'utf8').trim();
    return v === '' ? fallback : v;
  } catch {
    return fallback;
  }
}

function normalizeTarget(spec) {
  // "vlm-mock:8098" | "18123" | "http://host.docker.internal:18123" -> {host, port}
  let s = String(spec).trim();
  const m = /^https?:\/\/([^/]+)$/.exec(s);
  if (m) s = m[1];
  const idx = s.lastIndexOf(':');
  if (idx <= 0) return { host: 'host.docker.internal', port: Number(s) };
  return { host: s.slice(0, idx), port: Number(s.slice(idx + 1)) };
}

// VLMPROXY_TARGET is the initial target; /run/b14/target overrides it at runtime.
const initialTarget = normalizeTarget(
  process.env.VLMPROXY_TARGET || (() => {
    console.error('vlm-proxy: VLMPROXY_TARGET is not set (runner URL or vlm-mock:8098)');
    process.exit(2);
  })(),
);

let current = initialTarget;
let lastTargetSpec = `${initialTarget.host}:${initialTarget.port}`;
let listening = false;
const live = new Set();

function applyMode() {
  const mode = readOr(MODE_FILE, 'on');
  const t = readOr(TARGET_FILE, null);
  const want = mode !== 'off';
  if (t && t !== lastTargetSpec) {
    current = normalizeTarget(t);
    lastTargetSpec = t;
    console.log(`vlm-proxy: re-targeted -> ${current.host}:${current.port}`);
  }
  if (want && !listening) {
    server.listen(PORT, '0.0.0.0', () => {
      listening = true;
      console.log(`vlm-proxy: ON  ${PORT} -> ${current.host}:${current.port}`);
    });
  } else if (!want && listening) {
    const drained = live.size;
    server.close(() => {
      listening = false;
      console.log('vlm-proxy: OFF (listener closed; new dials get ECONNREFUSED)');
    });
    for (const s of live) s.destroy();
    live.clear();
    console.log(`vlm-proxy: OFF requested, draining ${drained} live sockets`);
  }
}

const BAD_GATEWAY = (host, port) => {
  const body = JSON.stringify({ error: { message: `b14 vlm-proxy cannot reach ${host}:${port}` } });
  return `HTTP/1.1 502 Bad Gateway\r\ncontent-type: application/json\r\ncontent-length: ${Buffer.byteLength(body)}\r\nconnection: close\r\n\r\n${body}`;
};

const server = net.createServer((client) => {
  live.add(client);
  client.setNoDelay(true);
  let flowed = 0; // request bytes already on their way upstream
  const remote = net.connect({ host: current.host, port: current.port });
  live.add(remote);
  const done = () => {
    live.delete(client);
    live.delete(remote);
    client.destroy();
    remote.destroy();
  };
  client.on('data', (c) => {
    flowed += c.length;
  });
  client.on('error', done);
  remote.on('error', (e) => {
    console.log(`vlm-proxy: forward error ${e.code} (${current.host}:${current.port})`);
    // Answer 502 rather than resetting when the dial fails before anything streamed. Measured
    // against the real backend: a bare reset surfaces as httpx.ReadError, which
    // _check_ai_vlm_health's handlers (system.py:933-941: ConnectError | Timeout | HTTPStatus |
    // OSError|RuntimeError) and _bounded_health_check (:1034) ALL miss — the readiness endpoint
    // then 500s and its own Docker healthcheck starts failing. A 502 reads as the legible
    // "ai-vlm service returned HTTP 502" and ready stays 200, as documented.
    if (flowed === 0 && !client.destroyed && client.writable) {
      client.write(BAD_GATEWAY(current.host, current.port));
      client.end();
    }
    done();
  });
  client.on('close', done);
  remote.on('close', done);
  client.pipe(remote);
  remote.pipe(client);
});
server.on('error', (e) => console.error(`vlm-proxy: listener error ${e.code}`));

fs.mkdirSync(STATE_DIR, { recursive: true });
console.log(`vlm-proxy: starting; mode=${readOr(MODE_FILE, 'on')} target=${current.host}:${current.port}`);
applyMode();
// NOT unref'd on purpose: while mode=off the listener is closed, and this timer is the only
// ref holding the event loop open. An unref'd timer let node exit(0) right after server.close()
// — compose restart:'unless-stopped' then brought the relay back with no mode file (measured:
// RestartCount=1, exit 0, ~1 s after the OFF log line) and the check quietly self-healed.
setInterval(applyMode, 250);
