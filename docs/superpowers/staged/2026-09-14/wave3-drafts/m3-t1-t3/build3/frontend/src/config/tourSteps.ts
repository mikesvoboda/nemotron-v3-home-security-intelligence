/**
 * Tour step definitions for the interactive product tour.
 *
 * These steps guide first-time users through the main features
 * of the Nemotron Security Dashboard.
 *
 * @module config/tourSteps
 */

import type { Step } from 'react-joyride';

/**
 * LocalStorage key for tracking tour completion status.
 */
export const TOUR_COMPLETED_KEY = 'nemotron-tour-completed';

/**
 * LocalStorage key for tracking if tour has been skipped.
 */
export const TOUR_SKIPPED_KEY = 'nemotron-tour-skipped';

/**
 * Check if the product tour has been completed by the user.
 */
export function isTourCompleted(): boolean {
  try {
    return localStorage.getItem(TOUR_COMPLETED_KEY) === 'true';
  } catch {
    // localStorage may be unavailable in some environments
    return false;
  }
}

/**
 * Check if the product tour has been skipped by the user.
 */
export function isTourSkipped(): boolean {
  try {
    return localStorage.getItem(TOUR_SKIPPED_KEY) === 'true';
  } catch {
    return false;
  }
}

/**
 * Mark the product tour as completed.
 */
export function markTourCompleted(): void {
  try {
    localStorage.setItem(TOUR_COMPLETED_KEY, 'true');
  } catch {
    // Silently fail if localStorage is unavailable
  }
}

/**
 * Mark the product tour as skipped.
 */
export function markTourSkipped(): void {
  try {
    localStorage.setItem(TOUR_SKIPPED_KEY, 'true');
  } catch {
    // Silently fail if localStorage is unavailable
  }
}

/**
 * Reset tour completion status (used for restarting the tour).
 */
export function resetTourStatus(): void {
  try {
    localStorage.removeItem(TOUR_COMPLETED_KEY);
    localStorage.removeItem(TOUR_SKIPPED_KEY);
  } catch {
    // Silently fail if localStorage is unavailable
  }
}

/**
 * Restart the product tour by clearing completion status from localStorage.
 * Alias for resetTourStatus for better API ergonomics.
 */
export function restartProductTour(): void {
  resetTourStatus();
}

/**
 * Check if the tour should be shown to the user.
 * Returns true if tour has not been completed or skipped.
 */
export function shouldShowTour(): boolean {
  return !isTourCompleted() && !isTourSkipped();
}

/**
 * Tour step definitions for the product tour.
 *
 * Each step includes:
 * - target: CSS selector for the element to highlight
 * - content: Description text shown to the user
 * - placement: Tooltip positioning
 * - disableBeacon: Whether to skip the beacon animation
 * - spotlightClicks: Whether to allow clicking the highlighted element
 */
export const tourSteps: Step[] = [
  {
    target: 'body',
    content:
      "Welcome to the Nemotron Security Dashboard! This interactive tour will guide you through the main features. Let's get started.",
    placement: 'center',
    disableBeacon: true,
    title: 'Welcome to Nemotron Security',
  },
  {
    target: '[data-tour="risk-gauge"]',
    content:
      'The Risk Gauge shows your current security risk level based on AI-analyzed camera detections. The score ranges from 0 (safe) to 100 (high risk).',
    placement: 'bottom',
    disableBeacon: true,
    title: 'Risk Gauge',
    spotlightClicks: true,
  },
  {
    target: '[data-tour="camera-grid"]',
    content:
      'The Camera Grid displays real-time status of all your connected cameras. Click on any camera for detailed view and recent activity.',
    placement: 'bottom',
    disableBeacon: true,
    title: 'Camera Grid',
    spotlightClicks: true,
  },
  {
    target: '[data-tour="activity-feed"]',
    content:
      'The Activity Feed shows recent detection events in real-time. Each event includes the camera source, detected objects, and risk assessment.',
    placement: 'left',
    disableBeacon: true,
    title: 'Activity Feed',
    spotlightClicks: true,
  },
  {
    target: '[data-tour="timeline-link"]',
    content:
      'Access the Timeline to review historical events, filter by date range, and analyze patterns in your security footage.',
    placement: 'right',
    disableBeacon: true,
    title: 'Event Timeline',
    spotlightClicks: true,
  },
  {
    target: '[data-tour="settings-link"]',
    content:
      'Configure your cameras, notification preferences, and AI detection settings in the Settings page. You can also restart this tour from there.',
    placement: 'right',
    disableBeacon: true,
    title: 'Settings',
    spotlightClicks: true,
  },
  {
    target: 'body',
    content:
      'You\'re all set! Enable browser notifications to receive real-time alerts when the AI detects suspicious activity. Click "Enable Notifications" to get started.',
    placement: 'center',
    disableBeacon: true,
    title: 'Tour Complete',
  },
];

/**
 * Default tour options for consistent styling.
 */
export const defaultTourStyles = {
  options: {
    // NVIDIA brand colors
    primaryColor: '#76B900',
    backgroundColor: '#1A1A1A',
    textColor: '#FFFFFF',
    arrowColor: '#1A1A1A',
    overlayColor: 'rgba(0, 0, 0, 0.75)',
    spotlightShadow: '0 0 15px rgba(118, 185, 0, 0.5)',
    width: 380,
    zIndex: 10000,
  },
  buttonNext: {
    backgroundColor: '#76B900',
    color: '#000000',
    fontSize: '14px',
    fontWeight: 600,
    padding: '10px 20px',
    borderRadius: '8px',
  },
  buttonBack: {
    color: '#9CA3AF',
    fontSize: '14px',
    marginRight: '10px',
  },
  buttonSkip: {
    color: '#9CA3AF',
    fontSize: '14px',
  },
  buttonClose: {
    color: '#9CA3AF',
  },
  tooltip: {
    backgroundColor: '#1A1A1A',
    borderRadius: '12px',
    color: '#FFFFFF',
    padding: '20px',
    boxShadow: '0 10px 40px rgba(0, 0, 0, 0.5)',
    border: '1px solid #333',
  },
  tooltipTitle: {
    color: '#76B900',
    fontSize: '18px',
    fontWeight: 700,
    marginBottom: '8px',
  },
  tooltipContent: {
    fontSize: '14px',
    lineHeight: '1.6',
    color: '#E5E7EB',
  },
  spotlight: {
    borderRadius: '8px',
  },
  overlay: {
    backgroundColor: 'rgba(0, 0, 0, 0.75)',
  },
  beaconInner: {
    backgroundColor: '#76B900',
  },
  beaconOuter: {
    backgroundColor: 'rgba(118, 185, 0, 0.3)',
    border: '2px solid #76B900',
  },
};

/**
 * Mobile-responsive tour styles.
 * Applied when viewport width is below 768px.
 */
export const mobileTourStyles = {
  ...defaultTourStyles,
  options: {
    ...defaultTourStyles.options,
    width: 300,
  },
  tooltip: {
    ...defaultTourStyles.tooltip,
    padding: '16px',
    maxWidth: '90vw',
  },
  tooltipTitle: {
    ...defaultTourStyles.tooltipTitle,
    fontSize: '16px',
  },
  tooltipContent: {
    ...defaultTourStyles.tooltipContent,
    fontSize: '13px',
  },
};
