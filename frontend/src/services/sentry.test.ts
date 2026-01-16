/**
 * Tests for Sentry error tracking integration.
 *
 * Following TDD approach - these tests are written first, before implementation.
 */
// eslint-disable-next-line import/order -- Test file imports vitest before mocking
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// Mock @sentry/react before importing the module under test
// Note: vi.mock is hoisted, so we define mock functions inside the factory
vi.mock('@sentry/react', () => {
  const mockInit = vi.fn();
  const mockCaptureException = vi.fn();
  const mockCaptureMessage = vi.fn();
  const mockAddBreadcrumb = vi.fn();
  const mockSetUser = vi.fn();
  const mockSetContext = vi.fn();
  const mockWithScope = vi.fn((callback: (scope: unknown) => void) => {
    callback({
      setTag: vi.fn(),
      setExtra: vi.fn(),
      setLevel: vi.fn(),
    });
  });

  return {
    init: mockInit,
    captureException: mockCaptureException,
    captureMessage: mockCaptureMessage,
    addBreadcrumb: mockAddBreadcrumb,
    setUser: mockSetUser,
    setContext: mockSetContext,
    withScope: mockWithScope,
    browserTracingIntegration: vi.fn(() => ({ name: 'BrowserTracing' })),
    replayIntegration: vi.fn(() => ({ name: 'Replay' })),
    ErrorBoundary: vi.fn(),
  };
});

// Import Sentry mock to get access to the mock functions
// eslint-disable-next-line import/order -- Must import after vi.mock for hoisting to work
import * as Sentry from '@sentry/react';

// Import the module under test - only type is used from static import
// The actual functions are imported dynamically in tests to pick up env changes
import type { SentryConfig } from './sentry';

describe('Sentry Integration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset module state between tests by re-importing
    vi.resetModules();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  describe('initSentry', () => {
    it('initializes Sentry with DSN from environment variable', async () => {
      vi.stubEnv('VITE_SENTRY_DSN', 'https://test@sentry.io/123');

      // Re-import to pick up env changes
      const { initSentry: init } = await import('./sentry');
      init();

      expect(Sentry.init).toHaveBeenCalledWith(
        expect.objectContaining({
          dsn: 'https://test@sentry.io/123',
        })
      );
    });

    it('does not initialize Sentry when DSN is not provided', async () => {
      vi.stubEnv('VITE_SENTRY_DSN', '');

      const { initSentry: init } = await import('./sentry');
      init();

      expect(Sentry.init).not.toHaveBeenCalled();
    });

    it('configures environment based on VITE_SENTRY_ENVIRONMENT', async () => {
      vi.stubEnv('VITE_SENTRY_DSN', 'https://test@sentry.io/123');
      vi.stubEnv('VITE_SENTRY_ENVIRONMENT', 'staging');

      const { initSentry: init } = await import('./sentry');
      init();

      expect(Sentry.init).toHaveBeenCalledWith(
        expect.objectContaining({
          environment: 'staging',
        })
      );
    });

    it('defaults to production environment when not specified', async () => {
      vi.stubEnv('VITE_SENTRY_DSN', 'https://test@sentry.io/123');
      vi.stubEnv('VITE_SENTRY_ENVIRONMENT', '');

      const { initSentry: init } = await import('./sentry');
      init();

      expect(Sentry.init).toHaveBeenCalledWith(
        expect.objectContaining({
          environment: 'production',
        })
      );
    });

    it('configures trace sample rate from environment', async () => {
      vi.stubEnv('VITE_SENTRY_DSN', 'https://test@sentry.io/123');
      vi.stubEnv('VITE_SENTRY_TRACES_SAMPLE_RATE', '0.5');

      const { initSentry: init } = await import('./sentry');
      init();

      expect(Sentry.init).toHaveBeenCalledWith(
        expect.objectContaining({
          tracesSampleRate: 0.5,
        })
      );
    });

    it('defaults trace sample rate to 0.1 when not specified', async () => {
      vi.stubEnv('VITE_SENTRY_DSN', 'https://test@sentry.io/123');
      vi.stubEnv('VITE_SENTRY_TRACES_SAMPLE_RATE', '');

      const { initSentry: init } = await import('./sentry');
      init();

      expect(Sentry.init).toHaveBeenCalledWith(
        expect.objectContaining({
          tracesSampleRate: 0.1,
        })
      );
    });

    it('configures replay sample rate from environment', async () => {
      vi.stubEnv('VITE_SENTRY_DSN', 'https://test@sentry.io/123');
      vi.stubEnv('VITE_SENTRY_REPLAY_SAMPLE_RATE', '0.2');

      const { initSentry: init } = await import('./sentry');
      init();

      expect(Sentry.init).toHaveBeenCalledWith(
        expect.objectContaining({
          replaysSessionSampleRate: 0.2,
        })
      );
    });

    it('configures replay on error sample rate from environment', async () => {
      vi.stubEnv('VITE_SENTRY_DSN', 'https://test@sentry.io/123');
      vi.stubEnv('VITE_SENTRY_REPLAY_ON_ERROR_RATE', '0.8');

      const { initSentry: init } = await import('./sentry');
      init();

      expect(Sentry.init).toHaveBeenCalledWith(
        expect.objectContaining({
          replaysOnErrorSampleRate: 0.8,
        })
      );
    });

    it('accepts custom configuration via function parameter', async () => {
      vi.stubEnv('VITE_SENTRY_DSN', 'https://test@sentry.io/123');

      const customConfig: Partial<SentryConfig> = {
        release: 'v1.0.0',
        debug: true,
      };

      const { initSentry: init } = await import('./sentry');
      init(customConfig);

      expect(Sentry.init).toHaveBeenCalledWith(
        expect.objectContaining({
          release: 'v1.0.0',
          debug: true,
        })
      );
    });

    it('includes browser tracing integration', async () => {
      vi.stubEnv('VITE_SENTRY_DSN', 'https://test@sentry.io/123');

      const { initSentry: init } = await import('./sentry');
      init();

      expect(Sentry.init).toHaveBeenCalledWith(
        expect.objectContaining({
          integrations: expect.arrayContaining([
            expect.objectContaining({ name: 'BrowserTracing' }),
          ]),
        })
      );
    });

    it('includes replay integration', async () => {
      vi.stubEnv('VITE_SENTRY_DSN', 'https://test@sentry.io/123');

      const { initSentry: init } = await import('./sentry');
      init();

      expect(Sentry.init).toHaveBeenCalledWith(
        expect.objectContaining({
          integrations: expect.arrayContaining([expect.objectContaining({ name: 'Replay' })]),
        })
      );
    });
  });

  describe('isSentryEnabled', () => {
    it('returns true when DSN is configured', async () => {
      vi.stubEnv('VITE_SENTRY_DSN', 'https://test@sentry.io/123');

      const { isSentryEnabled: check } = await import('./sentry');
      expect(check()).toBe(true);
    });

    it('returns false when DSN is not configured', async () => {
      vi.stubEnv('VITE_SENTRY_DSN', '');

      const { isSentryEnabled: check } = await import('./sentry');
      expect(check()).toBe(false);
    });

    it('returns false when DSN is whitespace only', async () => {
      vi.stubEnv('VITE_SENTRY_DSN', '   ');

      const { isSentryEnabled: check } = await import('./sentry');
      expect(check()).toBe(false);
    });
  });

  describe('captureError', () => {
    it('captures an Error object', async () => {
      vi.stubEnv('VITE_SENTRY_DSN', 'https://test@sentry.io/123');

      const { initSentry: init, captureError: capture } = await import('./sentry');
      init();

      const error = new Error('Test error');
      capture(error);

      expect(Sentry.captureException).toHaveBeenCalledWith(error, undefined);
    });

    it('captures error with additional context', async () => {
      vi.stubEnv('VITE_SENTRY_DSN', 'https://test@sentry.io/123');

      const { initSentry: init, captureError: capture } = await import('./sentry');
      init();

      const error = new Error('Test error');
      const context = {
        tags: { component: 'TestComponent' },
        extra: { userId: '123' },
      };

      capture(error, context);

      expect(Sentry.captureException).toHaveBeenCalledWith(error, context);
    });

    it('captures non-Error values', async () => {
      vi.stubEnv('VITE_SENTRY_DSN', 'https://test@sentry.io/123');

      const { initSentry: init, captureError: capture } = await import('./sentry');
      init();

      const errorMessage = 'String error message';
      capture(errorMessage);

      expect(Sentry.captureException).toHaveBeenCalledWith(errorMessage, undefined);
    });

    it('does not call Sentry when disabled', async () => {
      vi.stubEnv('VITE_SENTRY_DSN', '');

      const { captureError: capture } = await import('./sentry');

      const error = new Error('Test error');
      capture(error);

      expect(Sentry.captureException).not.toHaveBeenCalled();
    });
  });

  describe('captureMessage', () => {
    it('captures a message with default level', async () => {
      vi.stubEnv('VITE_SENTRY_DSN', 'https://test@sentry.io/123');

      const { initSentry: init, captureMessage: capture } = await import('./sentry');
      init();

      capture('Test message');

      expect(Sentry.captureMessage).toHaveBeenCalledWith('Test message', undefined);
    });

    it('captures a message with specified level', async () => {
      vi.stubEnv('VITE_SENTRY_DSN', 'https://test@sentry.io/123');

      const { initSentry: init, captureMessage: capture } = await import('./sentry');
      init();

      capture('Warning message', 'warning');

      expect(Sentry.captureMessage).toHaveBeenCalledWith('Warning message', 'warning');
    });

    it('does not call Sentry when disabled', async () => {
      vi.stubEnv('VITE_SENTRY_DSN', '');

      const { captureMessage: capture } = await import('./sentry');
      capture('Test message');

      expect(Sentry.captureMessage).not.toHaveBeenCalled();
    });
  });

  describe('addBreadcrumb', () => {
    it('adds a breadcrumb with message and category', async () => {
      vi.stubEnv('VITE_SENTRY_DSN', 'https://test@sentry.io/123');

      const { initSentry: init, addBreadcrumb: add } = await import('./sentry');
      init();

      add({
        message: 'User clicked button',
        category: 'ui.click',
      });

      expect(Sentry.addBreadcrumb).toHaveBeenCalledWith({
        message: 'User clicked button',
        category: 'ui.click',
      });
    });

    it('adds a breadcrumb with all properties', async () => {
      vi.stubEnv('VITE_SENTRY_DSN', 'https://test@sentry.io/123');

      const { initSentry: init, addBreadcrumb: add } = await import('./sentry');
      init();

      const breadcrumb = {
        message: 'API request',
        category: 'http',
        level: 'info' as const,
        data: { url: '/api/events', method: 'GET' },
      };

      add(breadcrumb);

      expect(Sentry.addBreadcrumb).toHaveBeenCalledWith(breadcrumb);
    });

    it('does not call Sentry when disabled', async () => {
      vi.stubEnv('VITE_SENTRY_DSN', '');

      const { addBreadcrumb: add } = await import('./sentry');
      add({ message: 'Test', category: 'test' });

      expect(Sentry.addBreadcrumb).not.toHaveBeenCalled();
    });
  });

  describe('setUserContext', () => {
    it('sets user context with id', async () => {
      vi.stubEnv('VITE_SENTRY_DSN', 'https://test@sentry.io/123');

      const { initSentry: init, setUserContext: set } = await import('./sentry');
      init();

      set({ id: 'user-123' });

      expect(Sentry.setUser).toHaveBeenCalledWith({ id: 'user-123' });
    });

    it('sets user context with email', async () => {
      vi.stubEnv('VITE_SENTRY_DSN', 'https://test@sentry.io/123');

      const { initSentry: init, setUserContext: set } = await import('./sentry');
      init();

      set({ email: 'user@example.com' });

      expect(Sentry.setUser).toHaveBeenCalledWith({ email: 'user@example.com' });
    });

    it('sets user context with all properties', async () => {
      vi.stubEnv('VITE_SENTRY_DSN', 'https://test@sentry.io/123');

      const { initSentry: init, setUserContext: set } = await import('./sentry');
      init();

      const user = {
        id: 'user-123',
        email: 'user@example.com',
        username: 'testuser',
      };

      set(user);

      expect(Sentry.setUser).toHaveBeenCalledWith(user);
    });

    it('clears user context when null is passed', async () => {
      vi.stubEnv('VITE_SENTRY_DSN', 'https://test@sentry.io/123');

      const { initSentry: init, setUserContext: set } = await import('./sentry');
      init();

      set(null);

      expect(Sentry.setUser).toHaveBeenCalledWith(null);
    });

    it('does not call Sentry when disabled', async () => {
      vi.stubEnv('VITE_SENTRY_DSN', '');

      const { setUserContext: set } = await import('./sentry');
      set({ id: 'user-123' });

      expect(Sentry.setUser).not.toHaveBeenCalled();
    });
  });
});

describe('API Breadcrumb Integration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('addBreadcrumb creates http category breadcrumb for API calls', async () => {
    vi.stubEnv('VITE_SENTRY_DSN', 'https://test@sentry.io/123');

    const { initSentry: init, addBreadcrumb: add } = await import('./sentry');
    init();

    add({
      category: 'http',
      message: 'GET /api/cameras',
      level: 'info',
      data: {
        method: 'GET',
        url: '/api/cameras',
        status_code: 200,
      },
    });

    expect(Sentry.addBreadcrumb).toHaveBeenCalledWith({
      category: 'http',
      message: 'GET /api/cameras',
      level: 'info',
      data: {
        method: 'GET',
        url: '/api/cameras',
        status_code: 200,
      },
    });
  });

  it('addBreadcrumb creates error level breadcrumb for failed API calls', async () => {
    vi.stubEnv('VITE_SENTRY_DSN', 'https://test@sentry.io/123');

    const { initSentry: init, addBreadcrumb: add } = await import('./sentry');
    init();

    add({
      category: 'http',
      message: 'GET /api/cameras failed',
      level: 'error',
      data: {
        method: 'GET',
        url: '/api/cameras',
        status_code: 500,
        error: 'Internal Server Error',
      },
    });

    expect(Sentry.addBreadcrumb).toHaveBeenCalledWith(
      expect.objectContaining({
        category: 'http',
        level: 'error',
        data: expect.objectContaining({
          status_code: 500,
        }),
      })
    );
  });
});

describe('addApiBreadcrumb helper', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('creates a breadcrumb for successful API calls', async () => {
    vi.stubEnv('VITE_SENTRY_DSN', 'https://test@sentry.io/123');

    const { initSentry: init, addApiBreadcrumb } = await import('./sentry');
    init();

    addApiBreadcrumb('GET', '/api/cameras', 200, 150);

    expect(Sentry.addBreadcrumb).toHaveBeenCalledWith({
      category: 'http',
      message: 'GET /api/cameras',
      level: 'info',
      data: {
        method: 'GET',
        url: '/api/cameras',
        status_code: 200,
        duration_ms: 150,
      },
    });
  });

  it('creates an error level breadcrumb for failed API calls', async () => {
    vi.stubEnv('VITE_SENTRY_DSN', 'https://test@sentry.io/123');

    const { initSentry: init, addApiBreadcrumb } = await import('./sentry');
    init();

    addApiBreadcrumb('POST', '/api/events', 500);

    expect(Sentry.addBreadcrumb).toHaveBeenCalledWith({
      category: 'http',
      message: 'POST /api/events',
      level: 'error',
      data: {
        method: 'POST',
        url: '/api/events',
        status_code: 500,
      },
    });
  });

  it('creates an error level breadcrumb for 4xx errors', async () => {
    vi.stubEnv('VITE_SENTRY_DSN', 'https://test@sentry.io/123');

    const { initSentry: init, addApiBreadcrumb } = await import('./sentry');
    init();

    addApiBreadcrumb('GET', '/api/events/999', 404);

    expect(Sentry.addBreadcrumb).toHaveBeenCalledWith(
      expect.objectContaining({
        level: 'error',
        data: expect.objectContaining({
          status_code: 404,
        }),
      })
    );
  });
});
