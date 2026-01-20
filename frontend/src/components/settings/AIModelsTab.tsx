/**
 * AIModelsTab - Comprehensive AI Models settings tab
 *
 * Combines core AI model status (RT-DETRv2, Nemotron) with
 * Model Zoo status cards for all 18 specialized models.
 *
 * @see NEM-3084 - Integrate comprehensive AI Models settings tab
 */

import AIModelsSettings from './AIModelsSettings';
import ModelZooSection from '../ai/ModelZooSection';

/**
 * Props for AIModelsTab component
 */
export interface AIModelsTabProps {
  /** Optional className for custom styling */
  className?: string;
}

/**
 * AIModelsTab component displays all AI model information in the Settings page
 *
 * Sections:
 * - Core Models: RT-DETRv2 (object detection) and Nemotron (risk analysis)
 * - Model Zoo: 18 specialized models with status, VRAM usage, and latency charts
 *
 * Features:
 * - Real-time status updates via HTTP polling
 * - NVIDIA dark theme styling
 * - Responsive layout
 */
export default function AIModelsTab({ className }: AIModelsTabProps) {
  return (
    <div className={className} data-testid="ai-models-tab">
      {/* Core Models Section */}
      <section className="mb-8">
        <AIModelsSettings />
      </section>

      {/* Model Zoo Section */}
      <section>
        <ModelZooSection pollingInterval={30000} />
      </section>
    </div>
  );
}
