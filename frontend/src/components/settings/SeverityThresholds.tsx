import { Card, Title, Text, Button } from '@tremor/react';
import { AlertCircle, ShieldAlert, Save, RotateCcw } from 'lucide-react';
import { useEffect, useState, useCallback } from 'react';

import {
  fetchSeverityConfig,
  updateSeverityThresholds,
  type SeverityMetadataResponse,
} from '../../services/api';

export interface SeverityThresholdsProps {
  className?: string;
}

interface EditableThresholds {
  low_max: number;
  medium_max: number;
  high_max: number;
}

interface ValidationError {
  field: string;
  message: string;
}

/**
 * SeverityThresholds component displays and allows editing of risk score thresholds.
 * - Fetches severity definitions from /api/system/severity endpoint
 * - Shows a table with severity levels, score ranges, and descriptions
 * - Allows editing threshold boundaries via input fields
 * - Validates that ranges are contiguous (0-100, no gaps/overlaps)
 * - Saves changes via PUT /api/system/severity endpoint
 */
export default function SeverityThresholds({ className }: SeverityThresholdsProps) {
  const [severityData, setSeverityData] = useState<SeverityMetadataResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [isEditing, setIsEditing] = useState(false);

  // Editable thresholds state
  const [editableThresholds, setEditableThresholds] = useState<EditableThresholds>({
    low_max: 29,
    medium_max: 59,
    high_max: 84,
  });

  // Original thresholds for reset functionality
  const [originalThresholds, setOriginalThresholds] = useState<EditableThresholds>({
    low_max: 29,
    medium_max: 59,
    high_max: 84,
  });

  // Validation errors
  const [validationErrors, setValidationErrors] = useState<ValidationError[]>([]);

  useEffect(() => {
    const loadSeverityConfig = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchSeverityConfig();
        setSeverityData(data);

        // Initialize editable thresholds from fetched data
        if (data.thresholds) {
          const thresholds = {
            low_max: data.thresholds.low_max,
            medium_max: data.thresholds.medium_max,
            high_max: data.thresholds.high_max,
          };
          setEditableThresholds(thresholds);
          setOriginalThresholds(thresholds);
        }
      } catch {
        setError('Failed to load severity thresholds');
      } finally {
        setLoading(false);
      }
    };

    void loadSeverityConfig();
  }, []);

  // Validate thresholds ensuring contiguous ranges from 0-100
  const validateThresholds = useCallback((thresholds: EditableThresholds): ValidationError[] => {
    const errors: ValidationError[] = [];

    // Check low_max bounds (1-98)
    if (thresholds.low_max < 1 || thresholds.low_max > 98) {
      errors.push({
        field: 'low_max',
        message: 'Low max must be between 1 and 98',
      });
    }

    // Check medium_max bounds (2-99)
    if (thresholds.medium_max < 2 || thresholds.medium_max > 99) {
      errors.push({
        field: 'medium_max',
        message: 'Medium max must be between 2 and 99',
      });
    }

    // Check high_max bounds (3-99)
    if (thresholds.high_max < 3 || thresholds.high_max > 99) {
      errors.push({
        field: 'high_max',
        message: 'High max must be between 3 and 99',
      });
    }

    // Check ordering: low_max < medium_max < high_max
    if (thresholds.low_max >= thresholds.medium_max) {
      errors.push({
        field: 'ordering',
        message: 'Low max must be less than Medium max',
      });
    }

    if (thresholds.medium_max >= thresholds.high_max) {
      errors.push({
        field: 'ordering',
        message: 'Medium max must be less than High max',
      });
    }

    return errors;
  }, []);

  // Handle threshold input changes
  const handleThresholdChange = (field: keyof EditableThresholds, value: string) => {
    const numValue = parseInt(value, 10);
    if (isNaN(numValue)) return;

    const newThresholds = {
      ...editableThresholds,
      [field]: numValue,
    };

    setEditableThresholds(newThresholds);
    setValidationErrors(validateThresholds(newThresholds));
    setSaveSuccess(false);
  };

  // Reset to original thresholds
  const handleReset = () => {
    setEditableThresholds(originalThresholds);
    setValidationErrors([]);
    setIsEditing(false);
    setSaveSuccess(false);
  };

  // Save thresholds
  const handleSave = async () => {
    const errors = validateThresholds(editableThresholds);
    if (errors.length > 0) {
      setValidationErrors(errors);
      return;
    }

    try {
      setSaving(true);
      setError(null);
      setSaveSuccess(false);

      const updatedData = await updateSeverityThresholds(editableThresholds);
      setSeverityData(updatedData);

      // Update original thresholds to new values
      if (updatedData.thresholds) {
        const thresholds = {
          low_max: updatedData.thresholds.low_max,
          medium_max: updatedData.thresholds.medium_max,
          high_max: updatedData.thresholds.high_max,
        };
        setEditableThresholds(thresholds);
        setOriginalThresholds(thresholds);
      }

      setIsEditing(false);
      setSaveSuccess(true);

      // Clear success message after 3 seconds
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch {
      setError('Failed to save severity thresholds');
    } finally {
      setSaving(false);
    }
  };

  // Check if thresholds have been modified
  const hasChanges =
    editableThresholds.low_max !== originalThresholds.low_max ||
    editableThresholds.medium_max !== originalThresholds.medium_max ||
    editableThresholds.high_max !== originalThresholds.high_max;

  // Compute ranges based on editable thresholds
  const computedRanges = {
    low: { min: 0, max: editableThresholds.low_max },
    medium: { min: editableThresholds.low_max + 1, max: editableThresholds.medium_max },
    high: { min: editableThresholds.medium_max + 1, max: editableThresholds.high_max },
    critical: { min: editableThresholds.high_max + 1, max: 100 },
  };

  // Sort definitions by min_score to display in ascending order (low to critical)
  const sortedDefinitions = severityData?.definitions
    ? [...severityData.definitions].sort((a, b) => a.min_score - b.min_score)
    : [];

  // Get field-specific validation error
  const getFieldError = (field: string): string | undefined => {
    return validationErrors.find((e) => e.field === field)?.message;
  };

  return (
    <Card className={`border-gray-800 bg-[#1A1A1A] shadow-lg ${className || ''}`}>
      <div className="mb-4 flex items-center justify-between">
        <Title className="flex items-center gap-2 text-white">
          <ShieldAlert className="h-5 w-5 text-[#76B900]" />
          Risk Score Thresholds
        </Title>

        {!loading && !error && severityData && (
          <div className="flex items-center gap-2">
            {isEditing ? (
              <>
                <Button
                  size="xs"
                  variant="secondary"
                  onClick={handleReset}
                  disabled={saving}
                  className="flex items-center gap-1"
                >
                  <RotateCcw className="h-3 w-3" />
                  Reset
                </Button>
                <Button
                  size="xs"
                  onClick={() => void handleSave()}
                  disabled={saving || validationErrors.length > 0 || !hasChanges}
                  className="flex items-center gap-1 bg-[#76B900] hover:bg-[#5a8c00]"
                >
                  <Save className="h-3 w-3" />
                  {saving ? 'Saving...' : 'Save'}
                </Button>
              </>
            ) : (
              <Button
                size="xs"
                variant="secondary"
                onClick={() => setIsEditing(true)}
                className="text-gray-300 hover:text-white"
              >
                Edit Thresholds
              </Button>
            )}
          </div>
        )}
      </div>

      {loading && (
        <div className="space-y-3">
          <div className="skeleton h-8 w-full"></div>
          <div className="skeleton h-8 w-full"></div>
          <div className="skeleton h-8 w-full"></div>
          <div className="skeleton h-8 w-full"></div>
        </div>
      )}

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-4">
          <AlertCircle className="h-5 w-5 flex-shrink-0 text-red-500" />
          <Text className="text-red-500">{error}</Text>
        </div>
      )}

      {saveSuccess && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-green-500/30 bg-green-500/10 p-4">
          <Text className="text-green-500">Severity thresholds saved successfully!</Text>
        </div>
      )}

      {validationErrors.length > 0 && isEditing && (
        <div className="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 p-4">
          <Text className="mb-2 font-medium text-red-500">Validation Errors:</Text>
          <ul className="list-inside list-disc space-y-1">
            {validationErrors.map((err, idx) => (
              <li key={idx} className="text-sm text-red-400">
                {err.message}
              </li>
            ))}
          </ul>
        </div>
      )}

      {!loading && !error && severityData && (
        <>
          {isEditing && (
            <div className="mb-4 rounded-lg border border-gray-700 bg-gray-800/50 p-4">
              <Text className="mb-3 text-sm text-gray-400">
                Adjust the maximum score for each severity level. Ranges will be automatically
                calculated to ensure no gaps or overlaps.
              </Text>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label
                    htmlFor="threshold-input-low"
                    className="mb-1 block text-xs font-medium text-gray-400"
                  >
                    Low Max (1-98)
                  </label>
                  <input
                    id="threshold-input-low"
                    type="number"
                    min={1}
                    max={98}
                    value={editableThresholds.low_max}
                    onChange={(e) => handleThresholdChange('low_max', e.target.value)}
                    className={`w-full rounded border bg-gray-900 px-3 py-2 text-white focus:outline-none focus:ring-2 ${
                      getFieldError('low_max')
                        ? 'border-red-500 focus:ring-red-500'
                        : 'border-gray-600 focus:ring-[#76B900]'
                    }`}
                    data-testid="threshold-input-low"
                  />
                  {getFieldError('low_max') && (
                    <Text className="mt-1 text-xs text-red-500">{getFieldError('low_max')}</Text>
                  )}
                </div>
                <div>
                  <label
                    htmlFor="threshold-input-medium"
                    className="mb-1 block text-xs font-medium text-gray-400"
                  >
                    Medium Max (2-99)
                  </label>
                  <input
                    id="threshold-input-medium"
                    type="number"
                    min={2}
                    max={99}
                    value={editableThresholds.medium_max}
                    onChange={(e) => handleThresholdChange('medium_max', e.target.value)}
                    className={`w-full rounded border bg-gray-900 px-3 py-2 text-white focus:outline-none focus:ring-2 ${
                      getFieldError('medium_max')
                        ? 'border-red-500 focus:ring-red-500'
                        : 'border-gray-600 focus:ring-[#76B900]'
                    }`}
                    data-testid="threshold-input-medium"
                  />
                  {getFieldError('medium_max') && (
                    <Text className="mt-1 text-xs text-red-500">{getFieldError('medium_max')}</Text>
                  )}
                </div>
                <div>
                  <label
                    htmlFor="threshold-input-high"
                    className="mb-1 block text-xs font-medium text-gray-400"
                  >
                    High Max (3-99)
                  </label>
                  <input
                    id="threshold-input-high"
                    type="number"
                    min={3}
                    max={99}
                    value={editableThresholds.high_max}
                    onChange={(e) => handleThresholdChange('high_max', e.target.value)}
                    className={`w-full rounded border bg-gray-900 px-3 py-2 text-white focus:outline-none focus:ring-2 ${
                      getFieldError('high_max')
                        ? 'border-red-500 focus:ring-red-500'
                        : 'border-gray-600 focus:ring-[#76B900]'
                    }`}
                    data-testid="threshold-input-high"
                  />
                  {getFieldError('high_max') && (
                    <Text className="mt-1 text-xs text-red-500">{getFieldError('high_max')}</Text>
                  )}
                </div>
              </div>
            </div>
          )}

          <div className="overflow-hidden rounded-lg border border-gray-700">
            <table className="w-full" role="table">
              <thead>
                <tr className="border-b border-gray-700 bg-gray-800/50">
                  <th
                    className="px-4 py-3 text-left text-sm font-medium text-gray-300"
                    role="columnheader"
                  >
                    Level
                  </th>
                  <th
                    className="px-4 py-3 text-left text-sm font-medium text-gray-300"
                    role="columnheader"
                  >
                    Range
                  </th>
                  <th
                    className="px-4 py-3 text-left text-sm font-medium text-gray-300"
                    role="columnheader"
                  >
                    Description
                  </th>
                </tr>
              </thead>
              <tbody>
                {sortedDefinitions.map((definition) => {
                  // Get computed range based on editable thresholds when editing
                  const range = isEditing
                    ? computedRanges[definition.severity]
                    : { min: definition.min_score, max: definition.max_score };

                  return (
                    <tr
                      key={definition.severity}
                      className="border-b border-gray-700/50 last:border-b-0"
                      role="row"
                    >
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <div
                            data-testid={`severity-indicator-${definition.severity}`}
                            className="h-3 w-3 rounded-full"
                            style={{ backgroundColor: definition.color }}
                          />
                          <Text className="font-medium text-white">{definition.label}</Text>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <Text
                          className={`font-mono ${isEditing && hasChanges ? 'text-[#76B900]' : 'text-gray-300'}`}
                          data-testid={`range-${definition.severity}`}
                        >
                          {range.min}-{range.max}
                        </Text>
                      </td>
                      <td className="px-4 py-3">
                        <Text className="text-gray-400">{definition.description}</Text>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Card>
  );
}
