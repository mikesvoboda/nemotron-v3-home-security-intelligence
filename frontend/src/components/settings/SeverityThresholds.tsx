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

interface ThresholdValues {
  low_max: number;
  medium_max: number;
  high_max: number;
}

/**
 * SeverityThresholds component displays and allows editing of risk score thresholds.
 * - Fetches severity definitions from /api/system/severity endpoint
 * - Shows editable threshold inputs with visual slider representation
 * - Validates that thresholds are contiguous and non-overlapping
 * - Saves changes via PUT /api/system/severity endpoint
 * - Displays color-coded indicators for each severity level
 * - Handles loading, error, and success states
 */
export default function SeverityThresholds({ className }: SeverityThresholdsProps) {
  const [severityData, setSeverityData] = useState<SeverityMetadataResponse | null>(null);
  const [editedThresholds, setEditedThresholds] = useState<ThresholdValues | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  useEffect(() => {
    const loadSeverityConfig = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchSeverityConfig();
        setSeverityData(data);
        setEditedThresholds({
          low_max: data.thresholds.low_max,
          medium_max: data.thresholds.medium_max,
          high_max: data.thresholds.high_max,
        });
      } catch {
        setError('Failed to load severity thresholds');
      } finally {
        setLoading(false);
      }
    };

    void loadSeverityConfig();
  }, []);

  // Validate thresholds are contiguous and non-overlapping
  const validateThresholds = useCallback((thresholds: ThresholdValues): string | null => {
    const { low_max, medium_max, high_max } = thresholds;

    if (low_max < 1 || low_max > 98) {
      return 'Low max must be between 1 and 98';
    }
    if (medium_max < 2 || medium_max > 99) {
      return 'Medium max must be between 2 and 99';
    }
    if (high_max < 3 || high_max > 99) {
      return 'High max must be between 3 and 99';
    }
    if (low_max >= medium_max) {
      return 'Low max must be less than Medium max';
    }
    if (medium_max >= high_max) {
      return 'Medium max must be less than High max';
    }
    return null;
  }, []);

  // Check if there are unsaved changes
  const hasChanges = !!(
    editedThresholds &&
    severityData &&
    (editedThresholds.low_max !== severityData.thresholds.low_max ||
      editedThresholds.medium_max !== severityData.thresholds.medium_max ||
      editedThresholds.high_max !== severityData.thresholds.high_max)
  );

  const handleThresholdChange = (field: keyof ThresholdValues, value: number) => {
    if (!editedThresholds) return;

    const newThresholds = { ...editedThresholds, [field]: value };
    setEditedThresholds(newThresholds);

    // Validate the new thresholds
    const validationResult = validateThresholds(newThresholds);
    setValidationError(validationResult);
    setSuccess(false);
  };

  const handleSave = async () => {
    if (!editedThresholds || !hasChanges) return;

    const validationResult = validateThresholds(editedThresholds);
    if (validationResult) {
      setValidationError(validationResult);
      return;
    }

    try {
      setSaving(true);
      setError(null);
      setSuccess(false);

      const updatedData = await updateSeverityThresholds(editedThresholds);
      setSeverityData(updatedData);
      setEditedThresholds({
        low_max: updatedData.thresholds.low_max,
        medium_max: updatedData.thresholds.medium_max,
        high_max: updatedData.thresholds.high_max,
      });
      setValidationError(null);
      setSuccess(true);

      // Clear success message after 3 seconds
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save severity thresholds');
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    if (severityData) {
      setEditedThresholds({
        low_max: severityData.thresholds.low_max,
        medium_max: severityData.thresholds.medium_max,
        high_max: severityData.thresholds.high_max,
      });
      setValidationError(null);
      setError(null);
      setSuccess(false);
    }
  };

  // Calculate ranges for display
  const getRanges = (thresholds: ThresholdValues) => ({
    low: { min: 0, max: thresholds.low_max },
    medium: { min: thresholds.low_max + 1, max: thresholds.medium_max },
    high: { min: thresholds.medium_max + 1, max: thresholds.high_max },
    critical: { min: thresholds.high_max + 1, max: 100 },
  });

  // Sort definitions by min_score to display in ascending order (low to critical)
  const sortedDefinitions = severityData?.definitions
    ? [...severityData.definitions].sort((a, b) => a.min_score - b.min_score)
    : [];

  const ranges = editedThresholds ? getRanges(editedThresholds) : null;

  return (
    <Card
      className={`border-gray-800 bg-[#1A1A1A] shadow-lg ${className || ''}`}
      data-testid="severity-thresholds-card"
    >
      <Title className="mb-4 flex items-center gap-2 text-white">
        <ShieldAlert className="h-5 w-5 text-[#76B900]" />
        Risk Score Thresholds
      </Title>

      {loading && (
        <div className="space-y-3">
          <div className="skeleton h-8 w-full"></div>
          <div className="skeleton h-8 w-full"></div>
          <div className="skeleton h-8 w-full"></div>
          <div className="skeleton h-8 w-full"></div>
        </div>
      )}

      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-4">
          <AlertCircle className="h-5 w-5 flex-shrink-0 text-red-500" />
          <Text className="text-red-500">{error}</Text>
        </div>
      )}

      {success && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-green-500/30 bg-green-500/10 p-4">
          <Save className="h-5 w-5 flex-shrink-0 text-green-500" />
          <Text className="text-green-500">Thresholds saved successfully!</Text>
        </div>
      )}

      {validationError && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-yellow-500/30 bg-yellow-500/10 p-4">
          <AlertCircle className="h-5 w-5 flex-shrink-0 text-yellow-500" />
          <Text className="text-yellow-500">{validationError}</Text>
        </div>
      )}

      {!loading && !error && severityData && editedThresholds && ranges && (
        <div className="space-y-6">
          {/* Visual Range Bar */}
          <div className="space-y-2">
            <Text className="text-sm font-medium text-gray-300">Score Distribution</Text>
            <div className="flex h-8 overflow-hidden rounded-lg">
              <div
                className="flex items-center justify-center text-xs font-medium text-white"
                style={{
                  backgroundColor: sortedDefinitions[0]?.color || '#22c55e',
                  width: `${ranges.low.max + 1}%`,
                }}
                title={`Low: ${ranges.low.min}-${ranges.low.max}`}
              >
                {ranges.low.max - ranges.low.min + 1 > 10 && 'Low'}
              </div>
              <div
                className="flex items-center justify-center text-xs font-medium text-black"
                style={{
                  backgroundColor: sortedDefinitions[1]?.color || '#eab308',
                  width: `${ranges.medium.max - ranges.medium.min + 1}%`,
                }}
                title={`Medium: ${ranges.medium.min}-${ranges.medium.max}`}
              >
                {ranges.medium.max - ranges.medium.min + 1 > 10 && 'Med'}
              </div>
              <div
                className="flex items-center justify-center text-xs font-medium text-white"
                style={{
                  backgroundColor: sortedDefinitions[2]?.color || '#f97316',
                  width: `${ranges.high.max - ranges.high.min + 1}%`,
                }}
                title={`High: ${ranges.high.min}-${ranges.high.max}`}
              >
                {ranges.high.max - ranges.high.min + 1 > 10 && 'High'}
              </div>
              <div
                className="flex items-center justify-center text-xs font-medium text-white"
                style={{
                  backgroundColor: sortedDefinitions[3]?.color || '#ef4444',
                  width: `${100 - ranges.critical.min + 1}%`,
                }}
                title={`Critical: ${ranges.critical.min}-${ranges.critical.max}`}
              >
                {ranges.critical.max - ranges.critical.min + 1 > 10 && 'Crit'}
              </div>
            </div>
            <div className="flex justify-between text-xs text-gray-500">
              <span>0</span>
              <span>25</span>
              <span>50</span>
              <span>75</span>
              <span>100</span>
            </div>
          </div>

          {/* Editable Threshold Inputs */}
          <div className="space-y-4">
            {/* Low Max Threshold */}
            <div>
              <div className="mb-2 flex items-end justify-between">
                <div className="flex items-center gap-2">
                  <div
                    className="h-3 w-3 rounded-full"
                    style={{ backgroundColor: sortedDefinitions[0]?.color || '#22c55e' }}
                  />
                  <Text className="font-medium text-gray-300">Low Max (0 to this value)</Text>
                </div>
                <Text className="text-lg font-semibold text-white">{editedThresholds.low_max}</Text>
              </div>
              <input
                type="range"
                min="1"
                max="98"
                step="1"
                value={editedThresholds.low_max}
                onChange={(e) => handleThresholdChange('low_max', parseInt(e.target.value))}
                className="h-2 w-full cursor-pointer appearance-none rounded-lg bg-gray-700 accent-[#22c55e]"
                aria-label="Low severity maximum score"
                data-testid="low-max-slider"
              />
              <div className="mt-1 flex justify-between text-xs text-gray-500">
                <span>1</span>
                <span>98</span>
              </div>
            </div>

            {/* Medium Max Threshold */}
            <div>
              <div className="mb-2 flex items-end justify-between">
                <div className="flex items-center gap-2">
                  <div
                    className="h-3 w-3 rounded-full"
                    style={{ backgroundColor: sortedDefinitions[1]?.color || '#eab308' }}
                  />
                  <Text className="font-medium text-gray-300">
                    Medium Max ({editedThresholds.low_max + 1} to this value)
                  </Text>
                </div>
                <Text className="text-lg font-semibold text-white">
                  {editedThresholds.medium_max}
                </Text>
              </div>
              <input
                type="range"
                min={editedThresholds.low_max + 1}
                max="99"
                step="1"
                value={editedThresholds.medium_max}
                onChange={(e) => handleThresholdChange('medium_max', parseInt(e.target.value))}
                className="h-2 w-full cursor-pointer appearance-none rounded-lg bg-gray-700 accent-[#eab308]"
                aria-label="Medium severity maximum score"
                data-testid="medium-max-slider"
              />
              <div className="mt-1 flex justify-between text-xs text-gray-500">
                <span>{editedThresholds.low_max + 1}</span>
                <span>99</span>
              </div>
            </div>

            {/* High Max Threshold */}
            <div>
              <div className="mb-2 flex items-end justify-between">
                <div className="flex items-center gap-2">
                  <div
                    className="h-3 w-3 rounded-full"
                    style={{ backgroundColor: sortedDefinitions[2]?.color || '#f97316' }}
                  />
                  <Text className="font-medium text-gray-300">
                    High Max ({editedThresholds.medium_max + 1} to this value)
                  </Text>
                </div>
                <Text className="text-lg font-semibold text-white">
                  {editedThresholds.high_max}
                </Text>
              </div>
              <input
                type="range"
                min={editedThresholds.medium_max + 1}
                max="99"
                step="1"
                value={editedThresholds.high_max}
                onChange={(e) => handleThresholdChange('high_max', parseInt(e.target.value))}
                className="h-2 w-full cursor-pointer appearance-none rounded-lg bg-gray-700 accent-[#f97316]"
                aria-label="High severity maximum score"
                data-testid="high-max-slider"
              />
              <div className="mt-1 flex justify-between text-xs text-gray-500">
                <span>{editedThresholds.medium_max + 1}</span>
                <span>99</span>
              </div>
            </div>

            {/* Critical Range (read-only, calculated) */}
            <div className="rounded-lg border border-gray-700 bg-gray-800/30 p-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div
                    className="h-3 w-3 rounded-full"
                    style={{ backgroundColor: sortedDefinitions[3]?.color || '#ef4444' }}
                  />
                  <Text className="font-medium text-gray-300">Critical Range</Text>
                </div>
                <Text className="font-mono text-white">
                  {editedThresholds.high_max + 1}-100
                </Text>
              </div>
              <Text className="mt-1 text-xs text-gray-500">
                Automatically calculated from High Max threshold
              </Text>
            </div>
          </div>

          {/* Severity Level Table */}
          <div className="border-t border-gray-800 pt-4">
            <Text className="mb-2 text-sm font-medium text-gray-400">Current Configuration</Text>
            <div className="overflow-hidden rounded-lg border border-gray-700">
              <table className="w-full" role="table">
                <thead>
                  <tr className="border-b border-gray-700 bg-gray-800/50">
                    <th
                      className="px-4 py-2 text-left text-sm font-medium text-gray-300"
                      role="columnheader"
                    >
                      Level
                    </th>
                    <th
                      className="px-4 py-2 text-left text-sm font-medium text-gray-300"
                      role="columnheader"
                    >
                      Range
                    </th>
                    <th
                      className="px-4 py-2 text-left text-sm font-medium text-gray-300"
                      role="columnheader"
                    >
                      Description
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="border-b border-gray-700/50">
                    <td className="px-4 py-2">
                      <div className="flex items-center gap-2">
                        <div
                          className="h-3 w-3 rounded-full"
                          style={{ backgroundColor: sortedDefinitions[0]?.color }}
                        />
                        <Text className="font-medium text-white">Low</Text>
                      </div>
                    </td>
                    <td className="px-4 py-2">
                      <Text className="font-mono text-gray-300">
                        {ranges.low.min}-{ranges.low.max}
                      </Text>
                    </td>
                    <td className="px-4 py-2">
                      <Text className="text-gray-400">Routine activity, no concern</Text>
                    </td>
                  </tr>
                  <tr className="border-b border-gray-700/50">
                    <td className="px-4 py-2">
                      <div className="flex items-center gap-2">
                        <div
                          className="h-3 w-3 rounded-full"
                          style={{ backgroundColor: sortedDefinitions[1]?.color }}
                        />
                        <Text className="font-medium text-white">Medium</Text>
                      </div>
                    </td>
                    <td className="px-4 py-2">
                      <Text className="font-mono text-gray-300">
                        {ranges.medium.min}-{ranges.medium.max}
                      </Text>
                    </td>
                    <td className="px-4 py-2">
                      <Text className="text-gray-400">Notable activity, worth reviewing</Text>
                    </td>
                  </tr>
                  <tr className="border-b border-gray-700/50">
                    <td className="px-4 py-2">
                      <div className="flex items-center gap-2">
                        <div
                          className="h-3 w-3 rounded-full"
                          style={{ backgroundColor: sortedDefinitions[2]?.color }}
                        />
                        <Text className="font-medium text-white">High</Text>
                      </div>
                    </td>
                    <td className="px-4 py-2">
                      <Text className="font-mono text-gray-300">
                        {ranges.high.min}-{ranges.high.max}
                      </Text>
                    </td>
                    <td className="px-4 py-2">
                      <Text className="text-gray-400">Concerning activity, review soon</Text>
                    </td>
                  </tr>
                  <tr>
                    <td className="px-4 py-2">
                      <div className="flex items-center gap-2">
                        <div
                          className="h-3 w-3 rounded-full"
                          style={{ backgroundColor: sortedDefinitions[3]?.color }}
                        />
                        <Text className="font-medium text-white">Critical</Text>
                      </div>
                    </td>
                    <td className="px-4 py-2">
                      <Text className="font-mono text-gray-300">
                        {ranges.critical.min}-{ranges.critical.max}
                      </Text>
                    </td>
                    <td className="px-4 py-2">
                      <Text className="text-gray-400">Immediate attention required</Text>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex gap-3 border-t border-gray-800 pt-4">
            <Button
              onClick={() => void handleSave()}
              disabled={!hasChanges || saving || !!validationError}
              className="flex-1 bg-[#76B900] text-gray-950 hover:bg-[#5c8f00] disabled:cursor-not-allowed disabled:opacity-50"
              data-testid="save-thresholds-button"
            >
              <Save className="mr-2 h-4 w-4" />
              {saving ? 'Saving...' : 'Save Thresholds'}
            </Button>
            <Button
              onClick={handleReset}
              disabled={!hasChanges || saving}
              variant="secondary"
              className="flex-1 disabled:cursor-not-allowed disabled:opacity-50"
              data-testid="reset-thresholds-button"
            >
              <RotateCcw className="mr-2 h-4 w-4" />
              Reset
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}
