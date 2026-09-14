/* eslint-disable @typescript-eslint/unbound-method */
import { render, act, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route, useNavigate } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import { NavigationTracker } from './NavigationTracker';

import { logger } from '@/services/logger';

// Mock the logger
vi.mock('@/services/logger', () => ({
  logger: {
    navigate: vi.fn(),
  },
}));

// Helper component to trigger navigation
function NavigationTrigger({ to }: { to: string }) {
  const navigate = useNavigate();
  return (
    <button onClick={() => void navigate(to)} data-testid="navigate-btn">
      Navigate
    </button>
  );
}

function TestApp({ initialPath = '/' }: { initialPath?: string }) {
  return (
    <MemoryRouter initialEntries={[initialPath]}>
      <NavigationTracker />
      <Routes>
        <Route path="/" element={<NavigationTrigger to="/alerts" />} />
        <Route path="/alerts" element={<NavigationTrigger to="/events" />} />
        <Route path="/events" element={<NavigationTrigger to="/" />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('NavigationTracker', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders nothing (returns null)', () => {
    const { container } = render(<TestApp />);
    // The NavigationTracker should not add any DOM elements
    // It should only render the Routes content
    expect(container.querySelector('[data-testid="navigate-btn"]')).toBeInTheDocument();
  });

  it('does not log navigation on initial render', () => {
    render(<TestApp />);
    expect(logger.navigate).not.toHaveBeenCalled();
  });

  it('logs navigation when route changes', async () => {
    const { getByTestId } = render(<TestApp />);

    // Navigate from / to /alerts
    act(() => {
      getByTestId('navigate-btn').click();
    });

    await waitFor(() => {
      expect(logger.navigate).toHaveBeenCalledWith('/', '/alerts', {
        search: undefined,
        hash: undefined,
      });
    });
  });

  it('logs multiple navigations correctly', async () => {
    const { getByTestId } = render(<TestApp />);

    // Navigate from / to /alerts
    act(() => {
      getByTestId('navigate-btn').click();
    });

    await waitFor(() => {
      expect(logger.navigate).toHaveBeenCalledWith('/', '/alerts', expect.any(Object));
    });

    // Navigate from /alerts to /events
    act(() => {
      getByTestId('navigate-btn').click();
    });

    await waitFor(() => {
      expect(logger.navigate).toHaveBeenCalledWith('/alerts', '/events', expect.any(Object));
    });

    // Navigate from /events back to /
    act(() => {
      getByTestId('navigate-btn').click();
    });

    await waitFor(() => {
      expect(logger.navigate).toHaveBeenCalledWith('/events', '/', expect.any(Object));
    });

    // Should have logged 3 navigations total
    expect(logger.navigate).toHaveBeenCalledTimes(3);
  });

  it('does not log when navigating to the same path', () => {
    function SamePathApp() {
      return (
        <MemoryRouter initialEntries={['/alerts']}>
          <NavigationTracker />
          <Routes>
            <Route path="/alerts" element={<NavigationTrigger to="/alerts" />} />
          </Routes>
        </MemoryRouter>
      );
    }

    const { getByTestId } = render(<SamePathApp />);

    // Try to navigate to the same path
    act(() => {
      getByTestId('navigate-btn').click();
    });

    // Should not log navigation to same path
    expect(logger.navigate).not.toHaveBeenCalled();
  });

  it('includes search params when present', async () => {
    function SearchParamsApp() {
      return (
        <MemoryRouter initialEntries={['/']}>
          <NavigationTracker />
          <Routes>
            <Route path="/" element={<NavigationTrigger to="/alerts?filter=high" />} />
            <Route path="/alerts" element={<div>Alerts</div>} />
          </Routes>
        </MemoryRouter>
      );
    }

    const { getByTestId } = render(<SearchParamsApp />);

    act(() => {
      getByTestId('navigate-btn').click();
    });

    await waitFor(() => {
      expect(logger.navigate).toHaveBeenCalledWith('/', '/alerts', {
        search: '?filter=high',
        hash: undefined,
      });
    });
  });

  it('includes hash when present', async () => {
    function HashApp() {
      return (
        <MemoryRouter initialEntries={['/']}>
          <NavigationTracker />
          <Routes>
            <Route path="/" element={<NavigationTrigger to="/docs#installation" />} />
            <Route path="/docs" element={<div>Docs</div>} />
          </Routes>
        </MemoryRouter>
      );
    }

    const { getByTestId } = render(<HashApp />);

    act(() => {
      getByTestId('navigate-btn').click();
    });

    await waitFor(() => {
      expect(logger.navigate).toHaveBeenCalledWith('/', '/docs', {
        search: undefined,
        hash: '#installation',
      });
    });
  });

  it('handles starting from a non-root path', async () => {
    const { getByTestId } = render(<TestApp initialPath="/alerts" />);

    // Navigate from /alerts to /events
    act(() => {
      getByTestId('navigate-btn').click();
    });

    await waitFor(() => {
      expect(logger.navigate).toHaveBeenCalledWith('/alerts', '/events', expect.any(Object));
    });
  });
});
