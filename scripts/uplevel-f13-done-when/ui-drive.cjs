// F1.3 Done-when UI drive: one Playwright pass against the live stack at
// http://127.0.0.1:18080. Mode from F13_MODE: "auth" (stack running
// EXPOSE_LAN=true — expect login screen, then a working app after login) or
// "open" (EXPOSE_LAN unset — expect no login at all).
// Run from this directory (or set F13_PLAYWRIGHT_PATH); it resolves
// playwright from the frontend workspace's node_modules.
const path = require('path');

const pwPath =
  process.env.F13_PLAYWRIGHT_PATH ||
  path.join(
    process.env.F13_REPO_ROOT || path.resolve(__dirname, '../../..'),
    'frontend/node_modules/playwright'
  );
const { chromium } = require(pwPath);

const BASE = process.env.F13_BASE_URL || 'http://127.0.0.1:18080';
const mode = process.env.F13_MODE;
const user = process.env.F13_UI_USER;
const password = process.env.F13_UI_PASSWORD;

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();

  const authCalls = [];
  page.on('response', (r) => {
    if (r.url().includes('/api/auth/'))
      authCalls.push(`${r.status()} ${r.url().replace(BASE, '')}`);
  });

  const sockets = [];
  page.on('websocket', (ws) => {
    const rec = { url: ws.url(), opened: true, frames: 0, closed: false };
    sockets.push(rec);
    ws.on('framereceived', () => {
      rec.frames += 1;
    });
    ws.on('close', () => {
      rec.closed = true;
    });
  });

  // Attach BEFORE goto: the cold-start bounce we watch for can commit while
  // goto is still resolving (it fired at +143ms in the pre-fix trace).
  const denied = [];
  page.on('framenavigated', (f) => {
    if (f === page.mainFrame() && new URL(f.url()).pathname.startsWith('/login')) {
      denied.push(f.url());
    }
  });

  console.log(`MODE=${mode}`);

  // The app mounts a react-joyride onboarding tour whose overlay div covers the
  // viewport and swallows clicks (it fires for a brand-new user with no stored
  // tour state). It is orthogonal to the auth gate; remove its portal so the
  // drive interacts with the login form itself.
  const killJoyride = async () => {
    await page.evaluate(() => {
      document.getElementById('react-joyride-portal')?.remove();
      document.querySelectorAll('.react-joyride__overlay').forEach((n) => n.remove());
    });
  };

  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await killJoyride();

  if (mode === 'auth') {
    // 1. The landing redirect must land on /login, showing the form.
    await page.waitForURL('**/login', { timeout: 20000 });
    await page.getByLabel(/username/i).waitFor({ timeout: 15000 });
    console.log('login screen: URL=' + page.url() + ' form visible');

    // 2. Log in with the bootstrapped admin (register it first — README).
    await page.getByLabel(/username/i).fill(user);
    await page.getByLabel(/^password/i).fill(password);
    await killJoyride();
    await page.getByRole('button', { name: /sign in|log in/i }).click();

    // 3. After login the app must come up: off /login and real content rendered.
    await page.waitForURL((u) => !u.pathname.startsWith('/login'), { timeout: 20000 });
    await page.waitForSelector('text=/threat|activity|camera|timeline|settings/i', {
      timeout: 20000,
    });
    await page.waitForTimeout(4000); // let the dashboard's WS connect
    console.log('after login: URL=' + page.url() + ' — app content rendered');
  } else {
    // open mode: no login may appear at ANY point. A text check alone is not
    // enough: the LoginPage brand heading ("...Dashboard") also matches
    // generic words, so the assertion is the location timeline (denied[],
    // collected from page load).
    await page.waitForTimeout(8000); // give any bounce to /login time to happen
    await page.waitForSelector('text=/threat|activity|camera|timeline|settings/i', {
      timeout: 20000,
    });
    await page.waitForTimeout(3000);
    console.log('open mode: final URL=' + page.url());
    console.log(
      'open mode: visited /login = ' +
        (denied.length ? 'YES (FAIL) ' + JSON.stringify(denied) : 'never — no login')
    );
  }

  console.log('auth endpoint calls: ' + JSON.stringify(authCalls));
  console.log(
    'websockets: ' +
      JSON.stringify(
        sockets.map((s) => ({ url: s.url.replace(BASE, ''), frames: s.frames, closed: s.closed }))
      )
  );
  await browser.close();
})().catch((e) => {
  console.error('DRIVE FAILED: ' + e.message);
  process.exit(1);
});
