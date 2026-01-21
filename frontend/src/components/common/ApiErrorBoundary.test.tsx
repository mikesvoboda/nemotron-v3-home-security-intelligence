/**
 * Tests for ApiErrorBoundary component (NEM-3179)
 *
 * Tests the centralized API error boundary that:
 * - Catches API errors globally
 * - Shows appropriate UI based on error type
 * - Provides retry mechanisms
 * - Distinguishes between transient and permanent errors
 * - Integrates with React Query
 */
import { QueryClient, QueryClientProvider, useMutation } from '@tanstack/react-query';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import * as React from 'react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import {
  ApiErrorBoundary,
  ApiErrorFallback,
  useApiErrorHandler,
} from './ApiErrorBoundary';
import { ApiError } from '../../services/api';
import { ErrorCode } from '../../utils/error-handling';

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: {
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  },
}));

// Create a test query client with no retries for predictable tests
function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

// Wrapper component for testing with React Query
function TestWrapper({
  children,
  queryClient,
}: {
  children: React.ReactNode;
  queryClient?: QueryClient;
}) {
  const client = queryClient ?? createTestQueryClient();
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

// Component that throws a render error
const RenderErrorComponent = ({ error }: { error: Error }) => {
  throw error;
};

describe('ApiErrorBoundary', () => {
  // Suppress console.error during tests
  const originalError = console.error;
  beforeEach(() => {
    console.error = vi.fn();
    vi.clearAllMocks();
  });
  afterEach(() => {
    console.error = originalError;
  });

  describe('normal rendering', () => {
    it('renders children when there is no error', () => {
      render(
        <TestWrapper>
          <ApiErrorBoundary>
            <div>Normal content</div>
          </ApiErrorBoundary>
        </TestWrapper>
      );
      expect(screen.getByText('Normal content')).toBeInTheDocument();
    });

    it('renders nested children without error', () => {
      render(
        <TestWrapper>
          <ApiErrorBoundary>
            <div>
              <span>Nested content</span>
            </div>
          </ApiErrorBoundary>
        </TestWrapper>
      );
      expect(screen.getByText('Nested content')).toBeInTheDocument();
    });
  });

  describe('API error catching', () => {
    it('catches and displays network errors', () => {
      const networkError = new Error('Network error');

      render(
        <TestWrapper>
          <ApiErrorBoundary>
            <RenderErrorComponent error={networkError} />
          </ApiErrorBoundary>
        </TestWrapper>
      );

      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/network error/i)).toBeInTheDocument();
    });

    it('catches and displays API errors with status codes', () => {
      const apiError = new ApiError(500, 'Internal Server Error');

      render(
        <TestWrapper>
          <ApiErrorBoundary>
            <RenderErrorComponent error={apiError} />
          </ApiErrorBoundary>
        </TestWrapper>
      );

      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/internal server error/i)).toBeInTheDocument();
    });

    it('displays appropriate UI for 404 errors (permanent)', () => {
      const notFoundError = new ApiError(404, 'Resource not found', undefined, {
        type: 'about:blank',
        title: 'Not Found',
        status: 404,
        error_code: ErrorCode.RESOURCE_NOT_FOUND,
      });

      render(
        <TestWrapper>
          <ApiErrorBoundary>
            <RenderErrorComponent error={notFoundError} />
          </ApiErrorBoundary>
        </TestWrapper>
      );

      expect(screen.getByRole('alert')).toBeInTheDocument();
      // Should not show retry for permanent errors
      expect(screen.queryByRole('button', { name: /retry/i })).not.toBeInTheDocument();
    });

    it('displays appropriate UI for 503 errors (transient)', () => {
      const serviceError = new ApiError(503, 'Service unavailable', undefined, {
        type: 'about:blank',
        title: 'Service Unavailable',
        status: 503,
        error_code: ErrorCode.SERVICE_UNAVAILABLE,
      });

      render(
        <TestWrapper>
          <ApiErrorBoundary>
            <RenderErrorComponent error={serviceError} />
          </ApiErrorBoundary>
        </TestWrapper>
      );

      expect(screen.getByRole('alert')).toBeInTheDocument();
      // Should show retry for transient errors
      expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
    });

    it('displays appropriate UI for rate limit errors with retry-after', () => {
      const rateLimitError = new ApiError(429, 'Rate limit exceeded', undefined, {
        type: 'about:blank',
        title: 'Too Many Requests',
        status: 429,
        error_code: ErrorCode.RATE_LIMIT_EXCEEDED,
        retry_after: 60,
      });

      render(
        <TestWrapper>
          <ApiErrorBoundary>
            <RenderErrorComponent error={rateLimitError} />
          </ApiErrorBoundary>
        </TestWrapper>
      );

      expect(screen.getByRole('alert')).toBeInTheDocument();
      // Check for the title or error code
      expect(screen.getByText(/too many requests/i)).toBeInTheDocument();
      expect(screen.getByText(/RATE_LIMIT_EXCEEDED/)).toBeInTheDocument();
      // Should indicate retry is possible
      expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
    });
  });

  describe('retry mechanism', () => {
    it('resets error state when retry is clicked', () => {
      let shouldThrow = true;

      const DynamicComponent = () => {
        if (shouldThrow) {
          throw new ApiError(503, 'Service unavailable', undefined, {
            type: 'about:blank',
            title: 'Service Unavailable',
            status: 503,
            error_code: ErrorCode.SERVICE_UNAVAILABLE,
          });
        }
        return <div>Content loaded successfully</div>;
      };

      render(
        <TestWrapper>
          <ApiErrorBoundary>
            <DynamicComponent />
          </ApiErrorBoundary>
        </TestWrapper>
      );

      // Should show error
      expect(screen.getByRole('alert')).toBeInTheDocument();

      // Stop throwing
      shouldThrow = false;

      // Click retry
      fireEvent.click(screen.getByRole('button', { name: /retry/i }));

      // Should show success
      expect(screen.getByText('Content loaded successfully')).toBeInTheDocument();
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });

    it('calls onRetry callback when provided', () => {
      const onRetry = vi.fn();
      const error = new ApiError(503, 'Service unavailable', undefined, {
        type: 'about:blank',
        title: 'Service Unavailable',
        status: 503,
        error_code: ErrorCode.SERVICE_UNAVAILABLE,
      });

      let shouldThrow = true;
      const DynamicComponent = () => {
        if (shouldThrow) throw error;
        return <div>Success</div>;
      };

      render(
        <TestWrapper>
          <ApiErrorBoundary onRetry={onRetry}>
            <DynamicComponent />
          </ApiErrorBoundary>
        </TestWrapper>
      );

      shouldThrow = false;
      fireEvent.click(screen.getByRole('button', { name: /retry/i }));

      expect(onRetry).toHaveBeenCalled();
    });

    it('shows refresh page option for critical errors', () => {
      const criticalError = new ApiError(500, 'Internal Server Error', undefined, {
        type: 'about:blank',
        title: 'Internal Server Error',
        status: 500,
        error_code: ErrorCode.INTERNAL_ERROR,
      });

      render(
        <TestWrapper>
          <ApiErrorBoundary>
            <RenderErrorComponent error={criticalError} />
          </ApiErrorBoundary>
        </TestWrapper>
      );

      expect(screen.getByRole('button', { name: /refresh/i })).toBeInTheDocument();
    });
  });

  describe('error classification', () => {
    it('identifies transient errors correctly', () => {
      const transientCodes = [
        ErrorCode.SERVICE_UNAVAILABLE,
        ErrorCode.TIMEOUT,
        ErrorCode.RATE_LIMIT_EXCEEDED,
        ErrorCode.DATABASE_ERROR,
      ];

      transientCodes.forEach((code) => {
        const error = new ApiError(503, code, undefined, {
          type: 'about:blank',
          title: code,
          status: 503,
          error_code: code,
        });

        const { unmount } = render(
          <TestWrapper>
            <ApiErrorBoundary>
              <RenderErrorComponent error={error} />
            </ApiErrorBoundary>
          </TestWrapper>
        );

        // Transient errors should show retry button
        expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
        unmount();
      });
    });

    it('identifies permanent errors correctly', () => {
      const permanentCodes = [
        ErrorCode.CAMERA_NOT_FOUND,
        ErrorCode.VALIDATION_ERROR,
        ErrorCode.ACCESS_DENIED,
      ];

      permanentCodes.forEach((code) => {
        const error = new ApiError(404, code, undefined, {
          type: 'about:blank',
          title: code,
          status: 404,
          error_code: code,
        });

        const { unmount } = render(
          <TestWrapper>
            <ApiErrorBoundary>
              <RenderErrorComponent error={error} />
            </ApiErrorBoundary>
          </TestWrapper>
        );

        // Permanent errors should NOT show retry button
        expect(screen.queryByRole('button', { name: /retry/i })).not.toBeInTheDocument();
        unmount();
      });
    });
  });

  describe('custom fallback', () => {
    it('renders custom fallback when provided', () => {
      const error = new ApiError(500, 'Test error');

      render(
        <TestWrapper>
          <ApiErrorBoundary fallback={<div data-testid="custom-fallback">Custom error UI</div>}>
            <RenderErrorComponent error={error} />
          </ApiErrorBoundary>
        </TestWrapper>
      );

      expect(screen.getByTestId('custom-fallback')).toBeInTheDocument();
      expect(screen.getByText('Custom error UI')).toBeInTheDocument();
    });

    it('renders fallback function with error details', () => {
      const error = new ApiError(500, 'Test error message');

      render(
        <TestWrapper>
          <ApiErrorBoundary
            fallback={(err, reset) => (
              <div data-testid="custom-fallback">
                <span>Error: {err.message}</span>
                <button onClick={reset}>Custom Retry</button>
              </div>
            )}
          >
            <RenderErrorComponent error={error} />
          </ApiErrorBoundary>
        </TestWrapper>
      );

      expect(screen.getByText(/Error: Test error message/)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /custom retry/i })).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('has role="alert" on error fallback', () => {
      const error = new ApiError(500, 'Test error');

      render(
        <TestWrapper>
          <ApiErrorBoundary>
            <RenderErrorComponent error={error} />
          </ApiErrorBoundary>
        </TestWrapper>
      );

      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('has aria-live="polite" for non-critical errors', () => {
      const error = new ApiError(429, 'Rate limited', undefined, {
        type: 'about:blank',
        title: 'Too Many Requests',
        status: 429,
        error_code: ErrorCode.RATE_LIMIT_EXCEEDED,
      });

      render(
        <TestWrapper>
          <ApiErrorBoundary>
            <RenderErrorComponent error={error} />
          </ApiErrorBoundary>
        </TestWrapper>
      );

      const alert = screen.getByRole('alert');
      expect(alert).toHaveAttribute('aria-live', 'polite');
    });

    it('has accessible button labels', () => {
      const error = new ApiError(503, 'Service unavailable', undefined, {
        type: 'about:blank',
        title: 'Service Unavailable',
        status: 503,
        error_code: ErrorCode.SERVICE_UNAVAILABLE,
      });

      render(
        <TestWrapper>
          <ApiErrorBoundary>
            <RenderErrorComponent error={error} />
          </ApiErrorBoundary>
        </TestWrapper>
      );

      expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /refresh/i })).toBeInTheDocument();
    });
  });

  describe('onError callback', () => {
    it('calls onError when error is caught', () => {
      const onError = vi.fn();
      const error = new ApiError(500, 'Test error');

      render(
        <TestWrapper>
          <ApiErrorBoundary onError={onError}>
            <RenderErrorComponent error={error} />
          </ApiErrorBoundary>
        </TestWrapper>
      );

      expect(onError).toHaveBeenCalledWith(error, expect.any(Object));
    });
  });
});

describe('ApiErrorFallback', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders error message', () => {
    const error = new ApiError(500, 'Test error message');

    render(
      <ApiErrorFallback
        error={error}
        isTransient={false}
        onRetry={() => {}}
        onRefresh={() => {}}
      />
    );

    expect(screen.getByText(/test error message/i)).toBeInTheDocument();
  });

  it('shows retry button for transient errors', () => {
    const error = new ApiError(503, 'Service unavailable');

    render(
      <ApiErrorFallback error={error} isTransient={true} onRetry={() => {}} onRefresh={() => {}} />
    );

    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
  });

  it('hides retry button for permanent errors', () => {
    const error = new ApiError(404, 'Not found');

    render(
      <ApiErrorFallback error={error} isTransient={false} onRetry={() => {}} onRefresh={() => {}} />
    );

    expect(screen.queryByRole('button', { name: /retry/i })).not.toBeInTheDocument();
  });

  it('calls onRetry when retry button is clicked', () => {
    const onRetry = vi.fn();
    const error = new ApiError(503, 'Service unavailable');

    render(
      <ApiErrorFallback error={error} isTransient={true} onRetry={onRetry} onRefresh={() => {}} />
    );

    fireEvent.click(screen.getByRole('button', { name: /retry/i }));
    expect(onRetry).toHaveBeenCalled();
  });

  it('calls onRefresh when refresh button is clicked', () => {
    const onRefresh = vi.fn();
    const error = new ApiError(500, 'Internal error');

    render(
      <ApiErrorFallback error={error} isTransient={false} onRetry={() => {}} onRefresh={onRefresh} />
    );

    fireEvent.click(screen.getByRole('button', { name: /refresh/i }));
    expect(onRefresh).toHaveBeenCalled();
  });

  it('displays RFC 7807 detail when available', () => {
    const error = new ApiError(400, 'Validation error', undefined, {
      type: 'about:blank',
      title: 'Bad Request',
      status: 400,
      detail: 'The camera ID format is invalid',
      error_code: ErrorCode.VALIDATION_ERROR,
    });

    render(
      <ApiErrorFallback error={error} isTransient={false} onRetry={() => {}} onRefresh={() => {}} />
    );

    expect(screen.getByText(/camera ID format is invalid/i)).toBeInTheDocument();
  });
});

describe('useApiErrorHandler', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns error handler function', () => {
    const TestComponent = () => {
      const handleError = useApiErrorHandler();
      return <div>{typeof handleError === 'function' ? 'valid' : 'invalid'}</div>;
    };

    render(
      <TestWrapper>
        <TestComponent />
      </TestWrapper>
    );

    expect(screen.getByText('valid')).toBeInTheDocument();
  });

  it('can be used to handle errors in mutations', async () => {
    const TestComponent = () => {
      const handleError = useApiErrorHandler();
      const [errorMessage, setErrorMessage] = React.useState<string | null>(null);

      const mutation = useMutation({
        mutationFn: () => {
          return Promise.reject(new ApiError(500, 'Mutation failed'));
        },
        onError: (error) => {
          const config = handleError(error);
          setErrorMessage(config.message);
        },
      });

      return (
        <div>
          <button onClick={() => mutation.mutate()}>Trigger</button>
          {errorMessage && <div data-testid="error-message">{errorMessage}</div>}
        </div>
      );
    };

    render(
      <TestWrapper>
        <TestComponent />
      </TestWrapper>
    );

    fireEvent.click(screen.getByText('Trigger'));

    await waitFor(() => {
      expect(screen.getByTestId('error-message')).toBeInTheDocument();
    });
  });
});
