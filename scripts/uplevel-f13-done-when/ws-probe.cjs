// F1.3 Done-when WS handshake probe: does the gate refuse an UNCREDENTIALED
// socket? Uses Node's built-in global WebSocket (Node >= 22, undici) — no
// `ws` package needed.
//
// B1.5 refuses a Web socket by ACCEPTING the handshake and then closing it
// (backend/api/middleware/auth.py _refuse: `await websocket.accept()` then
// `close(code=4001, ...)`), so an `open` event is NOT evidence of acceptance.
// The answer is the close CODE within a settle window. Expected on this stack:
//   EXPOSE_LAN=true  -> closed code=4001 reason="Authentication required"
//   EXPOSE_LAN unset -> no close; printed as "open (no close within Ns)"
// With a credential, pass F13_WS_PROTOCOL='api-key.<key>' to see it accepted.
const url = process.env.F13_WS_URL || 'ws://127.0.0.1:18080/ws/events';
const protocols = process.env.F13_WS_PROTOCOL ? process.env.F13_WS_PROTOCOL.split(',') : undefined;
// How long an open socket must survive before we call it genuinely open.
const SETTLE_MS = Number(process.env.F13_WS_SETTLE_MS || 2000);

const socket = protocols ? new WebSocket(url, protocols) : new WebSocket(url);
const t0 = Date.now();
let settled = false;
let opened = false;

const finish = (line, code) => {
  if (settled) return;
  settled = true;
  console.log(line);
  process.exit(code);
};

const settleTimer = setTimeout(() => {
  finish(`open (no close within ${SETTLE_MS}ms) ${url}`, 0);
}, SETTLE_MS);

socket.addEventListener('open', () => {
  opened = true;
  // Do not answer here: the gate accepts before it refuses (see header).
});

socket.addEventListener('close', (ev) => {
  clearTimeout(settleTimer);
  const held = opened ? `+${Date.now() - t0}ms` : 'handshake';
  finish(`closed code=${ev.code} reason="${ev.reason}" (${held})`, 0);
});

socket.addEventListener('error', (ev) => {
  clearTimeout(settleTimer);
  finish(`error ${ev.message || 'websocket error'}`, 1);
});
