import { screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import ProductTour from './ProductTour';
import {
  TOUR_COMPLETED_KEY,
  TOUR_SKIPPED_KEY,
  tourSteps,
  restartProductTour,
} from '../../config/tourSteps';
import { renderWithNavigation } from '../../test-utils';

// Mock react-joyride
vi.mock('react-joyride', () => ({
  default: vi.fn(({ callback, run, steps, stepIndex }) => {
    // Store the callback for testing
    if (run && callback) {
      // Simulate the tour being active
      return (
        <div data-testid="joyride-mock">
          <span data-testid="joyride-running">{run ? 'running' : 'stopped'}</span>
          <span data-testid="joyride-steps-count">{steps?.length || 0}</span>
          <span data-testid="joyride-step-index">{stepIndex ?? 'uncontrolled'}</span>
          {/* Fires the callback Joyride fires for a step whose target matches no
              mounted element (react-joyride EVENTS.TARGET_NOT_FOUND). Index 1 is a
              mid-tour dead step; the tour has 7 steps so index 6 is the last. */}
          <button
            data-testid="joyride-target-missing"
            onClick={() =>
              callback({
                action: 'prev',
                index: 1,
                status: 'running',
                type: 'error:target_not_found',
              })
            }
          >
            Target Missing (step 2)
          </button>
          <button
            data-testid="joyride-target-missing-last"
            onClick={() =>
              callback({
                action: 'next',
                index: 6,
                status: 'running',
                type: 'error:target_not_found',
              })
            }
          >
            Target Missing (last step)
          </button>
          <button
            data-testid="joyride-next"
            onClick={() =>
              callback({
                action: 'next',
                index: 0,
                status: 'running',
                type: 'step:after',
                lifecycle: 'complete',
              })
            }
          >
            Next
          </button>
          <button
            data-testid="joyride-skip"
            onClick={() =>
              callback({
                action: 'skip',
                index: 0,
                status: 'skipped',
                type: 'tour:end',
                lifecycle: 'complete',
              })
            }
          >
            Skip
          </button>
          <button
            data-testid="joyride-close"
            onClick={() =>
              callback({
                action: 'close',
                index: 0,
                status: 'running',
                type: 'tour:end',
                lifecycle: 'complete',
              })
            }
          >
            Close
          </button>
          {/* Simulates overlay click or escape key - close action without tour:end */}
          <button
            data-testid="joyride-overlay-close"
            onClick={() =>
              callback({
                action: 'close',
                index: 0,
                status: 'running',
                type: 'tooltip',
                lifecycle: 'complete',
              })
            }
          >
            Overlay Close
          </button>
          <button
            data-testid="joyride-finish"
            onClick={() =>
              callback({
                action: 'next',
                index: steps.length - 1,
                status: 'finished',
                type: 'tour:end',
                lifecycle: 'complete',
              })
            }
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
  EVENTS: {
    TOUR_START: 'tour:start',
    STEP_BEFORE: 'step:before',
    BEACON: 'beacon',
    TOOLTIP: 'tooltip',
    STEP_AFTER: 'step:after',
    TOUR_END: 'tour:end',
    TOUR_STATUS: 'tour:status',
    TARGET_NOT_FOUND: 'error:target_not_found',
    ERROR: 'error',
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

// Helper to wrap component with shared navigation fixture
const renderWithRouter = (ui: React.ReactElement) => {
  return renderWithNavigation(ui, { useMemoryRouter: false });
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

    it('persists dismissal across page visits - tour does not show after completion', async () => {
      // First visit: tour runs and user completes it
      const { unmount } = renderWithRouter(<ProductTour />);
      expect(screen.getByTestId('joyride-mock')).toBeInTheDocument();

      const finishButton = screen.getByTestId('joyride-finish');
      fireEvent.click(finishButton);

      await waitFor(() => {
        expect(localStorage.getItem(TOUR_COMPLETED_KEY)).toBe('true');
      });

      unmount();

      // Second visit: tour should NOT show
      renderWithRouter(<ProductTour />);
      expect(screen.queryByTestId('joyride-mock')).not.toBeInTheDocument();
    });

    it('persists dismissal across page visits - tour does not show after skip', async () => {
      // First visit: tour runs and user skips it
      const { unmount } = renderWithRouter(<ProductTour />);
      expect(screen.getByTestId('joyride-mock')).toBeInTheDocument();

      const skipButton = screen.getByTestId('joyride-skip');
      fireEvent.click(skipButton);

      await waitFor(() => {
        expect(localStorage.getItem(TOUR_SKIPPED_KEY)).toBe('true');
      });

      unmount();

      // Second visit: tour should NOT show
      renderWithRouter(<ProductTour />);
      expect(screen.queryByTestId('joyride-mock')).not.toBeInTheDocument();
    });

    it('persists dismissal across page visits - tour does not show after close', async () => {
      // First visit: tour runs and user closes it
      const { unmount } = renderWithRouter(<ProductTour />);
      expect(screen.getByTestId('joyride-mock')).toBeInTheDocument();

      const closeButton = screen.getByTestId('joyride-close');
      fireEvent.click(closeButton);

      await waitFor(() => {
        expect(localStorage.getItem(TOUR_COMPLETED_KEY)).toBe('true');
      });

      unmount();

      // Second visit: tour should NOT show
      renderWithRouter(<ProductTour />);
      expect(screen.queryByTestId('joyride-mock')).not.toBeInTheDocument();
    });

    it('persists dismissal when closing via overlay click (NEM-3518)', async () => {
      // This tests the bug fix for NEM-3518 where close via overlay/escape
      // might not trigger tour:end event
      const { unmount } = renderWithRouter(<ProductTour />);
      expect(screen.getByTestId('joyride-mock')).toBeInTheDocument();

      const overlayCloseButton = screen.getByTestId('joyride-overlay-close');
      fireEvent.click(overlayCloseButton);

      await waitFor(() => {
        expect(localStorage.getItem(TOUR_COMPLETED_KEY)).toBe('true');
      });

      unmount();

      // Second visit: tour should NOT show
      renderWithRouter(<ProductTour />);
      expect(screen.queryByTestId('joyride-mock')).not.toBeInTheDocument();
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

  describe('dead-target resilience (F-021)', () => {
    it('advances past a step whose target never mounted instead of stalling', async () => {
      renderWithRouter(<ProductTour />);
      expect(screen.getByTestId('joyride-step-index')).toHaveTextContent('0');

      fireEvent.click(screen.getByTestId('joyride-target-missing'));

      // Joyride would only self-advance when UNcontrolled (react-joyride 2.9.3
      // TARGET_NOT_FOUND branch runs `if (!controlled)`), and this component is
      // always controlled — so without ProductTour's own branch the tour stalls on
      // the dead step with its DOM removed: F-021's measured failure. The branch
      // does what uncontrolled Joyride would — move to the next step.
      await waitFor(() => {
        expect(screen.getByTestId('joyride-step-index')).toHaveTextContent('2');
      });
      // Still alive, and nothing stored: a skipped-over step is not a dismissal.
      expect(screen.getByTestId('joyride-mock')).toBeInTheDocument();
      expect(localStorage.getItem(TOUR_COMPLETED_KEY)).toBeNull();
      expect(localStorage.getItem(TOUR_SKIPPED_KEY)).toBeNull();
    });

    it("finishes when the last step's target is missing instead of stalling", async () => {
      const onComplete = vi.fn();
      renderWithRouter(<ProductTour onComplete={onComplete} />);

      fireEvent.click(screen.getByTestId('joyride-target-missing-last'));

      await waitFor(() => {
        expect(onComplete).toHaveBeenCalled();
        expect(localStorage.getItem(TOUR_COMPLETED_KEY)).toBe('true');
      });
      expect(screen.queryByTestId('joyride-mock')).not.toBeInTheDocument();
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

      rerender(<ProductTour run={true} forceRun />);
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

  it('has a risk step targeting the risk card that actually renders', () => {
    // F-021: this step targeted [data-tour="risk-gauge"], a selector no component
    // ever wrote (the rendered element is StatsRow's risk-card). A dead target
    // killed the whole tour, so the config now points at the real element.
    const riskStep = tourSteps.find((step) => step.target === '[data-tour="risk-card"]');
    expect(riskStep).toBeDefined();
    expect(riskStep?.title).toBe('Risk Level');
    // And the old dead selector is gone from the whole config.
    expect(tourSteps.some((step) => step.target === '[data-tour="risk-gauge"]')).toBe(false);
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
