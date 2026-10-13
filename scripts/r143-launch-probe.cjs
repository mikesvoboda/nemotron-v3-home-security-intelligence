// Ruling 143 clause-4 discriminator, committed per contract rule 3 ("commit
// every script, fixture and harness a package relies on; work from /tmp or a
// home directory does not count as evidence"). It launches the browser the same
// way both golden legs do and prints LAUNCHED or LAUNCHFAILED, so the SAME bytes
// answer "does the image supply the system libraries the host lacks?"
//
// Why .cjs, not .js: frontend/package.json declares "type": "module", so a .js
// file next to the tree that resolves @playwright/test is parsed as ESM and its
// `require` is undefined. The .cjs spelling forces CommonJS so the host arm and
// the container arm run identical bytes — the whole comparison depends on the
// probe being the constant and the ENVIRONMENT being the variable.
//
// Run it twice, from the repo root, exactly as PR #7034's body records:
//
//   # host — browser present, its shared libraries absent -> LAUNCHFAILED
//   NODE_PATH="$PWD/frontend/node_modules" node scripts/r143-launch-probe.cjs
//
//   # container — the image's own libraries make the same launch succeed
//   docker run --rm --network host -v "$PWD:$PWD:ro" -w "$PWD/frontend" \
//       -e NODE_PATH="$PWD/frontend/node_modules" \
//       mcr.microsoft.com/playwright:v1.63.0-noble \
//       node "$PWD/scripts/r143-launch-probe.cjs"
//
// The image tag is the one feature_check.py derives from frontend/package-lock.json;
// re-derive it (do not type it) so the probe can never run a browser the harness
// would not:  tag=$(python3 -c 'import sys; sys.path.insert(0,"scripts");
// import feature_check as fc; print(fc.playwright_image(fc.PACKAGE_LOCK))')
const { chromium } = require("@playwright/test");

(async () => {
  let browser;
  try {
    browser = await chromium.launch();
    const version = browser.version();
    // A launch that survives to a version string is the container's answer: the
    // image's libraries closed the gaps ldd reports as "not found" on the host.
    console.log(`LAUNCHED ${version}`);
  } catch (error) {
    // The host's answer: the browser binary is there, but a dlopen of one of its
    // missing shared libraries aborts the launch. Print only the first line —
    // the rest is the stack, not the signal.
    console.log(`LAUNCHFAILED ${String(error.message).split("\n")[0]}`);
    process.exitCode = 3;
  } finally {
    if (browser) await browser.close();
  }
})();
