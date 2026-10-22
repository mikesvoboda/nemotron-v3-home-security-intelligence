/**
 * The E2E suite's base URL, in one place.
 *
 * The dev server's port is pinned by vite.config.ts (`server.port: 8444,
 * strictPort`), and the E2E suite historically hard-coded the URL in three
 * places: the Playwright config's `use.baseURL`, global-setup's warm-up
 * navigation, and the origin global-setup wrote into the storage state.
 * The third one diverged (ruling 299, audit item Q-179): the storage state
 * was written under `https://localhost:8444` while the specs run at
 * `http://localhost:8444`, and Playwright applies localStorage per origin,
 * so the tour-suppression keys never landed for the specs that don't use
 * the shared fixtures' init script — the nightly visual specs and local
 * runs. Deriving both from one module keeps them from diverging again.
 *
 * `E2E_BASE_URL` is the override knob the Playwright docs suggest for
 * baseURL, so a stack on another port or host can be driven without
 * editing the config.
 */

const DEFAULT_E2E_BASE_URL = 'http://localhost:8444';

export function resolveE2eBaseUrl(): string {
  const raw = process.env.E2E_BASE_URL?.trim();
  if (!raw) {
    return DEFAULT_E2E_BASE_URL;
  }
  // A bare "localhost:8444" would later be interpreted as host:port by URL
  // parsing, so reject anything without a scheme rather than guessing one.
  const parsed = new URL(raw);
  if (!parsed.protocol.startsWith('http')) {
    throw new Error(
      `E2E_BASE_URL must be an http(s) URL, got: ${raw} (protocol ${parsed.protocol})`
    );
  }
  return raw;
}

export const E2E_BASE_URL = resolveE2eBaseUrl();

/**
 * The origin the storage state must be written under — the origin the specs
 * actually run at. Playwright seeds localStorage per origin, so this is the
 * origin part of the configured base URL, never a separate literal.
 */
export const E2E_STORAGE_STATE_ORIGIN = new URL(E2E_BASE_URL).origin;
