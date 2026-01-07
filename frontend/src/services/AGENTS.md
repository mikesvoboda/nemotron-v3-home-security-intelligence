# Frontend Services Directory

## Purpose

REST API client and logging service for interacting with the FastAPI backend. Provides typed fetch wrappers for all HTTP endpoints and centralized error logging.

## Key Files

| File                          | Purpose                                                       |
| ----------------------------- | ------------------------------------------------------------- |
| `api.ts`                      | Complete API client with typed methods for all REST endpoints |
| `api.test.ts`                 | Comprehensive test coverage for API client                    |
| `api.abort.test.ts`           | Tests for request cancellation and AbortController usage      |
| `api.missing-coverage.test.ts`| Tests for missing coverage scenarios                          |
| `auditApi.ts`                 | AI pipeline audit API client (model contributions, stats)     |
| `auditApi.test.ts`            | Tests for audit API client                                    |
| `abTestService.ts`            | A/B testing service for prompt playground                     |
| `abTestService.test.ts`       | Tests for A/B testing service                                 |
| `promptManagementApi.ts`      | Prompt management API client (CRUD, history, import/export)   |
| `promptManagementApi.test.ts` | Tests for prompt management API                               |
| `logger.ts`                   | Frontend logging service with batched backend sync            |
| `logger.test.ts`              | Tests for logger functionality                                |
| `metricsParser.ts`            | Prometheus text format parser for AI performance metrics      |
| `metricsParser.test.ts`       | Tests for Prometheus metrics parsing                          |
| `interceptors.ts`             | HTTP request/response interceptors for api client             |
| `interceptors.test.ts`        | Tests for interceptors                                        |
| `queryClient.ts`              | TanStack Query configuration and query key factories          |
| `queryClient.test.ts`         | Tests for QueryClient configuration                           |
| `.gitkeep`                    | Placeholder file                                              |

## API Client Structure (`api.ts`)

### Type Generation

**Types are auto-generated from the backend OpenAPI specification.** Do not manually define types that exist in the backend schemas.

```typescript
// Types re-exported from ../types/generated/
export type {
  Camera,
  CameraCreate,
  CameraUpdate,
  CameraListResponse,
  Event,
  EventListResponse,
  EventStatsResponse,
  Detection,
  DetectionListResponse,
  HealthResponse,
  ServiceStatus,
  GPUStats,
  GPUStatsHistoryResponse,
  SystemConfig,
  SystemConfigUpdate,
  SystemStats,
  LogEntry,
  LogsResponse,
  LogStats,
  FrontendLogCreate,
  DLQJobResponse,
  DLQJobsResponse,
  DLQStatsResponse,
  DLQClearResponse,
  DLQRequeueResponse,
  // ... and more
} from '../types/generated';
```

Run `./scripts/generate-types.sh` to regenerate types after backend changes.

### Configuration

| Environment Variable | Purpose                            | Default              |
| -------------------- | ---------------------------------- | -------------------- |
| `VITE_API_BASE_URL`  | Base URL for REST API calls        | `''` (relative)      |
| `VITE_WS_BASE_URL`   | Base URL for WebSocket connections | Uses window.location |
| `VITE_API_KEY`       | API key for authentication         | undefined            |

### WebSocket URL Helpers

```typescript
// Build WebSocket URL with proper protocol and optional API key
buildWebSocketUrl(endpoint: string): string
// Example: buildWebSocketUrl('/ws/events') => 'ws://localhost:8000/ws/events?api_key=xxx'

// Check if API key is configured
getApiKey(): string | undefined
```

The `buildWebSocketUrl` function:

- Uses `VITE_WS_BASE_URL` if set, otherwise falls back to `window.location.host`
- Automatically selects `ws:` or `wss:` based on page protocol
- Appends `api_key` query parameter if `VITE_API_KEY` is configured

### Core Functions

```typescript
// Internal - wraps fetch with JSON handling and error parsing
fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T>

// Internal - handles response status and JSON parsing
handleResponse<T>(response: Response): Promise<T>
```

### Camera Endpoints

```typescript
fetchCameras(): Promise<Camera[]>                                // GET /api/cameras
fetchCamera(id: string): Promise<Camera>                         // GET /api/cameras/{id}
createCamera(data: CameraCreate): Promise<Camera>                // POST /api/cameras
updateCamera(id: string, data: CameraUpdate): Promise<Camera>    // PATCH /api/cameras/{id}
deleteCamera(id: string): Promise<void>                          // DELETE /api/cameras/{id}
getCameraSnapshotUrl(cameraId: string): string                   // URL for snapshot image
```

### System Endpoints

```typescript
fetchHealth(): Promise<HealthResponse>                           // GET /api/system/health
fetchReadiness(): Promise<ReadinessResponse>                     // GET /api/system/health/ready
fetchGPUStats(): Promise<GPUStats>                               // GET /api/system/gpu
fetchGpuHistory(limit?: number): Promise<GPUStatsHistoryResponse> // GET /api/system/gpu/history
fetchConfig(): Promise<SystemConfig>                             // GET /api/system/config
updateConfig(data: SystemConfigUpdate): Promise<SystemConfig>    // PATCH /api/system/config
fetchStats(): Promise<SystemStats>                               // GET /api/system/stats
triggerCleanup(): Promise<CleanupResponse>                       // POST /api/system/cleanup
previewCleanup(): Promise<CleanupResponse>                       // POST /api/system/cleanup?dry_run=true
fetchTelemetry(): Promise<TelemetryResponse>                     // GET /api/system/telemetry
fetchStorageStats(): Promise<StorageStatsResponse>               // GET /api/system/storage
```

### Event Endpoints

```typescript
fetchEvents(params?: EventsQueryParams): Promise<EventListResponse>   // GET /api/events
fetchEvent(id: number): Promise<Event>                                // GET /api/events/{id}
fetchEventStats(params?: EventStatsQueryParams): Promise<EventStatsResponse>  // GET /api/events/stats
updateEvent(id: number, data: EventUpdateData): Promise<Event>        // PATCH /api/events/{id}
bulkUpdateEvents(ids: number[], data: EventUpdateData): Promise<BulkUpdateResult>  // Parallel updates
```

**Query Parameters:**

```typescript
interface EventsQueryParams {
  camera_id?: string;
  risk_level?: string;
  start_date?: string;
  end_date?: string;
  reviewed?: boolean;
  object_type?: string;
  limit?: number;
  offset?: number;
}
```

### Detection Endpoints

```typescript
fetchEventDetections(eventId: number, params?): Promise<DetectionListResponse>  // GET /api/events/{id}/detections
getDetectionImageUrl(detectionId: number): string           // /api/detections/{detectionId}/image
getDetectionVideoUrl(detectionId: number): string           // /api/detections/{detectionId}/video (with Range support)
getDetectionVideoThumbnailUrl(detectionId: number): string  // /api/detections/{detectionId}/video/thumbnail
```

### Logs Endpoints

```typescript
fetchLogStats(): Promise<LogStats>                   // GET /api/logs/stats
fetchLogs(params?: LogsQueryParams): Promise<LogsResponse>  // GET /api/logs
```

### DLQ (Dead Letter Queue) Endpoints

```typescript
type DLQQueueName = 'dlq:detection_queue' | 'dlq:analysis_queue';

fetchDlqStats(): Promise<DLQStatsResponse>                                // GET /api/dlq/stats
fetchDlqJobs(queueName: DLQQueueName, start?, limit?): Promise<DLQJobsResponse>  // GET /api/dlq/jobs/{queue}
requeueDlqJob(queueName: DLQQueueName): Promise<DLQRequeueResponse>       // POST /api/dlq/requeue/{queue}
requeueAllDlqJobs(queueName: DLQQueueName): Promise<DLQRequeueResponse>   // POST /api/dlq/requeue-all/{queue}
clearDlq(queueName: DLQQueueName): Promise<DLQClearResponse>              // DELETE /api/dlq/{queue}
```

### Export Endpoints

```typescript
exportEventsCSV(params?: ExportQueryParams): Promise<void>  // GET /api/events/export (triggers download)
```

### Search Endpoints

```typescript
searchEvents(params: EventSearchParams): Promise<SearchResponse>  // GET /api/events/search
```

**Search Parameters:**

```typescript
interface EventSearchParams {
  q: string; // Required search query
  camera_id?: string; // Filter by camera IDs (comma-separated)
  start_date?: string; // Filter by start date (ISO format)
  end_date?: string; // Filter by end date (ISO format)
  severity?: string; // Filter by risk levels (comma-separated: low,medium,high,critical)
  object_type?: string; // Filter by object types (comma-separated: person,vehicle,animal)
  reviewed?: boolean; // Filter by reviewed status
  limit?: number; // Max results (default 50)
  offset?: number; // Pagination offset
}
```

**Query Syntax (PostgreSQL full-text search):**

- Basic words: `"person vehicle"` (implicit AND)
- Phrase search: `'"suspicious person"'` (exact phrase)
- Boolean OR: `"person OR animal"`
- Boolean NOT: `"person NOT cat"`
- Boolean AND: `"person AND vehicle"` (explicit)

### Notification Endpoints

```typescript
fetchNotificationConfig(): Promise<NotificationConfig>  // GET /api/notification/config
testNotification(channel, recipients?, webhookUrl?): Promise<TestNotificationResult>  // POST /api/notification/test
```

**Types:**

```typescript
type NotificationChannel = 'email' | 'webhook' | 'push';

interface NotificationConfig {
  notification_enabled: boolean;
  email_configured: boolean;
  webhook_configured: boolean;
  push_configured: boolean;
  available_channels: NotificationChannel[];
  smtp_host: string | null;
  smtp_port: number | null;
  smtp_from_address: string | null;
  smtp_use_tls: boolean | null;
  default_webhook_url: string | null;
  webhook_timeout_seconds: number | null;
  default_email_recipients: string[];
}

interface TestNotificationResult {
  channel: NotificationChannel;
  success: boolean;
  error: string | null;
  message: string;
}
```

### Storage Types (Client-side)

```typescript
interface StorageCategoryStats {
  file_count: number;
  size_bytes: number;
}

interface StorageStatsResponse {
  disk_used_bytes: number;
  disk_total_bytes: number;
  disk_free_bytes: number;
  disk_usage_percent: number;
  thumbnails: StorageCategoryStats;
  images: StorageCategoryStats;
  clips: StorageCategoryStats;
  events_count: number;
  detections_count: number;
  gpu_stats_count: number;
  logs_count: number;
  timestamp: string;
}
```

### Media URL Helpers

```typescript
getMediaUrl(cameraId: string, filename: string): string    // /api/media/cameras/{cameraId}/{filename}
getThumbnailUrl(filename: string): string                   // /api/media/thumbnails/{filename}
```

## Error Handling

### `ApiError` Class

Custom error class for API failures:

```typescript
class ApiError extends Error {
  status: number; // HTTP status code (0 for network errors)
  data?: unknown; // Parsed error response body
  message: string; // Human-readable error message
}
```

**Usage:**

```typescript
try {
  const camera = await fetchCamera('invalid-id');
} catch (error) {
  if (error instanceof ApiError) {
    if (error.status === 404) {
      console.error('Camera not found');
    }
    console.error('Error data:', error.data);
  }
}
```

## Logger Service (`logger.ts`)

Singleton logger instance that captures and batches frontend logs for backend storage.

**Features:**

- Batches logs (default: 10 entries) before sending to reduce API calls
- Configurable flush interval (default: 5000ms)
- Captures unhandled errors via `window.onerror`
- Captures unhandled promise rejections via `window.onunhandledrejection`
- Automatically includes current URL in log entries
- Component-scoped loggers via `forComponent()`
- Queue size limit (100) prevents memory issues on network failures

**Configuration:**

```typescript
interface LoggerConfig {
  batchSize: number; // default: 10
  flushIntervalMs: number; // default: 5000
  endpoint: string; // default: "/api/logs/frontend"
  enabled: boolean; // default: true
}
```

**Methods:**

```typescript
logger.debug(message, extra?)     // DEBUG level log
logger.info(message, extra?)      // INFO level log
logger.warn(message, extra?)      // WARNING level log
logger.error(message, extra?)     // ERROR level log
logger.event(eventName, extra?)   // User event (INFO level, component: "user_event")
logger.apiError(endpoint, status, message)  // API error logging
logger.forComponent(name)         // Create scoped logger
logger.flush()                    // Manual flush
logger.destroy()                  // Cleanup (clears interval, flushes)
```

**ComponentLogger:**

```typescript
const log = logger.forComponent('EventTimeline');
log.debug('Rendering events', { count: events.length });
log.error('Failed to fetch events');
```

## Authentication

When `VITE_API_KEY` is set:

- REST requests include `X-API-Key` header
- WebSocket URLs include `api_key` query parameter

## Testing

`api.test.ts` provides comprehensive coverage:

- Successful API calls with response parsing
- Error handling (4xx, 5xx responses)
- Network errors (status code 0)
- 204 No Content responses
- Query parameter handling
- Request body serialization
- Bulk update operations
- WebSocket URL construction

`logger.test.ts` covers:

- Log batching behavior
- Flush timing
- Error capture handlers
- Component-scoped logging

## Usage Examples

### Fetching with Filters

```typescript
const response = await fetchEvents({
  risk_level: 'high',
  camera_id: 'cam_123',
  reviewed: false,
  limit: 20,
});
```

### Bulk Operations

```typescript
const result = await bulkUpdateEvents([1, 2, 3], { reviewed: true });
console.log(\`Updated: \${result.successful.length}, Failed: \${result.failed.length}\`);
```

### Export CSV

```typescript
await exportEventsCSV({
  risk_level: 'high',
  start_date: '2024-01-01',
});
// Triggers browser download
```

### DLQ Management

```typescript
const stats = await fetchDlqStats();
if (stats.total > 0) {
  const jobs = await fetchDlqJobs('dlq:detection_queue');
  // Inspect failed jobs, then requeue
  await requeueAllDlqJobs('dlq:detection_queue');
}
```

## Audit API Client (`auditApi.ts`)

Specialized API client for AI pipeline audit endpoints. Provides typed fetch wrappers for:

- Event audit data (model contributions, confidence scores)
- Audit statistics and summaries
- Model leaderboards (accuracy, usage rankings)
- AI recommendation endpoints

**Key Types:**

```typescript
interface ModelContributions {
  rtdetr: boolean;
  florence: boolean;
  clip: boolean;
  violence: boolean;
  clothing: boolean;
  vehicle: boolean;
  pet: boolean;
  weather: boolean;
}

// Custom error class
class AuditApiError extends Error {
  status: number;
  data?: unknown;
}
```

## Prometheus Metrics Parser (`metricsParser.ts`)

Parses Prometheus text exposition format for AI performance metrics from `/api/metrics`.

**Features:**

- Parses gauge and histogram metrics
- Extracts labels and values
- Calculates percentiles from histogram buckets (p50, p95, p99)
- Computes average latency from histogram sum/count

**Key Types:**

```typescript
interface ParsedMetric {
  name: string;
  labels: Record<string, string>;
  value: number;
}

interface AILatencyMetrics {
  avg_ms: number | null;
  p50_ms: number | null;
  p95_ms: number | null;
  p99_ms: number | null;
}
```

## TanStack Query Configuration (`queryClient.ts`)

Provides centralized server-state management for the frontend using TanStack Query (React Query).

### Features

- **QueryClient Configuration**: Sensible defaults for stale time, retry logic, and caching
- **Query Key Factories**: Type-safe, hierarchical cache key management
- **Stale Time Constants**: Different freshness requirements for different data types

### Stale Time Constants

```typescript
DEFAULT_STALE_TIME = 30 * 1000;   // 30 seconds - events, cameras
REALTIME_STALE_TIME = 5 * 1000;   // 5 seconds - health, GPU metrics
STATIC_STALE_TIME = 5 * 60 * 1000; // 5 minutes - config, severity
```

### Query Key Factories

Hierarchical key structure enables granular cache invalidation:

```typescript
// Examples
queryKeys.cameras.all           // ['cameras'] - invalidate all camera queries
queryKeys.cameras.list()        // ['cameras', 'list']
queryKeys.cameras.detail(id)    // ['cameras', 'detail', 'cam-1']
queryKeys.events.list(filters)  // ['events', 'list', { camera_id: 'cam-1' }]
queryKeys.system.health         // ['system', 'health']
```

### Usage

```typescript
import { queryClient, queryKeys } from './services/queryClient';
import { useQueryClient } from '@tanstack/react-query';

// In a component
const queryClient = useQueryClient();

// Invalidate all camera data
queryClient.invalidateQueries({ queryKey: queryKeys.cameras.all });

// Invalidate specific camera
queryClient.invalidateQueries({ queryKey: queryKeys.cameras.detail('cam-1') });
```

### App Integration

The QueryClientProvider is configured in `App.tsx`:

```tsx
import { QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { queryClient } from './services/queryClient';

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      {/* App content */}
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  );
}
```

## A/B Test Service (`abTestService.ts`)

Service for running A/B tests comparing original and modified prompts against events. Used by the Prompt Playground feature.

**Features:**

- Fetch random events for A/B testing
- Test prompts against single events
- Batch A/B testing with configurable sample sizes
- Model configuration support (model name, temperature, maxTokens)
- Detailed comparison results with statistical metrics

**Key Types:**

```typescript
interface ModelConfig {
  model: string;
  temperature: number;
  maxTokens: number;
}

interface EventSummary {
  id: number;
  timestamp: string;
  cameraName: string;
  detectionCount: number;
}

interface TestPromptResponse {
  riskScore: number;
  riskLevel: string;
  reasoning: string;
  responseTime: number;
}

interface ABTestComparison {
  eventId: number;
  original: TestPromptResponse;
  modified: TestPromptResponse;
  scoreDelta: number;
  levelChanged: boolean;
}

interface ABTestResult {
  comparisons: ABTestComparison[];
  summary: ABTestSummary;
}
```

**Key Functions:**

```typescript
// Fetch random events for testing
fetchRandomEvents(limit?: number): Promise<EventSummary[]>

// Test prompt against single event
testPrompt(eventId: number, prompt: string, modelConfig: ModelConfig): Promise<TestPromptResponse>

// Run A/B test comparing two prompts
runABTest(params: ABTestParams): Promise<ABTestResult>
```

## Prompt Management API (`promptManagementApi.ts`)

Specialized API client for prompt management endpoints including version history, CRUD operations, testing, and import/export.

**Features:**

- Fetch all prompts for all AI models
- View prompt version history with pagination
- Restore previous prompt versions
- Update prompts with validation
- Test prompt changes without saving
- Export prompts to JSON
- Import prompts with preview and validation

**Key Types:**

```typescript
type AIModelEnum = 'nemotron' | 'rt-detr' | 'florence' | 'clip';

interface ModelPromptConfig {
  model: AIModelEnum;
  prompt: string;
  version: number;
  updated_at: string;
}

interface PromptHistoryEntry {
  version: number;
  prompt: string;
  updated_at: string;
  updated_by: string | null;
}

interface PromptsExportResponse {
  version: string;
  exported_at: string;
  prompts: Record<AIModelEnum, string>;
}

interface PromptsImportPreviewResponse {
  valid: boolean;
  errors: string[];
  warnings: string[];
  models_to_update: AIModelEnum[];
  current_versions: Record<AIModelEnum, number>;
}
```

**Key Functions:**

```typescript
// Fetch all prompts
fetchAllPrompts(): Promise<AllPromptsResponse>

// Get prompt history
fetchPromptHistory(model: AIModelEnum, limit?: number, offset?: number): Promise<PromptHistoryResponse>

// Update prompt
updatePrompt(model: AIModelEnum, prompt: string): Promise<ModelPromptConfig>

// Restore previous version
restorePromptVersion(model: AIModelEnum, version: number): Promise<PromptRestoreResponse>

// Test prompt without saving
testPrompt(request: PromptTestRequest): Promise<PromptTestResult>

// Export all prompts
exportPrompts(): Promise<PromptsExportResponse>

// Preview import
previewImport(data: PromptsImportPreviewRequest): Promise<PromptsImportPreviewResponse>

// Import prompts
importPrompts(data: PromptsImportRequest): Promise<PromptsImportResponse>
```

**Custom Error Class:**

```typescript
class PromptApiError extends Error {
  status: number;
  data?: unknown;
}
```

## HTTP Interceptors (`interceptors.ts`)

Request and response interceptors for the API client. Provides hooks for logging, authentication, error handling, and request/response transformation.

**Features:**

- Pre-request hooks (add headers, log requests, modify config)
- Post-response hooks (transform data, log responses)
- Error handling hooks (retry logic, toast notifications)
- Request/response logging
- Authentication token injection
- Rate limiting detection

**Key Types:**

```typescript
interface RequestInterceptor {
  (config: RequestInit, url: string): RequestInit | Promise<RequestInit>;
}

interface ResponseInterceptor {
  <T>(response: Response, data: T): T | Promise<T>;
}

interface ErrorInterceptor {
  (error: ApiError): void | Promise<void>;
}
```

## Notes

- All functions are async and return Promises
- Type safety enforced through auto-generated TypeScript interfaces
- Relative URLs used by default (works with proxied development setup)
- FastAPI `detail` field automatically extracted from error responses
- Logger automatically logs to console in all environments
- Logger queue is preserved on flush failures (up to 100 entries)
- TanStack Query DevTools available in development mode (bottom-right corner)
- A/B testing service supports batch testing with configurable sample sizes
- Prompt management API includes version control with rollback capability
- All new services use custom error classes for type-safe error handling

## Entry Points

For AI agents exploring this codebase:

1. **Start with `api.ts`** - Main API client with all REST endpoint methods
2. **Type imports**: Types are re-exported from `../types/generated/`
3. **WebSocket URLs**: Use `buildWebSocketUrl()` for WebSocket connections
4. **Error handling**: All API calls can throw `ApiError` with status and data
5. **Logging**: Import `logger` singleton for frontend logging to backend
6. **A/B testing**: Use `abTestService.ts` for prompt playground A/B tests
7. **Prompt management**: Use `promptManagementApi.ts` for prompt CRUD and versioning
8. **Audit data**: Use `auditApi.ts` for AI pipeline audit and model contribution data
