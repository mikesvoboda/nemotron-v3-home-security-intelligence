/**
 * ModelStatusCards - Displays RT-DETRv2 and Nemotron model status cards
 *
 * Shows status badges, health information, and key metrics for each AI model.
 * This component is designed for the AI Performance page.
 */

import { Card, Title, Text, Badge } from '@tremor/react';
import { clsx } from 'clsx';
import { Cpu, Brain, CheckCircle, XCircle, AlertTriangle, HelpCircle } from 'lucide-react';

import type { AIModelStatus } from '../../hooks/useAIMetrics';
import type { AILatencyMetrics } from '../../services/metricsParser';

export interface ModelStatusCardsProps {
  /** RT-DETR model status */
  rtdetr: AIModelStatus;
  /** Nemotron model status */
  nemotron: AIModelStatus;
  /** RT-DETR detection latency (for inline stats) */
  detectionLatency?: AILatencyMetrics | null;
  /** Nemotron analysis latency (for inline stats) */
  analysisLatency?: AILatencyMetrics | null;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Get badge color based on status
 */
function getStatusColor(status: string): 'green' | 'yellow' | 'red' | 'gray' {
  switch (status) {
    case 'healthy':
      return 'green';
    case 'degraded':
      return 'yellow';
    case 'unhealthy':
      return 'red';
    default:
      return 'gray';
  }
}

/**
 * Get status icon based on status
 */
function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case 'healthy':
      return <CheckCircle className="h-5 w-5 text-green-500" />;
    case 'degraded':
      return <AlertTriangle className="h-5 w-5 text-yellow-500" />;
    case 'unhealthy':
      return <XCircle className="h-5 w-5 text-red-500" />;
    default:
      return <HelpCircle className="h-5 w-5 text-gray-500" />;
  }
}

/**
 * Format latency value for display
 */
function formatLatency(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return 'N/A';
  if (ms < 1) return '< 1ms';
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

/**
 * ModelStatusCards - Grid of AI model status cards
 */
export default function ModelStatusCards({
  rtdetr,
  nemotron,
  detectionLatency,
  analysisLatency,
  className,
}: ModelStatusCardsProps) {
  return (
    <div className={clsx('grid gap-4 md:grid-cols-2', className)} data-testid="model-status-cards">
      {/* RT-DETRv2 Card */}
      <Card className="border-gray-800 bg-[#1A1A1A] shadow-lg" data-testid="rtdetr-status-card">
        <div className="mb-4 flex items-center justify-between">
          <Title className="flex items-center gap-2 text-white">
            <Cpu className="h-5 w-5 text-[#76B900]" />
            RT-DETRv2
          </Title>
          <Badge color={getStatusColor(rtdetr.status)} data-testid="rtdetr-badge">
            {rtdetr.status}
          </Badge>
        </div>

        <div className="space-y-3">
          {/* Status Row */}
          <div className="flex items-center gap-3 rounded-lg bg-gray-800/50 p-3">
            <StatusIcon status={rtdetr.status} />
            <div className="flex-1">
              <Text className="text-sm font-medium text-gray-300">Object Detection</Text>
              {rtdetr.message && <Text className="text-xs text-gray-500">{rtdetr.message}</Text>}
            </div>
          </div>

          {/* Latency Stats (if available) */}
          {detectionLatency && (
            <div className="rounded-lg bg-gray-800/50 p-3">
              <Text className="mb-2 text-xs font-medium text-gray-400">Inference Latency</Text>
              <div className="grid grid-cols-3 gap-2 text-center">
                <div>
                  <Text className="text-xs text-gray-500">Avg</Text>
                  <Text className="font-semibold text-white">
                    {formatLatency(detectionLatency.avg_ms)}
                  </Text>
                </div>
                <div>
                  <Text className="text-xs text-gray-500">P95</Text>
                  <Text className="font-semibold text-white">
                    {formatLatency(detectionLatency.p95_ms)}
                  </Text>
                </div>
                <div>
                  <Text className="text-xs text-gray-500">P99</Text>
                  <Text className="font-semibold text-white">
                    {formatLatency(detectionLatency.p99_ms)}
                  </Text>
                </div>
              </div>
              {detectionLatency.sample_count > 0 && (
                <Text className="mt-2 text-center text-xs text-gray-500">
                  {detectionLatency.sample_count.toLocaleString()} samples
                </Text>
              )}
            </div>
          )}

          {/* Model Info */}
          <div className="text-xs text-gray-500">
            <Text>Real-Time Detection Transformer v2</Text>
            <Text>COCO + Objects365 pre-trained</Text>
          </div>
        </div>
      </Card>

      {/* Nemotron Card */}
      <Card className="border-gray-800 bg-[#1A1A1A] shadow-lg" data-testid="nemotron-status-card">
        <div className="mb-4 flex items-center justify-between">
          <Title className="flex items-center gap-2 text-white">
            <Brain className="h-5 w-5 text-[#76B900]" />
            Nemotron
          </Title>
          <Badge color={getStatusColor(nemotron.status)} data-testid="nemotron-badge">
            {nemotron.status}
          </Badge>
        </div>

        <div className="space-y-3">
          {/* Status Row */}
          <div className="flex items-center gap-3 rounded-lg bg-gray-800/50 p-3">
            <StatusIcon status={nemotron.status} />
            <div className="flex-1">
              <Text className="text-sm font-medium text-gray-300">Risk Analysis LLM</Text>
              {nemotron.message && (
                <Text className="text-xs text-gray-500">{nemotron.message}</Text>
              )}
            </div>
          </div>

          {/* Latency Stats (if available) */}
          {analysisLatency && (
            <div className="rounded-lg bg-gray-800/50 p-3">
              <Text className="mb-2 text-xs font-medium text-gray-400">Inference Latency</Text>
              <div className="grid grid-cols-3 gap-2 text-center">
                <div>
                  <Text className="text-xs text-gray-500">Avg</Text>
                  <Text className="font-semibold text-white">
                    {formatLatency(analysisLatency.avg_ms)}
                  </Text>
                </div>
                <div>
                  <Text className="text-xs text-gray-500">P95</Text>
                  <Text className="font-semibold text-white">
                    {formatLatency(analysisLatency.p95_ms)}
                  </Text>
                </div>
                <div>
                  <Text className="text-xs text-gray-500">P99</Text>
                  <Text className="font-semibold text-white">
                    {formatLatency(analysisLatency.p99_ms)}
                  </Text>
                </div>
              </div>
              {analysisLatency.sample_count > 0 && (
                <Text className="mt-2 text-center text-xs text-gray-500">
                  {analysisLatency.sample_count.toLocaleString()} samples
                </Text>
              )}
            </div>
          )}

          {/* Model Info */}
          <div className="text-xs text-gray-500">
            <Text>NVIDIA Nemotron Mini 4B Instruct</Text>
            <Text>via llama.cpp inference server</Text>
          </div>
        </div>
      </Card>
    </div>
  );
}
