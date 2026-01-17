# AI Performance Summary Components

## Purpose

This directory contains the AI Performance Summary Row component, which provides a condensed view of AI pipeline health for the AI Performance page header.

## Files

| File                              | Purpose                                    |
| --------------------------------- | ------------------------------------------ |
| `AIPerformanceSummaryRow.tsx`     | Summary row with 5 clickable indicators    |
| `AIPerformanceSummaryRow.test.tsx`| Test suite for AIPerformanceSummaryRow     |
| `AGENTS.md`                       | This documentation file                    |

## Component Details

### AIPerformanceSummaryRow.tsx

Displays 5 key indicators in a horizontal row at the top of the AI Performance page:

| Indicator   | Description                                    | Status Logic                                    |
| ----------- | ---------------------------------------------- | ----------------------------------------------- |
| RT-DETRv2   | Object detection model status and latency      | Green: <50ms, Yellow: 50-200ms, Red: >200ms/down |
| Nemotron    | LLM analysis model status and latency          | Green: <5s, Yellow: 5-15s, Red: >15s/down        |
| Queues      | Combined queue depth (detection + analysis)    | Green: <5, Yellow: 5-20, Red: >20               |
| Throughput  | Events processed per minute                    | Color based on processing rate                  |
| Errors      | Total pipeline errors                          | Green: 0, Yellow: 1-5, Red: >5                  |

**Props Interface:**

```typescript
interface AIPerformanceSummaryRowProps {
  rtdetr: AIModelStatus;
  nemotron: AIModelStatus;
  detectionLatency?: AILatencyMetrics | null;
  analysisLatency?: AILatencyMetrics | null;
  detectionQueueDepth: number;
  analysisQueueDepth: number;
  totalDetections: number;
  totalEvents: number;
  totalErrors: number;
  throughputPerMinute?: number;
  sectionRefs?: SectionRefs;
  onIndicatorClick?: (indicator: IndicatorType) => void;
  className?: string;
}
```

**Features:**

- Color-coded status indicators (green/yellow/red/gray)
- Click-to-scroll to relevant page sections
- Hover tooltips with additional detail
- Real-time updates via props
- Responsive: 5 columns desktop, 2x3 grid mobile

**Exported Types:**

```typescript
export type IndicatorType = 'rtdetr' | 'nemotron' | 'queues' | 'throughput' | 'errors';
export type StatusColor = 'green' | 'yellow' | 'red' | 'gray';
export interface SectionRefs { ... }
export interface AIPerformanceSummaryRowProps { ... }
```

## Usage

```tsx
import AIPerformanceSummaryRow from './AIPerformanceSummaryRow';
// Or from parent path:
import AIPerformanceSummaryRow from '../ai-performance/AIPerformanceSummaryRow';

<AIPerformanceSummaryRow
  rtdetr={rtdetrStatus}
  nemotron={nemotronStatus}
  detectionLatency={detectionLatency}
  analysisLatency={analysisLatency}
  detectionQueueDepth={queues.detection}
  analysisQueueDepth={queues.analysis}
  totalDetections={metrics.totalDetections}
  totalEvents={metrics.totalEvents}
  totalErrors={metrics.totalErrors}
  sectionRefs={sectionRefs}
  onIndicatorClick={handleIndicatorClick}
/>
```

## Dependencies

- `clsx` - Conditional class composition
- `lucide-react` - CheckCircle, XCircle, AlertCircle, Layers, TrendingUp, AlertTriangle icons
- `../../hooks/useAIMetrics` - AIModelStatus type
- `../../services/metricsParser` - AILatencyMetrics type

## Testing

```bash
# Run component tests
cd frontend && npm test -- AIPerformanceSummaryRow

# Run with coverage
cd frontend && npm test -- --coverage AIPerformanceSummaryRow
```

## Related Components

- `../ai/AIPerformancePage.tsx` - Parent page that uses this summary row
- `../ai/ModelStatusCards.tsx` - Detailed model status cards
- `../ai/LatencyPanel.tsx` - Detailed latency metrics
- `../ai/PipelineHealthPanel.tsx` - Queue and throughput details
