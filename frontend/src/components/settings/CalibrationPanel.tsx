/**
 * CalibrationPanel component for Settings page
 *
 * Settings panel for configuring AI calibration thresholds:
 * - View and adjust risk sensitivity thresholds (Low, Medium, High)
 * - Adjust learning rate (decay factor) for threshold adaptation
 * - View feedback statistics and calibration status
 * - Reset to default values
 *
 * This component wraps RiskSensitivitySettings with additional
 * Settings page specific styling and layout.
 *
 * @see NEM-2355 - Create CalibrationPanel component for Settings page
 */

import { Card, Text, Title } from '@tremor/react';
import { clsx } from 'clsx';
import { Settings2 } from 'lucide-react';

import RiskSensitivitySettings from './RiskSensitivitySettings';

export interface CalibrationPanelProps {
  /** Additional CSS classes */
  className?: string;
}

/**
 * CalibrationPanel - Settings panel for AI calibration configuration
 */
export default function CalibrationPanel({ className }: CalibrationPanelProps) {
  return (
    <div className={clsx('space-y-6', className)} data-testid="calibration-panel">
      {/* Section Header */}
      <div className="flex items-center gap-3">
        <Settings2 className="h-6 w-6 text-[#76B900]" />
        <div>
          <Title className="text-white">AI Calibration Settings</Title>
          <Text className="mt-1 text-gray-400">
            Fine-tune how the AI system categorizes risk scores and adapts to your feedback
          </Text>
        </div>
      </div>

      {/* Info Card */}
      <Card className="border-gray-800 bg-[#121212]">
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-gray-300">How Calibration Works</h3>
          <ul className="space-y-2 text-sm text-gray-400">
            <li className="flex items-start gap-2">
              <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-[#76B900]" />
              <span>
                <strong className="text-gray-300">Thresholds</strong> determine how risk scores are
                categorized into Low, Medium, High, and Critical levels.
              </span>
            </li>
            <li className="flex items-start gap-2">
              <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-[#76B900]" />
              <span>
                <strong className="text-gray-300">Learning Rate</strong> controls how quickly
                thresholds adapt when you provide feedback on events.
              </span>
            </li>
            <li className="flex items-start gap-2">
              <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-[#76B900]" />
              <span>
                <strong className="text-gray-300">Feedback</strong> from marking events as false
                positives or missed detections adjusts future risk assessments.
              </span>
            </li>
          </ul>
        </div>
      </Card>

      {/* Risk Sensitivity Settings Component */}
      <RiskSensitivitySettings />
    </div>
  );
}
