import { Card, Title, Text, Button } from '@tremor/react';
import { AlertCircle, Eye, Save, RotateCcw } from 'lucide-react';
import { useEffect, useState, useCallback } from 'react';

import { useSettingsQuery, useUpdateSettings, type DetectionSettings } from '../../hooks/useSettingsApi';

export interface DetectionThresholdsPanelProps {
  className?: string;
}

/**
 * DetectionThresholdsPanel component displays and allows editing of detection confidence thresholds.
 * - Fetches settings from /api/v1/settings endpoint via useSettingsApi
 * - Shows editable threshold sliders with percentage value display
 * - Provides save and reset functionality
 * - Displays explanations for each threshold
 * - Handles loading, error, and success states
 */
export default function DetectionThresholdsPanel({ className }: DetectionThresholdsPanelProps) {
  const { settings, isLoading, error: fetchError } = useSettingsQuery();
  const {
    mutateAsync: updateSettings,
    isPending: isSaving,
    isError: isSaveError,
    error: saveError,
    reset: resetMutation,
  } = useUpdateSettings();

  const [editedThresholds, setEditedThresholds] = useState<DetectionSettings | null>(null);
  const [success, setSuccess] = useState(false);

  // Initialize edited thresholds when settings are loaded
  useEffect(() => {
    if (settings?.detection) {
      setEditedThresholds({
        confidence_threshold: settings.detection.confidence_threshold,
        fast_path_threshold: settings.detection.fast_path_threshold,
      });
    }
  }, [settings?.detection]);

  // Check if there are unsaved changes
  const hasChanges = !!(
    editedThresholds &&
    settings?.detection &&
    (editedThresholds.confidence_threshold !== settings.detection.confidence_threshold ||
      editedThresholds.fast_path_threshold !== settings.detection.fast_path_threshold)
  );

  const handleThresholdChange = useCallback((field: keyof DetectionSettings, value: number) => {
    setEditedThresholds((prev) => (prev ? { ...prev, [field]: value } : prev));
    setSuccess(false);
  }, []);

  const handleSave = async () => {
    if (!editedThresholds || !hasChanges) return;

    try {
      setSuccess(false);
      resetMutation();

      await updateSettings({
        detection: editedThresholds,
      });

      setSuccess(true);

      // Clear success message after 3 seconds
      setTimeout(() => setSuccess(false), 3000);
    } catch {
      // Error is handled by the mutation state
    }
  };

  const handleReset = () => {
    if (settings?.detection) {
      setEditedThresholds({
        confidence_threshold: settings.detection.confidence_threshold,
        fast_path_threshold: settings.detection.fast_path_threshold,
      });
      setSuccess(false);
      resetMutation();
    }
  };

  const errorMessage = fetchError?.message ?? (isSaveError ? saveError?.message : null);

  return (
    <Card
      className={`border-gray-800 bg-[#1A1A1A] shadow-lg ${className || ''}`}
      data-testid="detection-thresholds-card"
    >
      <Title className="mb-4 flex items-center gap-2 text-white">
        <Eye className="h-5 w-5 text-[#76B900]" />
        Detection Thresholds
      </Title>
      <Text className="mb-6 text-gray-300">
        Configure AI detection sensitivity and confidence thresholds
      </Text>

      {isLoading && (
        <div className="space-y-4">
          <div className="skeleton h-12 w-full"></div>
          <div className="skeleton h-12 w-full"></div>
        </div>
      )}

      {errorMessage && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-4">
          <AlertCircle className="h-5 w-5 flex-shrink-0 text-red-400" />
          <Text className="text-red-400">{errorMessage}</Text>
        </div>
      )}

      {success && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-green-500/30 bg-green-500/10 p-4">
          <Save className="h-5 w-5 flex-shrink-0 text-green-500" />
          <Text className="text-green-500">Detection thresholds saved successfully!</Text>
        </div>
      )}

      {!isLoading && editedThresholds && (
        <div className="space-y-6">
          {/* Minimum Confidence Threshold */}
          <div>
            <div className="mb-2 flex items-end justify-between">
              <div>
                <Text className="font-medium text-gray-300">Minimum Confidence</Text>
              </div>
              <span
                className="text-lg font-semibold text-white font-mono"
                data-testid="confidence-value"
              >
                {(editedThresholds.confidence_threshold * 100).toFixed(0)}%
              </span>
            </div>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={editedThresholds.confidence_threshold}
              onChange={(e) =>
                handleThresholdChange('confidence_threshold', parseFloat(e.target.value))
              }
              className="h-2 w-full cursor-pointer appearance-none rounded-lg bg-gray-700 accent-[#76B900]"
              aria-label="Minimum detection confidence threshold"
              data-testid="confidence-slider"
            />
            <div className="mt-1 flex justify-between text-xs text-gray-300">
              <span>0%</span>
              <span>100%</span>
            </div>
            <Text className="mt-2 text-sm text-gray-300">
              Detections below this confidence level will be ignored. Lower values detect more
              objects but may include false positives.
            </Text>
          </div>

          {/* Fast Path Threshold */}
          <div>
            <div className="mb-2 flex items-end justify-between">
              <div>
                <Text className="font-medium text-gray-300">Fast Path Threshold</Text>
              </div>
              <span
                className="text-lg font-semibold text-white font-mono"
                data-testid="fast-path-value"
              >
                {(editedThresholds.fast_path_threshold * 100).toFixed(0)}%
              </span>
            </div>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={editedThresholds.fast_path_threshold}
              onChange={(e) =>
                handleThresholdChange('fast_path_threshold', parseFloat(e.target.value))
              }
              className="h-2 w-full cursor-pointer appearance-none rounded-lg bg-gray-700 accent-[#76B900]"
              aria-label="Fast path confidence threshold"
              data-testid="fast-path-slider"
            />
            <div className="mt-1 flex justify-between text-xs text-gray-300">
              <span>0%</span>
              <span>100%</span>
            </div>
            <Text className="mt-2 text-sm text-gray-300">
              High-confidence detections above this threshold are fast-tracked for immediate
              processing. Higher values prioritize only the most certain detections.
            </Text>
          </div>

          {/* Action Buttons */}
          <div className="flex gap-3 border-t border-gray-800 pt-4">
            <Button
              onClick={() => void handleSave()}
              disabled={!hasChanges || isSaving}
              className="flex-1 bg-[#76B900] text-gray-950 hover:bg-[#5c8f00] disabled:cursor-not-allowed disabled:opacity-50"
              data-testid="save-thresholds-button"
            >
              <Save className="mr-2 h-4 w-4" />
              {isSaving ? 'Saving...' : 'Save Thresholds'}
            </Button>
            <Button
              onClick={handleReset}
              disabled={!hasChanges || isSaving}
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
