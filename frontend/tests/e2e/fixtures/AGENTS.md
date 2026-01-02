# E2E Test Fixtures Directory

## Purpose

Centralized test fixtures for E2E tests including mock data, API mocking utilities, and a custom Playwright test function with auto-mocking. This directory eliminates duplication of mock setup code across test specs.

## Key Files

| File                | Purpose                                        |
| ------------------- | ---------------------------------------------- |
| `index.ts`          | Central exports and custom test fixture        |
| `api-mocks.ts`      | API route interception and mock response setup |
| `test-data.ts`      | Mock data for cameras, events, GPU, logs, etc. |
| `websocket-mock.ts` | WebSocket simulation helpers                   |

## index.ts - Custom Test Fixture

Exports a custom Playwright `test` function with auto-mocking:

```typescript
import { test, expect } from '../fixtures';

// API mocks are automatically set up before each test
test('my test', async ({ page }) => {
  await page.goto('/');
  // All API calls are mocked!
});

// Override mock config for specific tests:
import { errorMockConfig } from '../fixtures';
test.use({ mockConfig: errorMockConfig });

test('error handling', async ({ page }) => {
  await page.goto('/');
  // Uses error mock configuration
});
```

**Exports:**

- `test` - Custom Playwright test function with auto-mocking
- `expect` - Re-exported Playwright expect
- All exports from `test-data.ts`, `api-mocks.ts`, `websocket-mock.ts`

## api-mocks.ts - API Mocking

### Mock Configurations

| Config                | Purpose                                     |
| --------------------- | ------------------------------------------- |
| `defaultMockConfig`   | Normal operation with healthy data          |
| `emptyMockConfig`     | Empty state testing (no events, no cameras) |
| `errorMockConfig`     | API failure scenarios (500 errors)          |
| `highAlertMockConfig` | High-risk state with many alerts            |

### ApiMockConfig Interface

```typescript
interface ApiMockConfig {
  // Camera data
  cameras?: Camera[];
  camerasError?: boolean;

  // Event data
  events?: Event[];
  eventsError?: boolean;
  eventStats?: EventStats;

  // GPU data
  gpuStats?: GPUStats;
  gpuError?: boolean;
  gpuHistory?: GPUHistorySample[];

  // System health
  systemHealth?: SystemHealth;
  systemHealthError?: boolean;

  // Logs
  logs?: Log[];
  logStats?: LogStats;
  logsError?: boolean;

  // Audit logs
  auditLogs?: AuditLog[];
  auditStats?: AuditStats;
  auditError?: boolean;

  // Telemetry
  telemetry?: Telemetry;
  telemetryError?: boolean;

  // WebSocket behavior
  wsConnectionFail?: boolean;
}
```

### setupApiMocks Function

```typescript
async function setupApiMocks(page: Page, config?: ApiMockConfig): Promise;
```

Sets up all API route interceptions. Call in `beforeEach` or use the auto-mocking fixture.

**Important**: More specific routes must be registered BEFORE more general routes. The function handles this internally.

### Helper Functions

| Function       | Purpose                                  |
| -------------- | ---------------------------------------- |
| `interceptApi` | Intercept a specific API response        |
| `withDelay`    | Create delayed response (loading states) |
| `withError`    | Create error response                    |

## test-data.ts - Mock Data

### Camera Data

```typescript
export const mockCameras = {
  frontDoor: { id: 'cam-1', name: 'Front Door', status: 'online', ... },
  backYard: { id: 'cam-2', name: 'Back Yard', status: 'online', ... },
  garage: { id: 'cam-3', name: 'Garage', status: 'offline', ... },
  driveway: { id: 'cam-4', name: 'Driveway', status: 'online', ... },
};

export const allCameras = Object.values(mockCameras);
```

### Event Data

```typescript
export const mockEvents = {
  lowRisk: { risk_score: 25, risk_level: 'low', ... },
  mediumRisk: { risk_score: 55, risk_level: 'medium', ... },
  highRisk: { risk_score: 78, risk_level: 'high', ... },
  criticalRisk: { risk_score: 92, risk_level: 'critical', ... },
};

export const allEvents = Object.values(mockEvents);
```

### GPU Stats

```typescript
export const mockGPUStats = {
  healthy: { utilization: 45, temperature: 52, ... },
  highLoad: { utilization: 95, temperature: 82, ... },
  idle: { utilization: 5, temperature: 38, ... },
};

export function generateGPUHistory(count: number): GPUHistorySample[]
```

### System Health

```typescript
export const mockSystemHealth = {
  healthy: { status: 'healthy', services: { ... } },
  degraded: { status: 'degraded', services: { ... } },
  unhealthy: { status: 'unhealthy', services: { ... } },
};
```

### Additional Mock Data

- `mockSystemStats` - System statistics (normal, busy, empty)
- `mockSystemConfig` - System configuration
- `mockEventStats` - Event statistics by risk level
- `mockLogs` - Sample log entries
- `mockLogStats` - Log statistics by level
- `mockAuditLogs` - Audit log entries
- `mockAuditStats` - Audit statistics
- `mockTelemetry` - Pipeline telemetry data
- `transparentPngBase64` - 1x1 transparent PNG for camera snapshots

## websocket-mock.ts - WebSocket Simulation

Since Playwright cannot directly mock WebSocket connections, this module provides simulation utilities:

### Functions

| Function                     | Purpose                           |
| ---------------------------- | --------------------------------- |
| `setupWebSocketMock`         | Block/configure WebSocket upgrade |
| `createWebSocketMessage`     | Create simulated WS message       |
| `simulateNewEvent`           | Simulate event creation           |
| `simulateCameraStatusChange` | Simulate camera status update     |
| `simulateGpuUpdate`          | Simulate GPU stats update         |
| `simulateSystemAlert`        | Simulate system alert             |
| `isShowingDisconnectedState` | Check for disconnection indicator |
| `waitForConnectionAttempt`   | Wait for WS connection attempt    |

### WebSocket Event Types

```typescript
type WebSocketEventType =
  | 'event_created'
  | 'event_updated'
  | 'camera_status'
  | 'gpu_update'
  | 'system_alert'
  | 'performance_update';
```

### Usage Example

```typescript
import { simulateNewEvent, setupWebSocketMock } from '../fixtures';

test('handles real-time events', async ({ page }) => {
  await setupWebSocketMock(page, { blockConnections: false });
  await page.goto('/');

  // Simulate a new event
  await simulateNewEvent(page, {
    id: 100,
    camera_id: 'cam-1',
    camera_name: 'Front Door',
    risk_score: 75,
    risk_level: 'high',
    summary: 'Test event',
  });

  // Verify UI updated
  await expect(page.getByText('Test event')).toBeVisible();
});
```

## Usage Patterns

### Basic Test with Auto-Mocking

```typescript
import { test, expect } from '../fixtures';

test('dashboard loads', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: /Dashboard/i })).toBeVisible();
});
```

### Test with Custom Mock Config

```typescript
import { test, expect, emptyMockConfig } from '../fixtures';

test.describe('empty states', () => {
  test.use({ mockConfig: emptyMockConfig });

  test('shows no events message', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByText(/No activity/i)).toBeVisible();
  });
});
```

### Manual Mock Setup

```typescript
import { test, setupApiMocks, defaultMockConfig } from '../fixtures';

test('with manual setup', async ({ page }) => {
  await setupApiMocks(page, {
    ...defaultMockConfig,
    gpuStats: { utilization: 99, temperature: 85, ... },
  });
  await page.goto('/system');
});
```

## Notes for AI Agents

- Always import from `fixtures/index.ts` (via `../fixtures`)
- Use the `test` export for auto-mocking, or `setupApiMocks` for manual control
- WebSocket is blocked by default (`wsConnectionFail: true`)
- Mock data matches backend API response schemas
- Route registration order is handled automatically by `setupApiMocks`
- Use `withDelay` to test loading states
- Use `withError` to test error states

## Entry Points

1. **Auto-Mocking**: Import `test` from this directory
2. **Mock Configs**: `defaultMockConfig`, `emptyMockConfig`, `errorMockConfig`
3. **Mock Data**: `mockCameras`, `mockEvents`, `mockGPUStats`, etc.
4. **WebSocket**: `simulateNewEvent`, `simulateCameraStatusChange`, etc.
