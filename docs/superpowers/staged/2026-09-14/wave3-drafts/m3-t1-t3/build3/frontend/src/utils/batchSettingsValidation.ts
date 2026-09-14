/**
 * Batch settings validation utility
 *
 * Provides validation rules, presets, and latency impact calculations
 * for batch processing configuration.
 *
 * @see NEM-3873 - Batch Config Validation
 */

// ============================================================================
// Types
// ============================================================================

/**
 * Result of validating batch settings
 */
export interface BatchSettingsValidation {
  /** Whether the settings are valid (no errors) */
  isValid: boolean;
  /** Non-blocking warnings about suboptimal settings */
  warnings: string[];
  /** Blocking errors that prevent saving */
  errors: string[];
}

/**
 * Latency impact preview for batch settings
 */
export interface LatencyImpact {
  /** Minimum expected latency (idle timeout) */
  minLatencySeconds: number;
  /** Maximum expected latency (full window) */
  maxLatencySeconds: number;
  /** Typical expected latency (average) */
  typicalLatencySeconds: number;
  /** Human-readable description */
  description: string;
}

/**
 * Batch processing preset configuration
 */
export interface BatchPreset {
  /** Unique identifier for the preset */
  id: string;
  /** Display name */
  name: string;
  /** Batch window duration in seconds */
  windowSeconds: number;
  /** Idle timeout in seconds */
  idleTimeoutSeconds: number;
  /** Description of the preset behavior */
  description: string;
}

// ============================================================================
// Constants
// ============================================================================

/** Maximum allowed batch window (matches backend) */
const MAX_WINDOW_SECONDS = 600;

/** Maximum allowed idle timeout (matches backend) */
const MAX_IDLE_TIMEOUT_SECONDS = 300;

/** Threshold below which window is considered too aggressive */
const MIN_RECOMMENDED_WINDOW = 30;

/** Threshold above which window is considered too slow */
const MAX_RECOMMENDED_WINDOW = 180;

/**
 * Predefined batch processing presets
 */
export const BATCH_PRESETS: BatchPreset[] = [
  {
    id: 'realtime',
    name: 'Real-time',
    windowSeconds: 30,
    idleTimeoutSeconds: 10,
    description:
      'Fastest response time with higher processing overhead. Best for high-security areas requiring immediate alerts.',
  },
  {
    id: 'balanced',
    name: 'Balanced',
    windowSeconds: 90,
    idleTimeoutSeconds: 30,
    description:
      'Default setting balancing response time and efficiency. Recommended for most use cases.',
  },
  {
    id: 'efficient',
    name: 'Efficient',
    windowSeconds: 180,
    idleTimeoutSeconds: 60,
    description:
      'Lower processing overhead with delayed notifications. Best for low-priority areas or resource-constrained systems.',
  },
];

// ============================================================================
// Validation Functions
// ============================================================================

/**
 * Validate batch settings and return warnings/errors
 *
 * @param windowSeconds - Batch window duration
 * @param idleTimeoutSeconds - Idle timeout duration
 * @returns Validation result with isValid, warnings, and errors
 */
export function validateBatchSettings(
  windowSeconds: number,
  idleTimeoutSeconds: number
): BatchSettingsValidation {
  const warnings: string[] = [];
  const errors: string[] = [];

  // Check for invalid values (blocking errors)
  if (windowSeconds <= 0) {
    errors.push('Batch window must be greater than 0');
  }

  if (idleTimeoutSeconds <= 0) {
    errors.push('Idle timeout must be greater than 0');
  }

  if (windowSeconds > MAX_WINDOW_SECONDS) {
    errors.push(`Batch window cannot exceed ${MAX_WINDOW_SECONDS} seconds`);
  }

  if (idleTimeoutSeconds > MAX_IDLE_TIMEOUT_SECONDS) {
    errors.push(`Idle timeout cannot exceed ${MAX_IDLE_TIMEOUT_SECONDS} seconds`);
  }

  // If there are errors, return early
  if (errors.length > 0) {
    return { isValid: false, warnings, errors };
  }

  // Check for suboptimal settings (warnings)
  if (idleTimeoutSeconds >= windowSeconds) {
    warnings.push('Idle timeout should be less than batch window for optimal performance');
  }

  if (windowSeconds < MIN_RECOMMENDED_WINDOW) {
    warnings.push(
      `Batch window under ${MIN_RECOMMENDED_WINDOW} seconds may cause excessive processing overhead`
    );
  }

  if (windowSeconds > MAX_RECOMMENDED_WINDOW) {
    warnings.push(
      `Batch window over ${MAX_RECOMMENDED_WINDOW} seconds may delay event notifications significantly`
    );
  }

  return { isValid: true, warnings, errors };
}

// ============================================================================
// Latency Impact Functions
// ============================================================================

/**
 * Calculate the estimated latency impact of batch settings
 *
 * @param windowSeconds - Batch window duration
 * @param idleTimeoutSeconds - Idle timeout duration
 * @returns Latency impact preview
 */
export function calculateLatencyImpact(
  windowSeconds: number,
  idleTimeoutSeconds: number
): LatencyImpact {
  const minLatencySeconds = idleTimeoutSeconds;
  const maxLatencySeconds = windowSeconds;
  const typicalLatencySeconds = (minLatencySeconds + maxLatencySeconds) / 2;

  // Determine description based on settings
  const presetId = detectCurrentPreset(windowSeconds, idleTimeoutSeconds);
  let description: string;

  switch (presetId) {
    case 'realtime':
      description = `Real-time: Events processed within ${minLatencySeconds}-${maxLatencySeconds} seconds`;
      break;
    case 'balanced':
      description = `Balanced: Events processed within ${minLatencySeconds}-${maxLatencySeconds} seconds`;
      break;
    case 'efficient':
      description = `Efficient: Events processed within ${minLatencySeconds}-${maxLatencySeconds} seconds`;
      break;
    default:
      description = `Custom: Events processed within ${minLatencySeconds}-${maxLatencySeconds} seconds`;
  }

  return {
    minLatencySeconds,
    maxLatencySeconds,
    typicalLatencySeconds,
    description,
  };
}

// ============================================================================
// Preset Detection Functions
// ============================================================================

/**
 * Detect which preset (if any) matches the current settings
 *
 * @param windowSeconds - Current batch window
 * @param idleTimeoutSeconds - Current idle timeout
 * @returns Preset ID or null if no preset matches
 */
export function detectCurrentPreset(
  windowSeconds: number,
  idleTimeoutSeconds: number
): string | null {
  const matchingPreset = BATCH_PRESETS.find(
    (preset) =>
      preset.windowSeconds === windowSeconds && preset.idleTimeoutSeconds === idleTimeoutSeconds
  );

  return matchingPreset?.id ?? null;
}
