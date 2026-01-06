/**
 * MSW (Mock Service Worker) server for Node.js test environment.
 *
 * This server intercepts HTTP requests in Vitest tests and returns mock responses
 * defined in handlers.ts. It runs in Node.js and is started before tests.
 *
 * ## Test Setup Integration
 *
 * The server is automatically started and stopped via the test setup file
 * (`src/test/setup.ts`). Individual tests don't need to manage the server lifecycle.
 *
 * ## Overriding Handlers in Tests
 *
 * Use `server.use()` to override handlers for specific test scenarios:
 *
 * ```typescript
 * import { server } from '../mocks/server';
 * import { http, HttpResponse } from 'msw';
 *
 * it('handles API error', async () => {
 *   // Override the default /api/cameras handler for this test only
 *   server.use(
 *     http.get('/api/cameras', () => {
 *       return HttpResponse.json({ detail: 'Server error' }, { status: 500 });
 *     })
 *   );
 *
 *   // ... test error handling logic
 * });
 * ```
 *
 * Handler overrides are automatically cleared after each test by the
 * `server.resetHandlers()` call in the test setup.
 *
 * ## Runtime Request Handlers
 *
 * You can also add one-time handlers dynamically:
 *
 * ```typescript
 * import { server } from '../mocks/server';
 * import { http, HttpResponse } from 'msw';
 *
 * it('handles specific response sequence', async () => {
 *   let callCount = 0;
 *   server.use(
 *     http.get('/api/cameras', () => {
 *       callCount++;
 *       if (callCount === 1) {
 *         // First call: loading state
 *         return new HttpResponse(null, { status: 204 });
 *       }
 *       // Second call: return data
 *       return HttpResponse.json({ cameras: [...] });
 *     })
 *   );
 *   // ...
 * });
 * ```
 *
 * @see https://mswjs.io/docs/integrations/node
 */

import { setupServer } from 'msw/node';

import { handlers } from './handlers';

/**
 * MSW server instance for use in Vitest tests.
 *
 * Lifecycle:
 * - Started in beforeAll (via test setup)
 * - Handlers reset in afterEach (via test setup)
 * - Stopped in afterAll (via test setup)
 *
 * @example
 * ```typescript
 * // Override a handler for a single test
 * import { server } from '../mocks/server';
 * import { http, HttpResponse } from 'msw';
 *
 * it('handles empty response', async () => {
 *   server.use(
 *     http.get('/api/events', () => {
 *       return HttpResponse.json({ events: [], count: 0, limit: 50, offset: 0 });
 *     })
 *   );
 *   // Test with empty events
 * });
 * ```
 */
export const server = setupServer(...handlers);
