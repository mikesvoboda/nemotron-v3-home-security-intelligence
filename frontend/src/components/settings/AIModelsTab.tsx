/**
 * AIModelsTab - Comprehensive AI Models settings tab
 *
 * Combines core AI model status (RT-DETRv2, Nemotron) with
 * Model Zoo status cards for all 18 specialized models, plus
 * enhanced model management panel with VRAM visualization.
 *
 * @see NEM-3084 - Integrate comprehensive AI Models settings tab
 * @see NEM-3179 - Add AI model management UI
 */

import AIModelsSettings from './AIModelsSettings';
import ModelManagementPanel from './ModelManagementPanel';
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
 * - Model Management: VRAM usage overview, model status summary, categorized models
 * - Model Zoo: Detailed model cards with latency charts
 *
 * Features:
 * - Real-time status updates via HTTP polling
 * - VRAM usage visualization with color-coded indicators
 * - Model performance metrics (load count, latency)
 * - NVIDIA dark theme styling
 * - Responsive layout
 */
export default function AIModelsTab({ className }: AIModelsTabProps) {
  return (
    <div className={className} data-testid="ai-models-tab">
      {/* Core Models Section - RT-DETRv2 and Nemotron */}
      <section className="mb-8">
        <AIModelsSettings />
      </section>

      {/* Model Management Panel - VRAM usage and categorized model overview */}
      <section className="mb-8">
        <ModelManagementPanel />
      </section>

      {/* Model Zoo Section - Detailed cards with latency charts */}
      <section>
        <ModelZooSection pollingInterval={30000} />
      </section>
    </div>
  );
}
