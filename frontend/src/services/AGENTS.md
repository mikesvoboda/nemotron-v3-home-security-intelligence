# Frontend Services Directory

## Purpose

REST API client and logging service for interacting with the FastAPI backend. Provides typed fetch wrappers for all HTTP endpoints and centralized error logging.

## Key Files

### `api.ts`

Complete API client with type-safe methods for cameras, events, detections, system info, logs, and media URLs.

### `logger.ts`

Frontend logging service that captures errors and events, batches them, and sends to the backend for storage.

## API Client Structure

### Configuration

- **Base URL**: Configurable via `VITE_API_BASE_URL` environment variable (defaults to empty string for relative paths)
- **Headers**: Automatic `Content-Type: application/json` header injection
- **Error Handling**: Custom `ApiError` class with status codes and error data

### Core Functions

#### `fetchApi<T>(endpoint, options?)`

Internal helper that wraps `fetch` with:

- Automatic JSON serialization/deserialization
- Error response parsing (extracts `detail` field from FastAPI responses)
- Type-safe return values
- Network error handling (status code 0)

#### `handleResponse<T>(response)`

Internal helper that:

- Throws `ApiError` for non-OK responses
- Handles 204 No Content responses (returns `undefined`)
- Parses JSON responses with error handling

### Camera Endpoints

```typescript
fetchCameras(): Promise<Camera[]>                          // GET /api/cameras
fetchCamera(id: string): Promise<Camera>                   // GET /api/cameras/{id}
createCamera(data: CameraCreate): Promise<Camera>          // POST /api/cameras
updateCamera(id: string, data: CameraUpdate): Promise<Camera>  // PATCH /api/cameras/{id}
deleteCamera(id: string): Promise<void>                    // DELETE /api/cameras/{id}
```

**Types:**

```typescript
interface Camera {
  id: string;
  name: string;
  folder_path: string;
  status: string;
  created_at: string;
  last_seen_at: string | null;
}

interface CameraCreate {
  name: string;
  folder_path: string;
  status?: string;
}

interface CameraUpdate {
  name?: string;
  folder_path?: string;
  status?: string;
}
```

### System Endpoints

```typescript
fetchHealth(): Promise<HealthResponse>             // GET /api/system/health
fetchGPUStats(): Promise<GPUStats>                // GET /api/system/gpu
fetchConfig(): Promise<SystemConfig>              // GET /api/system/config
updateConfig(data: SystemConfigUpdate): Promise<SystemConfig>  // PATCH /api/system/config
fetchStats(): Promise<SystemStats>                // GET /api/system/stats
```

**Types:**

```typescript
interface HealthResponse {
  status: string;
  services: Record;
  timestamp: string;
}

interface GPUStats {
  utilization: number | null;
  memory_used: number | null;
  memory_total: number | null;
  temperature: number | null;
  inference_fps: number | null;
}

interface SystemConfig {
  app_name: string;
  version: string;
  retention_days: number;
  batch_window_seconds: number;
  batch_idle_timeout_seconds: number;
  detection_confidence_threshold: number;
}

interface SystemConfigUpdate {
  retention_days?: number;
  batch_window_seconds?: number;
  batch_idle_timeout_seconds?: number;
  detection_confidence_threshold?: number;
}

interface SystemStats {
  total_cameras: number;
  total_events: number;
  total_detections: number;
  uptime_seconds: number;
}
```

### Event Endpoints

```typescript
fetchEvents(params?: EventsQueryParams): Promise<EventListResponse>  // GET /api/events
fetchEvent(id: number): Promise<Event>                               // GET /api/events/{id}
updateEvent(id: number, data: EventUpdateData): Promise<Event>       // PATCH /api/events/{id}
bulkUpdateEvents(ids: number[], data: EventUpdateData): Promise<BulkUpdateResult>  // Parallel updates
fetchEventDetections(eventId: number, params?): Promise<DetectionListResponse>  // GET /api/events/{id}/detections
```

**Types:**

```typescript
interface Event {
  id: number;
  camera_id: string;
  started_at: string;
  ended_at: string | null;
  risk_score: number | null;
  risk_level: string | null;
  summary: string | null;
  reviewed: boolean;
  notes: string | null;
  detection_count: number;
}

interface EventListResponse {
  events: Event[];
  count: number;
  limit: number;
  offset: number;
}

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

interface EventUpdateData {
  reviewed?: boolean;
  notes?: string | null;
}

interface BulkUpdateResult {
  successful: number[];
  failed: Array;
}
```

### Detection Endpoints

```typescript
fetchEventDetections(eventId: number, params?): Promise<DetectionListResponse>
getDetectionImageUrl(detectionId: number): string  // /api/detections/{id}/image
```

**Types:**

```typescript
interface Detection {
  id: number;
  camera_id: string;
  file_path: string;
  file_type: string | null;
  detected_at: string;
  object_type: string | null;
  confidence: number | null;
  bbox_x: number | null;
  bbox_y: number | null;
  bbox_width: number | null;
  bbox_height: number | null;
  thumbnail_path: string | null;
}

interface DetectionListResponse {
  detections: Detection[];
  count: number;
  limit: number;
  offset: number;
}
```

### Logs Endpoints

```typescript
fetchLogStats(): Promise<LogStats>                 // GET /api/logs/stats
fetchLogs(params?: LogsQueryParams): Promise<LogsResponse>  // GET /api/logs
```

**Types:**

```typescript
interface LogStats {
  total_today: number;
  errors_today: number;
  warnings_today: number;
  by_component: Record;
  by_level: Record;
  top_component: string | null;
}

interface LogEntry {
  id: number;
  timestamp: string;
  level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL';
  component: string;
  message: string;
  camera_id?: string | null;
  event_id?: number | null;
  request_id?: string | null;
  detection_id?: number | null;
  duration_ms?: number | null;
  extra?: Record | null;
  source: string;
  user_agent?: string | null;
}

interface LogsQueryParams {
  level?: string;
  component?: string;
  camera_id?: string;
  source?: string;
  search?: string;
  start_date?: string;
  end_date?: string;
  limit?: number;
  offset?: number;
}
```

### Media URL Helpers

```typescript
getMediaUrl(cameraId: string, filename: string): string    // /api/media/cameras/{cameraId}/{filename}
getThumbnailUrl(filename: string): string                   // /api/media/thumbnails/{filename}
getDetectionImageUrl(detectionId: number): string          // /api/detections/{detectionId}/image
```

These return full URLs for use in `<img>` src attributes.

## Error Handling

### `ApiError` Class

Custom error class extending `Error`:

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
  const cameras = await fetchCameras();
} catch (error) {
  if (error instanceof ApiError) {
    console.error(`API Error ${error.status}: ${error.message}`);
    console.error('Error data:', error.data);
  }
}
```

## Logger Service

### `logger.ts`

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

**Usage:**

```typescript
import { logger } from '@/services/logger';

// Direct logging
logger.info('User clicked button', { buttonId: 'submit' });
logger.error('Failed to load data', { error: err.message });

// Component-scoped logger
const log = logger.forComponent('EventTimeline');
log.debug('Rendering events', { count: events.length });
log.error('Failed to fetch events');

// API error logging
logger.apiError('/api/events', 500, 'Internal Server Error');

// User event tracking
logger.event('filter_applied', { filter: 'high_risk' });
```

## Testing

### `api.test.ts`

Comprehensive test coverage including:

- Successful API calls with response parsing
- Error handling (4xx, 5xx responses)
- Network errors
- 204 No Content responses
- Query parameter handling
- Request body serialization
- Bulk update operations

**Test Utilities:**

- `vi.fn()` for mocking `fetch`
- Mock Response objects
- Type validation

## Usage Examples

### Fetching Cameras

```typescript
import { fetchCameras } from '@/services/api';

const cameras = await fetchCameras();
// cameras: Camera[]
```

### Creating a Camera

```typescript
import { createCamera } from '@/services/api';

const newCamera = await createCamera({
  name: 'Front Door',
  folder_path: '/export/foscam/front_door',
  status: 'active',
});
```

### Fetching Events with Filtering

```typescript
import { fetchEvents } from '@/services/api';

const response = await fetchEvents({
  risk_level: 'high',
  camera_id: 'cam_123',
  reviewed: false,
  limit: 20,
  offset: 0,
});
// response: { events: Event[], count: number, limit: number, offset: number }
```

### Updating Event with Notes

```typescript
import { updateEvent } from '@/services/api';

const updatedEvent = await updateEvent(42, {
  reviewed: true,
  notes: 'False positive - neighbor walking dog',
});
```

### Bulk Updating Events

```typescript
import { bulkUpdateEvents } from '@/services/api';

const result = await bulkUpdateEvents([1, 2, 3], { reviewed: true });
console.log(`Updated: ${result.successful.length}, Failed: ${result.failed.length}`);
```

### Handling Errors

```typescript
import { fetchCamera, ApiError } from '@/services/api';

try {
  const camera = await fetchCamera('invalid-id');
} catch (error) {
  if (error instanceof ApiError && error.status === 404) {
    console.error('Camera not found');
  }
}
```

## Notes

- All functions are async and return Promises
- Type safety enforced through TypeScript interfaces
- Environment variable `VITE_API_BASE_URL` allows flexible deployment
- Relative URLs used by default (works with proxied development setup)
- FastAPI `detail` field automatically extracted from error responses
- Logger automatically logs to console in all environments
- Logger queue is preserved on flush failures (up to 100 entries)
