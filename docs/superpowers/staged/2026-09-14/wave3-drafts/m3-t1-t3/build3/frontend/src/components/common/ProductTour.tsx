/**
 * ProductTour component for guiding first-time users through the dashboard.
 *
 * Uses react-joyride to create an interactive tour with NVIDIA-branded styling.
 * The tour automatically runs for first-time users and can be restarted from Settings.
 *
 * @module components/common/ProductTour
 */

import { useState, useCallback, useEffect } from 'react';
import Joyride, { CallBackProps, ACTIONS, EVENTS, STATUS } from 'react-joyride';

import {
  tourSteps,
  defaultTourStyles,
  mobileTourStyles,
  shouldShowTour,
  markTourCompleted,
  markTourSkipped,
} from '../../config/tourSteps';

/**
 * Props for the ProductTour component.
 */
export interface ProductTourProps {
  /**
   * External control for running the tour.
   * When provided, overrides the internal shouldShowTour logic.
   */
  run?: boolean;

  /**
   * Force the tour to run even if previously completed/skipped.
   * Useful for restarting the tour from settings.
   */
  forceRun?: boolean;

  /**
   * Starting step index (0-based).
   * Defaults to 0 (first step).
   */
  startIndex?: number;

  /**
   * Callback fired when the tour completes successfully.
   */
  onComplete?: () => void;

  /**
   * Callback fired when the user skips the tour.
   */
  onSkip?: () => void;

  /**
   * Callback fired when tour step changes.
   */
  onStepChange?: (stepIndex: number) => void;
}

/**
 * Check if the viewport is mobile-sized.
 */
function useIsMobile(): boolean {
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768);
    };

    // Check on mount
    checkMobile();

    // Listen for resize
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  return isMobile;
}

/**
 * Interactive product tour component for first-time users.
 *
 * Features:
 * - 7-step tour covering main dashboard features
 * - NVIDIA dark theme styling
 * - Mobile-responsive tooltips
 * - localStorage persistence for completion status
 * - Restart capability via exported function
 *
 * @example
 * ```tsx
 * // Basic usage in App.tsx
 * <ProductTour />
 *
 * // With callbacks
 * <ProductTour
 *   onComplete={() => showNotificationPrompt()}
 *   onSkip={() => logAnalytics('tour_skipped')}
 * />
 *
 * // Force restart from Settings
 * import { restartProductTour } from './ProductTour';
 * <button onClick={restartProductTour}>Restart Tour</button>
 * ```
 */
export default function ProductTour({
  run: externalRun,
  forceRun = false,
  startIndex = 0,
  onComplete,
  onSkip,
  onStepChange,
}: ProductTourProps) {
  // Track internal run state
  const [internalRun, setInternalRun] = useState(() => {
    // If forceRun is true, always start running
    if (forceRun) return true;
    // If external run prop is provided, defer to it
    if (externalRun !== undefined) return externalRun;
    // Otherwise check localStorage
    return shouldShowTour();
  });

  // Track current step index
  const [stepIndex, setStepIndex] = useState(startIndex);

  // Check for mobile viewport
  const isMobile = useIsMobile();

  // Determine which styles to use
  const styles = isMobile ? mobileTourStyles : defaultTourStyles;

  // Update internal state when external props change
  useEffect(() => {
    if (forceRun) {
      setInternalRun(true);
      setStepIndex(startIndex);
    } else if (externalRun !== undefined) {
      setInternalRun(externalRun);
    }
  }, [externalRun, forceRun, startIndex]);

  /**
   * Handle tour callbacks from Joyride.
   */
  const handleJoyrideCallback = useCallback(
    (data: CallBackProps) => {
      const { action, index, status, type } = data;

      // Handle step changes - only advance on step:after events
      if (type === EVENTS.STEP_AFTER) {
        if (action === ACTIONS.NEXT) {
          setStepIndex(index + 1);
          onStepChange?.(index + 1);
        } else if (action === ACTIONS.PREV) {
          setStepIndex(index - 1);
          onStepChange?.(index - 1);
        }
      }

      // Handle close action at any point (overlay click, escape key, or X button)
      // This must be checked before tour end events because close actions
      // may not always trigger a tour:end event (NEM-3518 fix)
      if (action === ACTIONS.CLOSE) {
        setInternalRun(false);
        markTourCompleted();
        onComplete?.();
        return; // Exit early to prevent duplicate handling
      }

      // Handle tour end events (completion or skip)
      if (type === EVENTS.TOUR_END) {
        if (status === STATUS.FINISHED) {
          // User completed the tour by clicking through all steps
          setInternalRun(false);
          markTourCompleted();
          onComplete?.();
        } else if (status === STATUS.SKIPPED) {
          // User clicked the Skip button
          setInternalRun(false);
          markTourSkipped();
          onSkip?.();
        }
      }
    },
    [onComplete, onSkip, onStepChange]
  );

  // Determine if tour should run
  const shouldRun =
    externalRun !== undefined ? externalRun && (forceRun || shouldShowTour()) : internalRun;

  // Don't render anything if not running
  if (!shouldRun) {
    return null;
  }

  return (
    <Joyride
      steps={tourSteps}
      run={shouldRun}
      stepIndex={stepIndex}
      callback={handleJoyrideCallback}
      continuous
      showProgress
      showSkipButton
      hideCloseButton={false}
      disableCloseOnEsc={false}
      disableOverlayClose={false}
      spotlightPadding={8}
      styles={styles}
      locale={{
        back: 'Back',
        close: 'Close',
        last: 'Finish',
        next: 'Next',
        skip: 'Skip Tour',
      }}
      floaterProps={{
        disableAnimation: false,
      }}
    />
  );
}
