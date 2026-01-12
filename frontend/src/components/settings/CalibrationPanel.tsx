/**
 * CalibrationPanel - Settings panel for AI calibration and feedback statistics
 *
 * This component provides a unified interface for:
 * - Viewing and adjusting risk threshold settings
 * - Displaying feedback statistics from user submissions
 * - Managing sensitivity levels for event classification
 *
 * Settings panel for configuring AI calibration thresholds:
 * - View and adjust risk sensitivity thresholds (Low, Medium, High)
 * - Adjust learning rate (decay factor) for threshold adaptation
 * - View feedback statistics and calibration status
 * - Reset to default values
 *
 * Uses RiskSensitivitySettings as the core implementation, wrapped
 * with additional context and documentation for the Settings page.
 *
 * @see NEM-2355 - Create CalibrationPanel component for Settings page
 * @see NEM-2356 - Add CalibrationPanel to Settings page
 */

import { Card, Text, Title } from '@tremor/react';
import { clsx } from 'clsx';
import { Activity, BarChart3, Info, Settings2 } from 'lucide-react';

import RiskSensitivitySettings from './RiskSensitivitySettings';

export interface CalibrationPanelProps {
  /** Additional CSS classes */
  className?: string;
}

/**
 * CalibrationPanel - Main component for calibration settings
 *
 * Provides threshold adjustment and feedback statistics display.
 */
export default function CalibrationPanel({ className }: CalibrationPanelProps) {
  return (
    <div className={clsx('space-y-6', className)} data-testid="calibration-panel">
      {/* Introduction Card */}
      <Card className="border-gray-800 bg-[#1A1A1A]">
        <div className="flex items-start gap-4">
          <div className="rounded-lg bg-[#76B900]/20 p-3">
            <Settings2 className="h-6 w-6 text-[#76B900]" />
          </div>
          <div className="flex-1">
            <Title className="text-white">AI Calibration</Title>
            <Text className="mt-2 text-gray-400">
              Fine-tune how the AI classifies security events. Adjust risk thresholds based on
              your environment and provide feedback to improve detection accuracy over time.
            </Text>
          </div>
        </div>
      </Card>

      {/* How It Works Card */}
      <Card className="border-gray-800 bg-[#1A1A1A]">
        <div className="mb-4 flex items-center gap-2">
          <Info className="h-5 w-5 text-[#76B900]" />
          <Title className="text-white">How Calibration Works</Title>
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          <div className="rounded-lg border border-gray-700 bg-[#121212] p-4">
            <div className="mb-2 flex items-center gap-2">
              <Activity className="h-4 w-4 text-blue-400" />
              <Text className="font-medium text-gray-300">Threshold Adjustment</Text>
            </div>
            <Text className="text-sm text-gray-500">
              Set the risk score boundaries that determine Low, Medium, High, and Critical event classifications.
            </Text>
          </div>
          <div className="rounded-lg border border-gray-700 bg-[#121212] p-4">
            <div className="mb-2 flex items-center gap-2">
              <BarChart3 className="h-4 w-4 text-green-400" />
              <Text className="font-medium text-gray-300">Feedback Learning</Text>
            </div>
            <Text className="text-sm text-gray-500">
              Your feedback on event accuracy helps the system learn and improve classification over time.
            </Text>
          </div>
          <div className="rounded-lg border border-gray-700 bg-[#121212] p-4">
            <div className="mb-2 flex items-center gap-2">
              <Settings2 className="h-4 w-4 text-yellow-400" />
              <Text className="font-medium text-gray-300">Learning Rate</Text>
            </div>
            <Text className="text-sm text-gray-500">
              Control how quickly thresholds adapt based on feedback - higher rates mean faster adaptation.
            </Text>
          </div>
        </div>
      </Card>

      {/* Risk Sensitivity Settings (core calibration functionality) */}
      <RiskSensitivitySettings />

      {/* Tips Card */}
      <Card className="border-gray-800 bg-[#1A1A1A]">
        <Title className="mb-3 text-white">Tips for Effective Calibration</Title>
        <ul className="space-y-2 text-sm text-gray-400">
          <li className="flex items-start gap-2">
            <span className="mt-1 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-[#76B900]" />
            <span>
              <strong className="text-gray-300">Start with defaults:</strong> The default thresholds
              work well for most environments. Only adjust if you see consistent misclassifications.
            </span>
          </li>
          <li className="flex items-start gap-2">
            <span className="mt-1 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-[#76B900]" />
            <span>
              <strong className="text-gray-300">Provide consistent feedback:</strong> Regular feedback
              on event accuracy helps the system learn your specific environment.
            </span>
          </li>
          <li className="flex items-start gap-2">
            <span className="mt-1 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-[#76B900]" />
            <span>
              <strong className="text-gray-300">Lower thresholds for more alerts:</strong> If you want
              more sensitive detection, lower the threshold values.
            </span>
          </li>
          <li className="flex items-start gap-2">
            <span className="mt-1 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-[#76B900]" />
            <span>
              <strong className="text-gray-300">Use a slower learning rate:</strong> If threshold
              changes seem too aggressive, reduce the learning rate for more gradual adaptation.
            </span>
          </li>
        </ul>
      </Card>
    </div>
  );
}
