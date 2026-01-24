# Test Factories Directory - AI Agent Guide

## Purpose

This directory contains factory functions for creating mock test data. Factories provide a consistent, type-safe way to create test entities with sensible defaults while allowing specific fields to be overridden for individual test cases.

## Key Files

| File            | Purpose                                      | Lines |
| --------------- | -------------------------------------------- | ----- |
| `index.ts`      | All factory functions and utilities          | ~305  |
| `index.test.ts` | Tests for factory functions                  | ~367  |

## Key Exports

### Counter Utilities

| Export          | Signature                  | Description                           |
| --------------- | -------------------------- | ------------------------------------- |
| `uniqueId`      | `(prefix?) => string`      | Generate unique ID (e.g., `camera-1`) |
| `resetCounter`  | `() => void`               | Reset counter to 0 (for test setup)   |

### Entity Factories

| Export                  | Entity Type       | Default Values                         |
| ----------------------- | ----------------- | -------------------------------------- |
| `cameraFactory`         | `Camera`          | name: "Test Camera", status: "online"  |
| `eventFactory`          | `Event`           | risk_score: 50, risk_level: "medium"   |
| `detectionFactory`      | `Detection`       | object_type: "person", confidence: 0.85|
| `gpuStatsFactory`       | `GPUStats`        | utilization: 45.5%, temp: 65C          |
| `healthResponseFactory` | `HealthResponse`  | status: "healthy", all services healthy|
| `systemStatsFactory`    | `SystemStats`     | 4 cameras, 150 events, 450 detections  |

### List Factories

| Export                  | Signature                                    |
| ----------------------- | -------------------------------------------- |
| `cameraFactoryList`     | `(count, overrideFn?) => Camera[]`           |
| `eventFactoryList`      | `(count, overrideFn?) => Event[]`            |
| `detectionFactoryList`  | `(count, overrideFn?) => Detection[]`        |
| `gpuStatsFactoryList`   | `(count, overrideFn?) => GPUStats[]`         |

## Usage Patterns

### Basic Factory Usage

```typescript
import { cameraFactory, eventFactory } from '@/test/factories';

// Create with defaults
const camera = cameraFactory();
expect(camera.status).toBe('online');

// Override specific fields
const offlineCamera = cameraFactory({
  name: 'Back Door',
  status: 'offline',
});
```

### Creating Multiple Entities

```typescript
import { cameraFactoryList } from '@/test/factories';

// Create 3 cameras with defaults
const cameras = cameraFactoryList(3);
expect(cameras).toHaveLength(3);

// Customize each camera based on index
const customCameras = cameraFactoryList(3, (i) => ({
  name: `Camera ${i + 1}`,
  id: `cam-${i + 1}`,
}));
```

### Creating Related Entities

```typescript
import { cameraFactory, eventFactory, detectionFactory } from '@/test/factories';

// Create a camera
const camera = cameraFactory({ id: 'front-door' });

// Create events for that camera
const event = eventFactory({
  camera_id: camera.id,
  risk_score: 85,
  risk_level: 'high',
});

// Create detections for the event
const detection = detectionFactory({
  camera_id: camera.id,
  object_type: 'person',
  confidence: 0.95,
});
```

### Test Setup with Counter Reset

```typescript
import { describe, beforeEach } from 'vitest';
import { resetCounter, cameraFactory } from '@/test/factories';

describe('MyComponent', () => {
  beforeEach(() => {
    resetCounter(); // IDs start from 1 in each test
  });

  it('creates predictable IDs', () => {
    const camera1 = cameraFactory();
    const camera2 = cameraFactory();

    expect(camera1.id).toBe('camera-1');
    expect(camera2.id).toBe('camera-2');
  });
});
```

### Testing with Mock Data

```typescript
import { render, screen } from '@testing-library/react';
import { cameraFactoryList } from '@/test/factories';
import { CameraList } from '@/components/CameraList';

it('renders camera list', () => {
  const cameras = cameraFactoryList(3, (i) => ({
    name: `Camera ${i}`,
    status: i === 1 ? 'offline' : 'online',
  }));

  render(<CameraList cameras={cameras} />);

  expect(screen.getByText('Camera 0')).toBeInTheDocument();
  expect(screen.getByText('offline')).toBeInTheDocument();
});
```

### Testing Health Status

```typescript
import { healthResponseFactory } from '@/test/factories';

it('handles degraded health status', () => {
  const health = healthResponseFactory({
    status: 'degraded',
    services: {
      database: { status: 'healthy', message: 'OK' },
      redis: { status: 'unhealthy', message: 'Connection failed' },
      ai: { status: 'healthy', message: 'OK' },
    },
  });

  expect(health.services.redis.status).toBe('unhealthy');
});
```

## Factory Default Values

### cameraFactory

```typescript
{
  id: uniqueId('camera'),        // 'camera-1', 'camera-2', etc.
  name: 'Test Camera',
  folder_path: '/export/foscam/test_camera',
  status: 'online',
  created_at: '2024-01-01T00:00:00Z',
  last_seen_at: new Date().toISOString(),
}
```

### eventFactory

```typescript
{
  id: counter,                    // Auto-incrementing number
  camera_id: uniqueId('camera'),
  started_at: new Date(Date.now() - 60000).toISOString(),  // 1 minute ago
  ended_at: new Date().toISOString(),
  risk_score: 50,
  risk_level: 'medium',
  summary: 'Test event summary',
  reviewed: false,
  detection_count: 1,
  notes: null,
}
```

### detectionFactory

```typescript
{
  id: counter++,                  // Auto-incrementing number
  camera_id: uniqueId('camera'),
  detected_at: new Date().toISOString(),
  object_type: 'person',
  confidence: 0.85,
  bbox_x: 100,
  bbox_y: 100,
  bbox_width: 200,
  bbox_height: 200,
  file_path: '/path/to/image.jpg',
  media_type: 'image',
}
```

### gpuStatsFactory

```typescript
{
  utilization: 45.5,
  memory_used: 8192,
  memory_total: 24576,
  temperature: 65,
  power_usage: 150,
  gpu_name: 'NVIDIA RTX A5500',
  inference_fps: 30,
}
```

### healthResponseFactory

```typescript
{
  status: 'healthy',
  services: {
    database: { status: 'healthy', message: 'Database operational' },
    redis: { status: 'healthy', message: 'Redis connected' },
    ai: { status: 'healthy', message: 'AI services operational' },
  },
  timestamp: new Date().toISOString(),
}
```

### systemStatsFactory

```typescript
{
  total_cameras: 4,
  total_events: 150,
  total_detections: 450,
  uptime_seconds: 86400,
}
```

## Types

Factories use types from the API service:

```typescript
import type {
  Camera,
  Event,
  Detection,
  GPUStats,
  HealthResponse,
  SystemStats,
} from '@/services/api';
```

## Notes for AI Agents

- **Always reset counter in beforeEach**: Ensures predictable IDs across tests
- **Use overrideFn for lists**: Customize each item based on index
- **Create related entities explicitly**: Link camera_id, event_id manually
- **Override only what you need**: Let defaults handle everything else
- **Use realistic values**: Defaults match production data patterns
- **Timestamps are dynamic**: `last_seen_at` and `detected_at` use current time
- **Confidence is 0-1**: Not 0-100 (matches API convention)
- **Risk score is 0-100**: Not 0-1 (matches API convention)
