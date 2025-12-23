# Frontend Services Directory

## Purpose

REST API client for interacting with the FastAPI backend. Provides typed fetch wrappers for all HTTP endpoints.

## Key Files

### `api.ts`

Complete API client with type-safe methods for cameras, system info, and media URLs.

## API Client Structure

### Configuration

- **Base URL**: Configurable via `VITE_API_BASE_URL` environment variable (defaults to relative path)
- **Headers**: Automatic `Content-Type: application/json` header injection
- **Error Handling**: Custom `ApiError` class with status codes and error data

### Core Functions

#### `fetchApi<T>(endpoint, options?)`

Internal helper that wraps `fetch` with:

- Automatic JSON serialization/deserialization
- Error response parsing (extracts `detail` field from FastAPI responses)
- Type-safe return values
- Network error handling

#### `handleResponse<T>(response)`

Internal helper that:

- Throws `ApiError` for non-OK responses
- Handles 204 No Content responses
- Parses JSON responses with error handling

### Camera Endpoints

```typescript
fetchCameras(): Promise<Camera[]>              // GET /api/cameras
fetchCamera(id: string): Promise<Camera>       // GET /api/cameras/{id}
createCamera(data: CameraCreate): Promise<Camera>  // POST /api/cameras
updateCamera(id: string, data: CameraUpdate): Promise<Camera>  // PATCH /api/cameras/{id}
deleteCamera(id: string): Promise<void>        // DELETE /api/cameras/{id}
```

**Types:**

- `Camera`: Full camera object with `id`, `name`, `folder_path`, `status`, `created_at`, `last_seen_at`
- `CameraCreate`: Fields for creating a camera
- `CameraUpdate`: Partial fields for updating a camera

### System Endpoints

```typescript
fetchHealth(): Promise<HealthResponse>         // GET /api/system/health
fetchGPUStats(): Promise<GPUStats>            // GET /api/system/gpu
fetchConfig(): Promise<SystemConfig>          // GET /api/system/config
fetchStats(): Promise<SystemStats>            // GET /api/system/stats
```

**Types:**

- `HealthResponse`: System health with service status map
- `GPUStats`: NVIDIA GPU metrics (utilization, memory, temperature, FPS)
- `SystemConfig`: App configuration (name, version, retention, batch settings)
- `SystemStats`: Aggregate statistics (cameras, events, detections, uptime)

### Media URL Helpers

```typescript
getMediaUrl(cameraId: string, filename: string): string    // /api/media/cameras/{cameraId}/{filename}
getThumbnailUrl(filename: string): string                   // /api/media/thumbnails/{filename}
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

## Testing

### `api.test.ts`

Comprehensive test coverage including:

- Successful API calls with response parsing
- Error handling (4xx, 5xx responses)
- Network errors
- 204 No Content responses
- Query parameter handling
- Request body serialization

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
