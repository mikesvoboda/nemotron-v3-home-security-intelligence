// B-1/B-2 key-mode drive: the deployment a browser reaches with VITE_API_KEY
// baked and EXPOSE_LAN=true — gate armed, one API_KEYS key live. The merged
// frontend treats the key as transport (no key→session bootstrap exists in
// AuthContext), so the key-mode contract the browser actually exercises is:
// the key authenticates REST, and an `api-key.<key>` subprotocol OFFER must
// complete a browser WebSocket handshake — which since RFC 6455 §4.1 means
// the server must ECHO a token, the exact B-1 defect (no accept() echoed;
// Chromium closed 1006 before open, on every key-offering socket).
//
// Assertions use browser primitives evaluated in the page, not the app's own
// components: the handshake is the unit under test, and the bounced app
// bundle (no session) is frontend behavior outside B-1's scope. The page
// only supplies a real browser origin + network stack.
//
// F13_API_KEY must match the API_KEYS entry in
// docker-compose.f13-key-mode.yml (default: its throwaway default).
// Run from this directory (or set F13_PLAYWRIGHT_PATH). Exit != 0 on FAIL.
const path = require('path');

const pwPath =
  process.env.F13_PLAYWRIGHT_PATH ||
  path.join(
    process.env.F13_REPO_ROOT || path.resolve(__dirname, '../../..'),
    'frontend/node_modules/playwright'
  );
const { chromium } = require(pwPath);

const BASE = process.env.F13_BASE_URL || 'http://127.0.0.1:18080';
const KEY = process.env.F13_API_KEY || 'f13-throwaway-key-not-a-secret'; // pragma: allowlist secret
const WS_PATH = process.env.F13_WS_PATH || '/ws/events';
const SETTLE_MS = Number(process.env.F13_WS_SETTLE_MS || 3000);

let failed = false;
const check = (label, ok, detail) => {
  console.log(`${ok ? 'PASS' : 'FAIL'} ${label}: ${detail}`);
  if (!ok) failed = true;
};

// One browser handshake, in-page: collect open/echo/close, settle-wait like
// ws-probe.cjs (the gate accepts BEFORE it refuses, so open alone is not
// acceptance — the close CODE is the answer when the key is wrong).
async function browserHandshake(page, offer) {
  return page.evaluate(
    ({ wsPath, offered, settleMs }) =>
      new Promise((resolve) => {
        const rec = { opened: false, protocol: null, code: null, held: false };
        const ws = new WebSocket(`ws://${location.host}${wsPath}`, [offered]);
        let done = false;
        const finish = () => {
          if (done) return;
          done = true;
          if (rec.opened && rec.code === null) rec.held = true;
          resolve(rec);
        };
        ws.onopen = () => {
          rec.opened = true;
          rec.protocol = ws.protocol;
        };
        ws.onclose = (ev) => {
          rec.code = ev.code;
          finish();
        };
        ws.onerror = () => {};
        setTimeout(finish, settleMs);
      }),
    { wsPath: WS_PATH, offered: offer, settleMs: SETTLE_MS }
  );
}

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const page = await ctx.newPage();
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded', timeout: 30000 });
  // /login is the expected landing here (no session cookie — the key is not
  // a session); nothing below depends on which view rendered.
  console.log(`key-mode: page at ${page.url()}`);

  // Leg 1 — REST with the key: the gate must let it through (200, not 401).
  const restOk = await page.evaluate(
    ({ key }) =>
      fetch('/api/events', { headers: { 'X-API-Key': key } }).then((r) => r.status),
    { key: KEY }
  );
  check('REST with key', restOk === 200, `status=${restOk} (want 200)`);

  // Leg 2 — REST without it: the gate is armed (401), proving leg 1 passed on
  // the key and not on an unarmed gate.
  const restNoKey = await page.evaluate(() => fetch('/api/events').then((r) => r.status));
  check('REST without key', restNoKey === 401, `status=${restNoKey} (want 401)`);

  // Leg 3 — B-1 proper: valid-key offer in a BROWSER. Must open, and the
  // browser must report our own token back as the negotiated subprotocol.
  // Pre-B-1 this leg is where Chromium died: no echo → 1006 before open.
  const good = await browserHandshake(page, `api-key.${KEY}`);
  check(
    'browser WS offer accepted',
    good.opened && good.held,
    `opened=${good.opened} held>${SETTLE_MS}ms=${good.held} code=${good.code}`
  );
  check(
    'browser saw the echo',
    good.protocol === `api-key.${KEY}`,
    `ws.protocol=${JSON.stringify(good.protocol)} (want "api-key.${KEY}")`
  );

  // Leg 4 — refusal keeps the echo AND the close code: a wrong key still
  // gets its offered token echoed (B-1 covers the gate's accept-then-close)
  // and then the deliberate 4001 — visible only because the echo rode first.
  const bad = await browserHandshake(page, 'api-key.the-wrong-key');
  check(
    'wrong-key refusal is 4001',
    bad.opened && bad.code === 4001,
    `opened=${bad.opened} code=${bad.code} (want 4001, NOT 1006)`
  );
  check(
    'refusal echoed too',
    bad.protocol === 'api-key.the-wrong-key',
    `ws.protocol=${JSON.stringify(bad.protocol)}`
  );

  await browser.close();
  if (failed) {
    console.error('KEY-MODE DRIVE FAILED');
    process.exit(1);
  }
  console.log('key-mode: all legs passed');
})().catch((e) => {
  console.error('DRIVE FAILED: ' + e.message);
  process.exit(1);
});
