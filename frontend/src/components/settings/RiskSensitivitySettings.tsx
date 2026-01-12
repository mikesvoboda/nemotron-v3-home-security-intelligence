/**
 * RiskSensitivitySettings component
 *
 * Settings panel for configuring risk sensitivity thresholds:
 * - View and adjust calibration thresholds (Low, Medium, High)
 * - Adjust learning rate (decay factor)
 * - View feedback statistics
 * - Reset to default values
 *
 * @see NEM-2320 - Add Risk Sensitivity settings to Settings page
 */

import { Card, Title, Text, Button } from '@tremor/react';
import { clsx } from 'clsx';
import { AlertCircle, RotateCcw, Save, Sliders, TrendingDown, TrendingUp } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import {
  fetchCalibration,
  fetchCalibrationDefaults,
  fetchFeedbackStats,
  resetCalibration,
  updateCalibration,
  type CalibrationResponse,
  type CalibrationDefaultsResponse,
  type FeedbackStatsResponse,
} from '../../services/api';

export interface RiskSensitivitySettingsProps {
  className?: string;
}

interface ThresholdState {
  low: number;
  medium: number;
  high: number;
  decayFactor: number;
}

/**
 * Settings section for risk sensitivity calibration
 */
export default function RiskSensitivitySettings({ className }: RiskSensitivitySettingsProps) {
  const [calibration, setCalibration] = useState<CalibrationResponse | null>(null);
  const [defaults, setDefaults] = useState<CalibrationDefaultsResponse | null>(null);
  const [feedbackStats, setFeedbackStats] = useState<FeedbackStatsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  // Local state for slider values (immediate visual feedback)
  const [thresholds, setThresholds] = useState<ThresholdState>({
    low: 30,
    medium: 60,
    high: 85,
    decayFactor: 0.1,
  });

  // Track if there are unsaved changes
  const hasChanges =
    calibration &&
    (thresholds.low !== calibration.low_threshold ||
      thresholds.medium !== calibration.medium_threshold ||
      thresholds.high !== calibration.high_threshold ||
      thresholds.decayFactor !== calibration.decay_factor);

  // Load calibration data on mount
  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        setError(null);

        const [calibrationData, defaultsData, statsData] = await Promise.all([
          fetchCalibration(),
          fetchCalibrationDefaults(),
          fetchFeedbackStats().catch(() => null), // Stats are optional
        ]);

        setCalibration(calibrationData);
        setDefaults(defaultsData);
        setFeedbackStats(statsData);
        setThresholds({
          low: calibrationData.low_threshold,
          medium: calibrationData.medium_threshold,
          high: calibrationData.high_threshold,
          decayFactor: calibrationData.decay_factor,
        });
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load calibration settings');
      } finally {
        setLoading(false);
      }
    }

    void loadData();
  }, []);

  // Validate threshold ordering
  const validateThresholds = useCallback((low: number, medium: number, high: number): string | null => {
    if (low >= medium) {
      return `Low threshold (${low}) must be less than Medium threshold (${medium})`;
    }
    if (medium >= high) {
      return `Medium threshold (${medium}) must be less than High threshold (${high})`;
    }
    return null;
  }, []);

  // Handle threshold changes with validation
  const handleThresholdChange = useCallback(
    (field: 'low' | 'medium' | 'high', value: number) => {
      const newThresholds = { ...thresholds, [field]: value };
      setThresholds(newThresholds);

      const validationErr = validateThresholds(
        newThresholds.low,
        newThresholds.medium,
        newThresholds.high
      );
      setValidationError(validationErr);
    },
    [thresholds, validateThresholds]
  );

  // Handle decay factor change
  const handleDecayFactorChange = useCallback((value: number) => {
    setThresholds((prev) => ({ ...prev, decayFactor: value }));
  }, []);

  // Save changes
  const handleSave = useCallback(async () => {
    if (!hasChanges || validationError) return;

    try {
      setSaving(true);
      setError(null);
      setSuccess(false);

      const updated = await updateCalibration({
        low_threshold: thresholds.low,
        medium_threshold: thresholds.medium,
        high_threshold: thresholds.high,
        decay_factor: thresholds.decayFactor,
      });

      setCalibration(updated);
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save calibration');
    } finally {
      setSaving(false);
    }
  }, [hasChanges, validationError, thresholds]);

  // Reset to defaults
  const handleReset = useCallback(async () => {
    try {
      setResetting(true);
      setError(null);
      setSuccess(false);
      setValidationError(null);

      const result = await resetCalibration();
      setCalibration(result.calibration);
      setThresholds({
        low: result.calibration.low_threshold,
        medium: result.calibration.medium_threshold,
        high: result.calibration.high_threshold,
        decayFactor: result.calibration.decay_factor,
      });
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reset calibration');
    } finally {
      setResetting(false);
    }
  }, []);

  // Discard changes
  const handleDiscard = useCallback(() => {
    if (calibration) {
      setThresholds({
        low: calibration.low_threshold,
        medium: calibration.medium_threshold,
        high: calibration.high_threshold,
        decayFactor: calibration.decay_factor,
      });
      setValidationError(null);
    }
  }, [calibration]);

  // Calculate total feedback count
  const totalFeedback = calibration
    ? calibration.false_positive_count + calibration.missed_detection_count
    : 0;

  return (
    <Card
      className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
      data-testid="risk-sensitivity-settings"
    >
      <div className="mb-6">
        <div className="flex items-center gap-3">
          <Sliders className="h-6 w-6 text-[#76B900]" />
          <div>
            <Title className="text-white">Risk Sensitivity</Title>
            <Text className="mt-1 text-gray-400">
              Adjust how your system categorizes risk scores
            </Text>
          </div>
        </div>
      </div>

      {/* Loading State */}
      {loading && (
        <div className="space-y-4" data-testid="loading-skeleton">
          <div className="skeleton h-12 w-full rounded bg-gray-700"></div>
          <div className="skeleton h-12 w-full rounded bg-gray-700"></div>
          <div className="skeleton h-12 w-full rounded bg-gray-700"></div>
          <div className="skeleton h-12 w-full rounded bg-gray-700"></div>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-4">
          <AlertCircle className="h-5 w-5 flex-shrink-0 text-red-400" />
          <Text className="text-red-400">{error}</Text>
        </div>
      )}

      {/* Success State */}
      {success && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-green-500/30 bg-green-500/10 p-4">
          <Save className="h-5 w-5 flex-shrink-0 text-green-500" />
          <Text className="text-green-500">Settings saved successfully!</Text>
        </div>
      )}

      {/* Validation Error */}
      {validationError && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-yellow-500/30 bg-yellow-500/10 p-4">
          <AlertCircle className="h-5 w-5 flex-shrink-0 text-yellow-400" />
          <Text className="text-yellow-400">{validationError}</Text>
        </div>
      )}

      {/* Main Content */}
      {!loading && calibration && (
        <div className="space-y-6">
          {/* Feedback Info Banner */}
          <div className="rounded-lg border border-gray-700 bg-[#121212] p-4">
            <Text className="text-gray-300">
              Your thresholds have been tuned based on{' '}
              <span className="font-semibold text-[#76B900]">{totalFeedback}</span> feedback
              submissions.
            </Text>
          </div>

          {/* Threshold Sliders */}
          <div className="space-y-6">
            {/* Low to Medium Threshold */}
            <div data-testid="low-threshold-slider">
              <div className="mb-2 flex items-end justify-between">
                <div>
                  <Text className="font-medium text-gray-300">Low to Medium</Text>
                  <Text className="mt-1 text-xs text-gray-500">
                    Events below this score are considered low risk
                  </Text>
                </div>
                <Text className="text-lg font-semibold text-white">{thresholds.low}</Text>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                step="1"
                value={thresholds.low}
                onChange={(e) => handleThresholdChange('low', parseInt(e.target.value, 10))}
                className="h-2 w-full cursor-pointer appearance-none rounded-lg bg-gray-700 accent-[#76B900]"
                aria-label="Low to Medium threshold"
              />
              <div className="mt-1 flex justify-between text-xs text-gray-500">
                <span>0</span>
                <span>100</span>
              </div>
            </div>

            {/* Medium to High Threshold */}
            <div data-testid="medium-threshold-slider">
              <div className="mb-2 flex items-end justify-between">
                <div>
                  <Text className="font-medium text-gray-300">Medium to High</Text>
                  <Text className="mt-1 text-xs text-gray-500">
                    Events above this are considered high risk
                  </Text>
                </div>
                <Text className="text-lg font-semibold text-white">{thresholds.medium}</Text>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                step="1"
                value={thresholds.medium}
                onChange={(e) => handleThresholdChange('medium', parseInt(e.target.value, 10))}
                className="h-2 w-full cursor-pointer appearance-none rounded-lg bg-gray-700 accent-[#76B900]"
                aria-label="Medium to High threshold"
              />
              <div className="mt-1 flex justify-between text-xs text-gray-500">
                <span>0</span>
                <span>100</span>
              </div>
            </div>

            {/* High to Critical Threshold */}
            <div data-testid="high-threshold-slider">
              <div className="mb-2 flex items-end justify-between">
                <div>
                  <Text className="font-medium text-gray-300">High to Critical</Text>
                  <Text className="mt-1 text-xs text-gray-500">
                    Events above this are considered critical risk
                  </Text>
                </div>
                <Text className="text-lg font-semibold text-white">{thresholds.high}</Text>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                step="1"
                value={thresholds.high}
                onChange={(e) => handleThresholdChange('high', parseInt(e.target.value, 10))}
                className="h-2 w-full cursor-pointer appearance-none rounded-lg bg-gray-700 accent-[#76B900]"
                aria-label="High to Critical threshold"
              />
              <div className="mt-1 flex justify-between text-xs text-gray-500">
                <span>0</span>
                <span>100</span>
              </div>
            </div>

            {/* Learning Rate (Decay Factor) */}
            <div data-testid="learning-rate-slider">
              <div className="mb-2 flex items-end justify-between">
                <div>
                  <Text className="font-medium text-gray-300">Learning Rate</Text>
                  <Text className="mt-1 text-xs text-gray-500">
                    How quickly thresholds adapt to feedback
                  </Text>
                </div>
                <Text className="text-lg font-semibold text-white">
                  {thresholds.decayFactor.toFixed(2)}
                </Text>
              </div>
              <input
                type="range"
                min="0"
                max="1"
                step="0.01"
                value={thresholds.decayFactor}
                onChange={(e) => handleDecayFactorChange(parseFloat(e.target.value))}
                className="h-2 w-full cursor-pointer appearance-none rounded-lg bg-gray-700 accent-[#76B900]"
                aria-label="Learning rate"
              />
              <div className="mt-1 flex justify-between text-xs text-gray-500">
                <span>0.00 (Slow)</span>
                <span>1.00 (Fast)</span>
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex gap-3 border-t border-gray-800 pt-4">
            <Button
              onClick={() => void handleSave()}
              disabled={!hasChanges || saving || !!validationError}
              className="flex-1 bg-[#76B900] text-gray-950 hover:bg-[#5c8f00] disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Save className="mr-2 h-4 w-4" />
              {saving ? 'Saving...' : 'Save Changes'}
            </Button>
            <Button
              onClick={handleDiscard}
              disabled={!hasChanges || saving}
              variant="secondary"
              className="flex-1 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Discard
            </Button>
          </div>

          {/* Reset to Defaults */}
          <div className="border-t border-gray-800 pt-4">
            <Button
              onClick={() => void handleReset()}
              disabled={resetting}
              variant="secondary"
              className="w-full border-gray-600 text-gray-300 hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <RotateCcw className="mr-2 h-4 w-4" />
              {resetting ? 'Resetting...' : 'Reset to Defaults'}
            </Button>
            {defaults && (
              <Text className="mt-2 text-center text-xs text-gray-500">
                Defaults: Low={defaults.low_threshold}, Medium={defaults.medium_threshold}, High=
                {defaults.high_threshold}
              </Text>
            )}
          </div>

          {/* Feedback Statistics */}
          <div className="border-t border-gray-800 pt-4">
            <Text className="mb-3 font-medium text-gray-300">Feedback Stats</Text>
            <div className="grid grid-cols-2 gap-4">
              <div className="flex items-center gap-2 rounded-lg border border-gray-700 bg-[#121212] p-3">
                <TrendingDown className="h-5 w-5 text-yellow-500" />
                <div>
                  <Text className="text-2xl font-semibold text-white">
                    {calibration.false_positive_count}
                  </Text>
                  <Text className="text-xs text-gray-500">False positives marked</Text>
                </div>
              </div>
              <div className="flex items-center gap-2 rounded-lg border border-gray-700 bg-[#121212] p-3">
                <TrendingUp className="h-5 w-5 text-red-500" />
                <div>
                  <Text className="text-2xl font-semibold text-white">
                    {calibration.missed_detection_count}
                  </Text>
                  <Text className="text-xs text-gray-500">Missed detections marked</Text>
                </div>
              </div>
            </div>

            {/* Additional feedback breakdown from stats endpoint */}
            {feedbackStats && feedbackStats.total_feedback > 0 && (
              <div className="mt-4 rounded-lg border border-gray-700 bg-[#121212] p-3">
                <Text className="mb-2 text-xs font-medium text-gray-400">
                  Feedback by Type ({feedbackStats.total_feedback} total)
                </Text>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  {Object.entries(feedbackStats.by_type).map(([type, count]) => (
                    <div key={type} className="flex justify-between">
                      <Text className="text-gray-400 capitalize">{type.replace(/_/g, ' ')}</Text>
                      <Text className="font-medium text-white">{String(count)}</Text>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </Card>
  );
}
