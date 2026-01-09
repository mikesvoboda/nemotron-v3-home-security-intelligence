/**
 * Centralized validation utilities aligned with backend Pydantic schemas.
 *
 * These validation rules are derived from the backend schemas in:
 * - backend/api/schemas/zone.py
 * - backend/api/schemas/camera.py
 * - backend/api/schemas/alerts.py
 * - backend/api/schemas/notification_preferences.py
 * - backend/api/schemas/prompt_management.py
 *
 * IMPORTANT: When modifying these rules, ensure they match the backend schemas.
 * Backend validation is authoritative; frontend validation provides UX feedback.
 */

// =============================================================================
// Validation Constants (aligned with backend Pydantic Field constraints)
// =============================================================================

/**
 * Backend schema constraints for various entities.
 * These values come directly from backend Pydantic models.
 */
export const VALIDATION_LIMITS = {
  // Zone schema (backend/api/schemas/zone.py)
  zone: {
    name: { minLength: 1, maxLength: 255 },
    priority: { min: 0, max: 100 },
    coordinates: { minPoints: 3 },
    colorPattern: /^#[0-9A-Fa-f]{6}$/,
  },

  // Camera schema (backend/api/schemas/camera.py)
  camera: {
    name: { minLength: 1, maxLength: 255 },
    folderPath: { minLength: 1, maxLength: 500 },
  },

  // Alert rule schema (backend/api/schemas/alerts.py)
  alertRule: {
    name: { minLength: 1, maxLength: 255 },
    riskThreshold: { min: 0, max: 100 },
    minConfidence: { min: 0, max: 1 },
    cooldownSeconds: { min: 0 },
    dedupKeyTemplate: { maxLength: 255 },
  },

  // Notification preferences (backend/api/schemas/notification_preferences.py)
  notificationPreferences: {
    riskThreshold: { min: 0, max: 100 },
    quietHoursLabel: { minLength: 1, maxLength: 255 },
  },

  // Prompt management (backend/api/schemas/prompt_management.py)
  promptConfig: {
    temperature: { min: 0, max: 2 },
    maxTokens: { min: 1, max: 16384 },
  },
} as const;

// =============================================================================
// Validation Result Types
// =============================================================================

export interface ValidationResult {
  isValid: boolean;
  error?: string;
}

// =============================================================================
// Zone Validation Functions
// =============================================================================

/**
 * Validates zone name according to backend schema.
 * Backend constraint: min_length=1, max_length=255
 */
export function validateZoneName(name: string): ValidationResult {
  const trimmed = name.trim();
  const { minLength, maxLength } = VALIDATION_LIMITS.zone.name;

  if (trimmed.length < minLength) {
    return { isValid: false, error: 'Name is required' };
  }

  if (trimmed.length > maxLength) {
    return { isValid: false, error: `Name must be at most ${maxLength} characters` };
  }

  return { isValid: true };
}

/**
 * Validates zone priority according to backend schema.
 * Backend constraint: ge=0, le=100
 */
export function validateZonePriority(priority: number): ValidationResult {
  const { min, max } = VALIDATION_LIMITS.zone.priority;

  if (priority < min || priority > max) {
    return { isValid: false, error: `Priority must be between ${min} and ${max}` };
  }

  return { isValid: true };
}

/**
 * Validates zone color according to backend schema.
 * Backend constraint: pattern=r"^#[0-9A-Fa-f]{6}$"
 */
export function validateZoneColor(color: string): ValidationResult {
  if (!VALIDATION_LIMITS.zone.colorPattern.test(color)) {
    return { isValid: false, error: 'Color must be a valid hex color (e.g., #3B82F6)' };
  }

  return { isValid: true };
}

// =============================================================================
// Camera Validation Functions
// =============================================================================

/**
 * Validates camera name according to backend schema.
 * Backend constraint: min_length=1, max_length=255
 */
export function validateCameraName(name: string): ValidationResult {
  const trimmed = name.trim();
  const { minLength, maxLength } = VALIDATION_LIMITS.camera.name;

  if (trimmed.length < minLength) {
    return { isValid: false, error: 'Name is required' };
  }

  if (trimmed.length > maxLength) {
    return { isValid: false, error: `Name must be at most ${maxLength} characters` };
  }

  return { isValid: true };
}

/**
 * Checks if a path contains forbidden characters (aligned with backend).
 * Backend rejects: < > : " | ? * and control characters (0x00-0x1f)
 */
function containsForbiddenPathChars(path: string): boolean {
  // Check for forbidden printable characters
  if (/[<>:"|?*]/.test(path)) {
    return true;
  }

  // Check for control characters (0x00-0x1f) by examining each character code
  for (let i = 0; i < path.length; i++) {
    const charCode = path.charCodeAt(i);
    if (charCode >= 0x00 && charCode <= 0x1f) {
      return true;
    }
  }

  return false;
}

/**
 * Validates camera folder path according to backend schema.
 * Backend constraints:
 * - min_length=1, max_length=500
 * - No path traversal (..)
 * - No forbidden characters (< > : " | ? * or control characters)
 */
export function validateCameraFolderPath(folderPath: string): ValidationResult {
  const trimmed = folderPath.trim();
  const { minLength, maxLength } = VALIDATION_LIMITS.camera.folderPath;

  if (trimmed.length < minLength) {
    return { isValid: false, error: 'Folder path is required' };
  }

  if (trimmed.length > maxLength) {
    return { isValid: false, error: `Folder path must be at most ${maxLength} characters` };
  }

  // Check for path traversal attempts (security validation from backend)
  if (trimmed.includes('..')) {
    return { isValid: false, error: 'Path traversal (..) is not allowed in folder path' };
  }

  // Check for forbidden characters (security validation from backend)
  if (containsForbiddenPathChars(trimmed)) {
    return {
      isValid: false,
      error: 'Folder path contains forbidden characters (< > : " | ? * or control characters)',
    };
  }

  return { isValid: true };
}

// =============================================================================
// Alert Rule Validation Functions
// =============================================================================

/**
 * Validates alert rule name according to backend schema.
 * Backend constraint: min_length=1, max_length=255
 */
export function validateAlertRuleName(name: string): ValidationResult {
  const trimmed = name.trim();
  const { minLength, maxLength } = VALIDATION_LIMITS.alertRule.name;

  if (trimmed.length < minLength) {
    return { isValid: false, error: 'Name is required' };
  }

  if (trimmed.length > maxLength) {
    return { isValid: false, error: `Name must be at most ${maxLength} characters` };
  }

  return { isValid: true };
}

/**
 * Validates risk threshold according to backend schema.
 * Backend constraint: ge=0, le=100
 */
export function validateRiskThreshold(threshold: number | null): ValidationResult {
  if (threshold === null) {
    return { isValid: true }; // Optional field
  }

  const { min, max } = VALIDATION_LIMITS.alertRule.riskThreshold;

  if (threshold < min || threshold > max) {
    return { isValid: false, error: `Risk threshold must be between ${min} and ${max}` };
  }

  return { isValid: true };
}

/**
 * Validates min confidence according to backend schema.
 * Backend constraint: ge=0.0, le=1.0
 */
export function validateMinConfidence(confidence: number | null): ValidationResult {
  if (confidence === null) {
    return { isValid: true }; // Optional field
  }

  const { min, max } = VALIDATION_LIMITS.alertRule.minConfidence;

  if (confidence < min || confidence > max) {
    return { isValid: false, error: `Confidence must be between ${min} and ${max}` };
  }

  return { isValid: true };
}

/**
 * Validates cooldown seconds according to backend schema.
 * Backend constraint: ge=0
 */
export function validateCooldownSeconds(cooldown: number): ValidationResult {
  const { min } = VALIDATION_LIMITS.alertRule.cooldownSeconds;

  if (cooldown < min) {
    return { isValid: false, error: 'Cooldown cannot be negative' };
  }

  return { isValid: true };
}

/**
 * Validates dedup key template according to backend schema.
 * Backend constraint: max_length=255
 */
export function validateDedupKeyTemplate(template: string): ValidationResult {
  const { maxLength } = VALIDATION_LIMITS.alertRule.dedupKeyTemplate;

  if (template.length > maxLength) {
    return { isValid: false, error: `Dedup key template must be at most ${maxLength} characters` };
  }

  return { isValid: true };
}

// =============================================================================
// Alert Schedule Time Validation Functions
// =============================================================================

/**
 * Validates time format according to backend schema.
 * Backend constraint: pattern=r"^\d{2}:\d{2}$" with hours 00-23, minutes 00-59
 */
export function validateTimeFormat(timeStr: string): ValidationResult {
  if (!timeStr || timeStr.length !== 5 || timeStr[2] !== ':') {
    return { isValid: false, error: 'Invalid time format. Expected HH:MM format.' };
  }

  const hours = parseInt(timeStr.substring(0, 2), 10);
  const minutes = parseInt(timeStr.substring(3, 5), 10);

  if (isNaN(hours) || isNaN(minutes)) {
    return { isValid: false, error: 'Hours and minutes must be numeric.' };
  }

  if (hours < 0 || hours > 23) {
    return { isValid: false, error: `Invalid hours '${hours}'. Hours must be 00-23.` };
  }

  if (minutes < 0 || minutes > 59) {
    return { isValid: false, error: `Invalid minutes '${minutes}'. Minutes must be 00-59.` };
  }

  return { isValid: true };
}

/**
 * Valid days of the week (aligned with backend VALID_DAYS).
 */
export const VALID_DAYS = [
  'monday',
  'tuesday',
  'wednesday',
  'thursday',
  'friday',
  'saturday',
  'sunday',
] as const;

export type DayOfWeek = (typeof VALID_DAYS)[number];

/**
 * Validates day of week according to backend schema.
 */
export function validateDaysOfWeek(days: string[]): ValidationResult {
  const validDaysSet = new Set<string>(VALID_DAYS);
  const invalidDays = days.filter((day) => !validDaysSet.has(day.toLowerCase()));

  if (invalidDays.length > 0) {
    return {
      isValid: false,
      error: `Invalid day(s): ${invalidDays.join(', ')}. Valid days are: ${VALID_DAYS.join(', ')}`,
    };
  }

  return { isValid: true };
}

// =============================================================================
// Notification Preferences Validation Functions
// =============================================================================

/**
 * Validates quiet hours label according to backend schema.
 * Backend constraint: min_length=1, max_length=255
 */
export function validateQuietHoursLabel(label: string): ValidationResult {
  const trimmed = label.trim();
  const { minLength, maxLength } = VALIDATION_LIMITS.notificationPreferences.quietHoursLabel;

  if (trimmed.length < minLength) {
    return { isValid: false, error: 'Label is required' };
  }

  if (trimmed.length > maxLength) {
    return { isValid: false, error: `Label must be at most ${maxLength} characters` };
  }

  return { isValid: true };
}

// =============================================================================
// Prompt Configuration Validation Functions
// =============================================================================

/**
 * Validates LLM temperature according to backend schema.
 * Backend constraint: ge=0.0, le=2.0
 */
export function validateTemperature(temperature: number): ValidationResult {
  const { min, max } = VALIDATION_LIMITS.promptConfig.temperature;

  if (temperature < min || temperature > max) {
    return { isValid: false, error: `Temperature must be between ${min} and ${max}` };
  }

  return { isValid: true };
}

/**
 * Validates max tokens according to backend schema.
 * Backend constraint: ge=1, le=16384
 */
export function validateMaxTokens(maxTokens: number): ValidationResult {
  const { min, max } = VALIDATION_LIMITS.promptConfig.maxTokens;

  if (maxTokens < min || maxTokens > max) {
    return { isValid: false, error: `Max tokens must be between ${min} and ${max}` };
  }

  return { isValid: true };
}
