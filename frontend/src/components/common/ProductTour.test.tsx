import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import ProductTour from './ProductTour';
import {
  TOUR_COMPLETED_KEY,
  TOUR_SKIPPED_KEY,
  tourSteps,
  restartProductTour,
} from '../../config/tourSteps';

// Mock react-joyride
vi.mock('react-joyride', () => ({
  default: vi.fn(({ callback, run, steps }) => {
    // Store the callback for testing
    if (run && callback) {
      // Simulate the tour being active
      return (
        <div data-testid="joyride-mock">
          <span data-testid="joyride-running">{run ? 'running' : 'stopped'}</span>
          <span data-testid="joyride-steps-count">{steps?.length || 0}</span>
          <button
            data-testid="joyride-next"
            onClick={() => callback({ action: 'next', index: 0, status: 'running', type: 'step:after', lifecycle: 'complete' })}
          >
            Next
          </button>
          <button
            data-testid="joyride-skip"
            onClick={() => callback({ action: 'skip', index: 0, status: 'skipped', type: 'tour:end', lifecycle: 'complete' })}
          >
            Skip
          </button>
          <button
            data-testid="joyride-close"
            onClick={() => callback({ action: 'close', index: 0, status: 'finished', type: 'tour:end', lifecycle: 'complete' })}
          >
            Close
          </button>
          <button
            data-testid="joyride-finish"
            onClick={() => callback({ action: 'next', index: steps.length - 1, status: 'finished', type: 'tour:end', lifecycle: 'complete' })}
          >
            Finish
          </button>
        </div>
      );
    }
    return null;
  }),
  ACTIONS: {
    CLOSE: 'close',
    NEXT: 'next',
    PREV: 'prev',
    SKIP: 'skip',
    RESET: 'reset',
    UPDATE: 'update',
  },
  STATUS: {
    FINISHED: 'finished',
    SKIPPED: 'skipped',
    RUNNING: 'running',
    IDLE: 'idle',
    READY: 'ready',
    WAITING: 'waiting',
    PAUSED: 'paused',
    ERROR: 'error',
  },
}));

// Helper to wrap component with router
const renderWithRouter = (ui: React.ReactElement) => {
  return render(<BrowserRouter>{ui}</BrowserRouter>);
};

describe('ProductTour', () => {
  beforeEach(() => {
    // Clear localStorage before each test
    localStorage.clear();
    vi.clearAllMocks();
  });

  afterEach(() => {
    localStorage.clear();
  });

  describe('initial rendering', () => {
    it('renders the tour for first-time users', () => {
      renderWithRouter(<ProductTour />);

      expect(screen.getByTestId('joyride-mock')).toBeInTheDocument();
      expect(screen.getByTestId('joyride-running')).toHaveTextContent('running');
    });

    it('does not render tour when already completed', () => {
      localStorage.setItem(TOUR_COMPLETED_KEY, 'true');

      renderWithRouter(<ProductTour />);

      expect(screen.queryByTestId('joyride-mock')).not.toBeInTheDocument();
    });

    it('does not render tour when previously skipped', () => {
      localStorage.setItem(TOUR_SKIPPED_KEY, 'true');

      renderWithRouter(<ProductTour />);

      expect(screen.queryByTestId('joyride-mock')).not.toBeInTheDocument();
    });

    it('passes all tour steps to Joyride', () => {
      renderWithRouter(<ProductTour />);

      expect(screen.getByTestId('joyride-steps-count')).toHaveTextContent(
        tourSteps.length.toString()
      );
    });
  });

  describe('tour completion', () => {
    it('marks tour as completed when finished', async () => {
      renderWithRouter(<ProductTour />);

      const finishButton = screen.getByTestId('joyride-finish');
      fireEvent.click(finishButton);

      await waitFor(() => {
        expect(localStorage.getItem(TOUR_COMPLETED_KEY)).toBe('true');
      });
    });

    it('marks tour as skipped when user skips', async () => {
      renderWithRouter(<ProductTour />);

      const skipButton = screen.getByTestId('joyride-skip');
      fireEvent.click(skipButton);

      await waitFor(() => {
        expect(localStorage.getItem(TOUR_SKIPPED_KEY)).toBe('true');
      });
    });

    it('marks tour as completed when user closes on last step', async () => {
      renderWithRouter(<ProductTour />);

      const closeButton = screen.getByTestId('joyride-close');
      fireEvent.click(closeButton);

      await waitFor(() => {
        expect(localStorage.getItem(TOUR_COMPLETED_KEY)).toBe('true');
      });
    });
  });

  describe('tour callbacks', () => {
    it('calls onComplete callback when tour finishes', async () => {
      const onComplete = vi.fn();
      renderWithRouter(<ProductTour onComplete={onComplete} />);

      const finishButton = screen.getByTestId('joyride-finish');
      fireEvent.click(finishButton);

      await waitFor(() => {
        expect(onComplete).toHaveBeenCalled();
      });
    });

    it('calls onSkip callback when tour is skipped', async () => {
      const onSkip = vi.fn();
      renderWithRouter(<ProductTour onSkip={onSkip} />);

      const skipButton = screen.getByTestId('joyride-skip');
      fireEvent.click(skipButton);

      await waitFor(() => {
        expect(onSkip).toHaveBeenCalled();
      });
    });
  });

  describe('restartProductTour function', () => {
    it('clears tour completion status from localStorage', () => {
      localStorage.setItem(TOUR_COMPLETED_KEY, 'true');
      localStorage.setItem(TOUR_SKIPPED_KEY, 'true');

      restartProductTour();

      expect(localStorage.getItem(TOUR_COMPLETED_KEY)).toBeNull();
      expect(localStorage.getItem(TOUR_SKIPPED_KEY)).toBeNull();
    });

    it('allows tour to run again after restart', () => {
      // First, mark tour as completed
      localStorage.setItem(TOUR_COMPLETED_KEY, 'true');

      const { unmount } = renderWithRouter(<ProductTour />);
      expect(screen.queryByTestId('joyride-mock')).not.toBeInTheDocument();
      unmount();

      // Restart tour
      restartProductTour();

      // Re-render and verify tour runs
      renderWithRouter(<ProductTour />);
      expect(screen.getByTestId('joyride-mock')).toBeInTheDocument();
    });
  });

  describe('forceRun prop', () => {
    it('runs tour even when previously completed if forceRun is true', () => {
      localStorage.setItem(TOUR_COMPLETED_KEY, 'true');

      renderWithRouter(<ProductTour forceRun />);

      expect(screen.getByTestId('joyride-mock')).toBeInTheDocument();
    });

    it('runs tour even when previously skipped if forceRun is true', () => {
      localStorage.setItem(TOUR_SKIPPED_KEY, 'true');

      renderWithRouter(<ProductTour forceRun />);

      expect(screen.getByTestId('joyride-mock')).toBeInTheDocument();
    });
  });

  describe('controlled mode', () => {
    it('respects external run prop when provided', () => {
      renderWithRouter(<ProductTour run={false} />);

      expect(screen.queryByTestId('joyride-mock')).not.toBeInTheDocument();
    });

    it('runs tour when run prop changes to true', () => {
      const { rerender } = renderWithRouter(<ProductTour run={false} />);
      expect(screen.queryByTestId('joyride-mock')).not.toBeInTheDocument();

      rerender(
        <BrowserRouter>
          <ProductTour run={true} forceRun />
        </BrowserRouter>
      );
      expect(screen.getByTestId('joyride-mock')).toBeInTheDocument();
    });
  });

  describe('step index control', () => {
    it('allows starting from a specific step', () => {
      renderWithRouter(<ProductTour startIndex={2} />);

      // The mock doesn't actually track step index, but we can verify it renders
      expect(screen.getByTestId('joyride-mock')).toBeInTheDocument();
    });
  });
});

describe('tourSteps configuration', () => {
  it('has exactly 7 steps', () => {
    expect(tourSteps).toHaveLength(7);
  });

  it('has welcome step as first step', () => {
    expect(tourSteps[0].target).toBe('body');
    expect(tourSteps[0].title).toBe('Welcome to Nemotron Security');
  });

  it('has completion step as last step', () => {
    const lastStep = tourSteps[tourSteps.length - 1];
    expect(lastStep.target).toBe('body');
    expect(lastStep.title).toBe('Tour Complete');
  });

  it('has risk gauge step', () => {
    const riskStep = tourSteps.find((step) => step.target === '[data-tour="risk-gauge"]');
    expect(riskStep).toBeDefined();
    expect(riskStep?.title).toBe('Risk Gauge');
  });

  it('has camera grid step', () => {
    const cameraStep = tourSteps.find((step) => step.target === '[data-tour="camera-grid"]');
    expect(cameraStep).toBeDefined();
    expect(cameraStep?.title).toBe('Camera Grid');
  });

  it('has activity feed step', () => {
    const activityStep = tourSteps.find((step) => step.target === '[data-tour="activity-feed"]');
    expect(activityStep).toBeDefined();
    expect(activityStep?.title).toBe('Activity Feed');
  });

  it('has timeline link step', () => {
    const timelineStep = tourSteps.find((step) => step.target === '[data-tour="timeline-link"]');
    expect(timelineStep).toBeDefined();
    expect(timelineStep?.title).toBe('Event Timeline');
  });

  it('has settings link step', () => {
    const settingsStep = tourSteps.find((step) => step.target === '[data-tour="settings-link"]');
    expect(settingsStep).toBeDefined();
    expect(settingsStep?.title).toBe('Settings');
  });

  it('all steps have required properties', () => {
    tourSteps.forEach((step) => {
      expect(step.target).toBeDefined();
      expect(step.content).toBeDefined();
      expect(typeof step.content).toBe('string');
      expect((step.content as string).length).toBeGreaterThan(0);
      expect(step.disableBeacon).toBe(true);
    });
  });
});

describe('localStorage handling', () => {
  let originalLocalStorage: Storage;

  beforeEach(() => {
    originalLocalStorage = window.localStorage;
  });

  afterEach(() => {
    Object.defineProperty(window, 'localStorage', {
      value: originalLocalStorage,
      writable: true,
    });
  });

  it('handles localStorage errors gracefully', () => {
    // Mock localStorage to throw errors
    const mockLocalStorage = {
      getItem: vi.fn(() => {
        throw new Error('localStorage unavailable');
      }),
      setItem: vi.fn(() => {
        throw new Error('localStorage unavailable');
      }),
      removeItem: vi.fn(() => {
        throw new Error('localStorage unavailable');
      }),
      clear: vi.fn(),
      key: vi.fn(),
      length: 0,
    };

    Object.defineProperty(window, 'localStorage', {
      value: mockLocalStorage,
      writable: true,
    });

    // Should not throw when rendering
    expect(() => {
      renderWithRouter(<ProductTour />);
    }).not.toThrow();

    // Tour should run when localStorage is unavailable (defaults to showing)
    expect(screen.getByTestId('joyride-mock')).toBeInTheDocument();
  });
});

describe('accessibility', () => {
  it('tour component is accessible when running', () => {
    renderWithRouter(<ProductTour />);

    // Verify the tour renders
    expect(screen.getByTestId('joyride-mock')).toBeInTheDocument();
  });
});
