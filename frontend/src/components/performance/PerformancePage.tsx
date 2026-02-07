/**
 * PerformancePage - Full-page performance monitoring view
 *
 * Composes the three performance sub-components into a single page:
 * - PerformanceDashboard: Real-time metric cards (GPU, AI models, databases, host, containers)
 * - PerformanceCharts: Time-series charts (GPU utilization, temperature, latency, resources)
 * - PerformanceAlerts: Active threshold breach alerts
 *
 * Mounted at the /performance route.
 */

import PerformanceAlerts from './PerformanceAlerts';
import PerformanceCharts from './PerformanceCharts';
import PerformanceDashboard from './PerformanceDashboard';

export default function PerformancePage() {
  return (
    <div
      className="min-h-screen bg-[#121212] p-8"
      data-testid="performance-page"
    >
      <div className="mx-auto max-w-[1920px] space-y-8">
        {/* Real-time metric cards */}
        <PerformanceDashboard />

        {/* Active performance alerts */}
        <PerformanceAlerts />

        {/* Historical time-series charts */}
        <PerformanceCharts />
      </div>
    </div>
  );
}
