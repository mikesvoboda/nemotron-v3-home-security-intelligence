/**
 * Example usage of the RiskGauge component
 * This file demonstrates how to use the RiskGauge in different scenarios
 */

import RiskGauge from './RiskGauge';

export function RiskGaugeExamples() {
  return (
    <div className="grid grid-cols-1 gap-8 p-8 md:grid-cols-2 lg:grid-cols-3">
      {/* Basic usage - Low risk */}
      <div className="rounded-lg bg-gray-900 p-6">
        <h3 className="mb-4 text-lg font-semibold text-white">Low Risk (15/100)</h3>
        <RiskGauge value={15} />
      </div>

      {/* Medium risk without label */}
      <div className="rounded-lg bg-gray-900 p-6">
        <h3 className="mb-4 text-lg font-semibold text-white">
          Medium Risk - No Label (40/100)
        </h3>
        <RiskGauge value={40} showLabel={false} />
      </div>

      {/* High risk with small size */}
      <div className="rounded-lg bg-gray-900 p-6">
        <h3 className="mb-4 text-lg font-semibold text-white">High Risk - Small (65/100)</h3>
        <RiskGauge value={65} size="sm" />
      </div>

      {/* Critical risk with large size */}
      <div className="rounded-lg bg-gray-900 p-6">
        <h3 className="mb-4 text-lg font-semibold text-white">Critical Risk - Large (90/100)</h3>
        <RiskGauge value={90} size="lg" />
      </div>

      {/* With history sparkline */}
      <div className="rounded-lg bg-gray-900 p-6">
        <h3 className="mb-4 text-lg font-semibold text-white">With Risk History (55/100)</h3>
        <RiskGauge value={55} history={[10, 20, 35, 45, 50, 55]} />
      </div>

      {/* Edge case - Zero risk */}
      <div className="rounded-lg bg-gray-900 p-6">
        <h3 className="mb-4 text-lg font-semibold text-white">Zero Risk (0/100)</h3>
        <RiskGauge value={0} />
      </div>

      {/* Edge case - Maximum risk */}
      <div className="rounded-lg bg-gray-900 p-6">
        <h3 className="mb-4 text-lg font-semibold text-white">Maximum Risk (100/100)</h3>
        <RiskGauge value={100} />
      </div>

      {/* With custom className */}
      <div className="rounded-lg bg-gray-900 p-6">
        <h3 className="mb-4 text-lg font-semibold text-white">Custom Styling (30/100)</h3>
        <RiskGauge value={30} className="border-2 border-primary" />
      </div>
    </div>
  );
}

/**
 * Integration example showing dynamic risk updates
 */
export function DynamicRiskGaugeExample() {
  // In a real application, this would come from your state management
  // For example, from a WebSocket connection or API polling
  const currentRiskScore = 42; // Would be dynamic
  const riskHistory = [20, 25, 30, 35, 40, 42]; // Would be dynamic

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="w-full max-w-md rounded-lg bg-gray-900 p-8 shadow-xl">
        <h2 className="mb-6 text-center text-2xl font-bold text-white">
          Current Security Risk Level
        </h2>
        <RiskGauge value={currentRiskScore} history={riskHistory} size="lg" />
        <p className="mt-6 text-center text-sm text-gray-400">
          Real-time risk assessment based on AI analysis of camera feeds
        </p>
      </div>
    </div>
  );
}
