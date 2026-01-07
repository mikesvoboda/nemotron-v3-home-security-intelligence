/**
 * ChunkLoadErrorBoundary - Specialized error boundary for dynamic import failures
 *
 * This error boundary specifically handles chunk/module loading failures that
 * can occur when using React.lazy() and dynamic imports. These errors typically
 * happen due to:
 * - Network issues during chunk fetch
 * - Stale deployment where chunks have been replaced
 * - Browser cache issues
 *
 * For chunk load errors, it provides a user-friendly message with a reload button.
 * For other errors, it re-throws them to be handled by parent error boundaries.
 *
 * @example
 * <ChunkLoadErrorBoundary>
 *   <Suspense fallback={<RouteLoadingFallback />}>
 *     <LazyComponent />
 *   </Suspense>
 * </ChunkLoadErrorBoundary>
 */

import { AlertTriangle, RefreshCw } from 'lucide-react';
import { Component, type ErrorInfo, type ReactNode } from 'react';

export interface ChunkLoadErrorBoundaryProps {
  /** Child components to wrap */
  children: ReactNode;
  /** Optional callback when an error is caught */
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

export interface ChunkLoadErrorBoundaryState {
  hasChunkError: boolean;
  error: Error | null;
}

/**
 * Check if an error is a chunk/module loading error.
 * These errors occur when dynamic imports fail.
 */
function isChunkLoadError(error: Error): boolean {
  const message = error.message.toLowerCase();
  const name = error.name;

  return (
    name === 'ChunkLoadError' ||
    message.includes('loading chunk') ||
    message.includes('loading css chunk') ||
    message.includes('failed to fetch dynamically imported module') ||
    message.includes('dynamically imported module') ||
    // Vite-specific error patterns
    message.includes('failed to load module script') ||
    message.includes('error loading dynamically imported module')
  );
}

/**
 * ChunkLoadErrorBoundary catches chunk loading errors from React.lazy()
 * and displays a recovery UI. Non-chunk errors are re-thrown to parent
 * error boundaries.
 */
export default class ChunkLoadErrorBoundary extends Component<
  ChunkLoadErrorBoundaryProps,
  ChunkLoadErrorBoundaryState
> {
  constructor(props: ChunkLoadErrorBoundaryProps) {
    super(props);
    this.state = {
      hasChunkError: false,
      error: null,
    };
  }

  /**
   * Update state when an error is caught during rendering.
   * Only catches chunk load errors - others are re-thrown.
   */
  static getDerivedStateFromError(error: Error): Partial<ChunkLoadErrorBoundaryState> | null {
    if (isChunkLoadError(error)) {
      return {
        hasChunkError: true,
        error,
      };
    }
    // Re-throw non-chunk errors
    throw error;
  }

  /**
   * Log error information and call optional callback.
   */
  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    if (!isChunkLoadError(error)) {
      // This shouldn't happen due to getDerivedStateFromError,
      // but just in case, re-throw non-chunk errors
      throw error;
    }

    // Log chunk load error
    console.error('ChunkLoadErrorBoundary caught chunk load error:', error);

    // Call optional error callback
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }
  }

  /**
   * Reload the page to fetch fresh chunks.
   */
  handleReload = (): void => {
    window.location.reload();
  };

  render(): ReactNode {
    const { hasChunkError, error } = this.state;
    const { children } = this.props;

    if (hasChunkError) {
      return (
        <div
          role="alert"
          aria-live="assertive"
          className="flex min-h-[400px] w-full flex-col items-center justify-center p-8 text-center"
        >
          <div className="max-w-md rounded-lg border border-yellow-500/20 bg-yellow-500/5 p-8">
            <AlertTriangle
              className="mx-auto mb-4 h-12 w-12 text-yellow-500"
              aria-hidden="true"
            />
            <h2 className="mb-2 text-lg font-semibold text-white">
              Failed to Load Page
            </h2>
            <p className="mb-4 text-sm text-gray-400">
              The page failed to load. This can happen due to a network issue or an
              application update. Please reload to try again.
            </p>
            {error && import.meta.env.DEV && (
              <p className="mb-4 rounded bg-gray-800/50 px-3 py-2 font-mono text-xs text-yellow-400">
                {error.message}
              </p>
            )}
            <button
              type="button"
              onClick={this.handleReload}
              className="inline-flex items-center gap-2 rounded-md bg-primary-500 px-4 py-2 text-sm font-medium text-gray-950 transition-colors hover:bg-primary-600 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 focus:ring-offset-gray-900"
            >
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
              Reload Page
            </button>
          </div>
        </div>
      );
    }

    return children;
  }
}
