/**
 * Tests for ChunkLoadErrorBoundary component
 *
 * TDD RED Phase - These tests define the expected behavior of the error boundary
 * that specifically handles dynamic import/chunk loading failures.
 */
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import ChunkLoadErrorBoundary from './ChunkLoadErrorBoundary';

// Component that throws a chunk load error
function ThrowChunkLoadError(): never {
  const error = new Error('Loading chunk main failed');
  error.name = 'ChunkLoadError';
  throw error;
}

// Component that throws a generic error
function ThrowGenericError(): never {
  throw new Error('Generic error');
}

// Component that renders normally
function NormalComponent() {
  return <div data-testid="normal-content">Normal content</div>;
}

describe('ChunkLoadErrorBoundary', () => {
  // Suppress console.error during tests since we expect errors
  const originalConsoleError = console.error;

  beforeEach(() => {
    console.error = vi.fn();
  });

  afterEach(() => {
    console.error = originalConsoleError;
  });

  it('renders children when there is no error', () => {
    render(
      <ChunkLoadErrorBoundary>
        <NormalComponent />
      </ChunkLoadErrorBoundary>
    );
    expect(screen.getByTestId('normal-content')).toBeInTheDocument();
  });

  it('catches chunk load errors and displays fallback UI', () => {
    render(
      <ChunkLoadErrorBoundary>
        <ThrowChunkLoadError />
      </ChunkLoadErrorBoundary>
    );

    // Should show chunk-specific error message
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /failed to load page/i })).toBeInTheDocument();
  });

  it('provides a reload button for chunk load errors', async () => {
    const user = userEvent.setup();

    // Mock window.location.reload using Object.assign to replace the whole location
    const reloadMock = vi.fn();
    const originalLocation = window.location;
    // Use delete and reassignment pattern that works in jsdom
    // @ts-expect-error - Need to delete window.location for mock in jsdom
    delete window.location;
    // @ts-expect-error - Assigning mock location for testing purposes
    window.location = { ...originalLocation, reload: reloadMock } as Location;

    render(
      <ChunkLoadErrorBoundary>
        <ThrowChunkLoadError />
      </ChunkLoadErrorBoundary>
    );

    const reloadButton = screen.getByRole('button', { name: /reload/i });
    await user.click(reloadButton);

    expect(reloadMock).toHaveBeenCalledTimes(1);

    // Restore original location
    // @ts-expect-error - Restoring original location after mock
    window.location = originalLocation;
  });

  it('re-throws non-chunk-load errors to parent error boundaries', () => {
    // This tests that generic errors are not caught by this specialized boundary
    expect(() => {
      render(
        <ChunkLoadErrorBoundary>
          <ThrowGenericError />
        </ChunkLoadErrorBoundary>
      );
    }).toThrow('Generic error');
  });

  it('displays accessible error message with proper ARIA attributes', () => {
    render(
      <ChunkLoadErrorBoundary>
        <ThrowChunkLoadError />
      </ChunkLoadErrorBoundary>
    );

    const alert = screen.getByRole('alert');
    expect(alert).toHaveAttribute('aria-live', 'assertive');
  });

  it('accepts custom onError callback', () => {
    const onError = vi.fn();

    render(
      <ChunkLoadErrorBoundary onError={onError}>
        <ThrowChunkLoadError />
      </ChunkLoadErrorBoundary>
    );

    expect(onError).toHaveBeenCalledTimes(1);
    expect(onError).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'ChunkLoadError' }),
      expect.any(Object)
    );
  });
});
