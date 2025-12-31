/**
 * Test Data Fixtures for E2E Tests
 *
 * Contains mock data for cameras, events, alerts, GPU stats, and other entities.
 * All data is designed to be consistent and reusable across test specs.
 */

// Camera Mock Data
export const mockCameras = {
  frontDoor: {
    id: 'cam-1',
    name: 'Front Door',
    folder_path: '/export/foscam/front_door',
    status: 'online',
    created_at: new Date().toISOString(),
    last_seen_at: new Date().toISOString(),
  },
  backYard: {
    id: 'cam-2',
    name: 'Back Yard',
    folder_path: '/export/foscam/back_yard',
    status: 'online',
    created_at: new Date().toISOString(),
    last_seen_at: new Date().toISOString(),
  },
  garage: {
    id: 'cam-3',
    name: 'Garage',
    folder_path: '/export/foscam/garage',
    status: 'offline',
    created_at: new Date().toISOString(),
    last_seen_at: new Date(Date.now() - 3600000).toISOString(),
  },
  driveway: {
    id: 'cam-4',
    name: 'Driveway',
    folder_path: '/export/foscam/driveway',
    status: 'online',
    created_at: new Date().toISOString(),
    last_seen_at: new Date().toISOString(),
  },
};

export const allCameras = Object.values(mockCameras);

// Event Mock Data
export const mockEvents = {
  lowRisk: {
    id: 1,
    camera_id: 'cam-1',
    camera_name: 'Front Door',
    timestamp: new Date().toISOString(),
    started_at: new Date().toISOString(),
    ended_at: new Date(Date.now() + 30000).toISOString(),
    risk_score: 25,
    risk_level: 'low',
    summary: 'Person detected at front door - appears to be delivery',
    reviewed: false,
    notes: '',
  },
  mediumRisk: {
    id: 2,
    camera_id: 'cam-2',
    camera_name: 'Back Yard',
    timestamp: new Date(Date.now() - 600000).toISOString(),
    started_at: new Date(Date.now() - 600000).toISOString(),
    ended_at: new Date(Date.now() - 540000).toISOString(),
    risk_score: 55,
    risk_level: 'medium',
    summary: 'Unknown person lingering near back fence',
    reviewed: false,
    notes: '',
  },
  highRisk: {
    id: 3,
    camera_id: 'cam-4',
    camera_name: 'Driveway',
    timestamp: new Date(Date.now() - 1800000).toISOString(),
    started_at: new Date(Date.now() - 1800000).toISOString(),
    ended_at: new Date(Date.now() - 1740000).toISOString(),
    risk_score: 78,
    risk_level: 'high',
    summary: 'Suspicious vehicle parked with occupants inside',
    reviewed: false,
    notes: '',
  },
  criticalRisk: {
    id: 4,
    camera_id: 'cam-1',
    camera_name: 'Front Door',
    timestamp: new Date(Date.now() - 3600000).toISOString(),
    started_at: new Date(Date.now() - 3600000).toISOString(),
    ended_at: new Date(Date.now() - 3540000).toISOString(),
    risk_score: 92,
    risk_level: 'critical',
    summary: 'Multiple unknown individuals attempting door entry',
    reviewed: true,
    notes: 'Reported to authorities',
  },
};

export const allEvents = Object.values(mockEvents);

// GPU Stats Mock Data
export const mockGPUStats = {
  healthy: {
    gpu_name: 'NVIDIA RTX A5500',
    utilization: 45,
    memory_used: 8192,
    memory_total: 24576,
    temperature: 52,
    power_usage: 125,
    inference_fps: 12.5,
  },
  highLoad: {
    gpu_name: 'NVIDIA RTX A5500',
    utilization: 95,
    memory_used: 22000,
    memory_total: 24576,
    temperature: 82,
    power_usage: 230,
    inference_fps: 8.2,
  },
  idle: {
    gpu_name: 'NVIDIA RTX A5500',
    utilization: 5,
    memory_used: 2048,
    memory_total: 24576,
    temperature: 38,
    power_usage: 45,
    inference_fps: 0,
  },
};

// GPU History Data
export function generateGPUHistory(count: number = 10, baseStats = mockGPUStats.healthy) {
  return Array.from({ length: count }, (_, i) => ({
    utilization: baseStats.utilization + Math.floor(Math.random() * 10 - 5),
    memory_used: baseStats.memory_used + Math.floor(Math.random() * 500 - 250),
    memory_total: baseStats.memory_total,
    temperature: baseStats.temperature + Math.floor(Math.random() * 4 - 2),
    inference_fps: baseStats.inference_fps + (Math.random() * 2 - 1),
    recorded_at: new Date(Date.now() - i * 60000).toISOString(),
  }));
}

// System Health Mock Data
export const mockSystemHealth = {
  healthy: {
    status: 'healthy',
    version: '0.1.0',
    services: {
      postgresql: { status: 'healthy', message: 'Connected' },
      redis: { status: 'healthy', message: 'Connected' },
      rtdetr_server: { status: 'healthy', message: 'Ready' },
      nemotron: { status: 'healthy', message: 'Model loaded' },
    },
    timestamp: new Date().toISOString(),
  },
  degraded: {
    status: 'degraded',
    version: '0.1.0',
    services: {
      postgresql: { status: 'healthy', message: 'Connected' },
      redis: { status: 'degraded', message: 'High memory usage' },
      rtdetr_server: { status: 'healthy', message: 'Ready' },
      nemotron: { status: 'healthy', message: 'Model loaded' },
    },
    timestamp: new Date().toISOString(),
  },
  unhealthy: {
    status: 'unhealthy',
    version: '0.1.0',
    services: {
      postgresql: { status: 'unhealthy', message: 'Connection refused' },
      redis: { status: 'healthy', message: 'Connected' },
      rtdetr_server: { status: 'unhealthy', message: 'Model not loaded' },
      nemotron: { status: 'healthy', message: 'Model loaded' },
    },
    timestamp: new Date().toISOString(),
  },
};

// System Stats Mock Data
export const mockSystemStats = {
  normal: {
    total_events: 150,
    events_today: 12,
    high_risk_events: 3,
    active_cameras: 3,
    total_cameras: 4,
    total_detections: 1250,
    uptime_seconds: 86400, // 1 day
  },
  busy: {
    total_events: 500,
    events_today: 45,
    high_risk_events: 12,
    active_cameras: 4,
    total_cameras: 4,
    total_detections: 5000,
    uptime_seconds: 604800, // 7 days
  },
  empty: {
    total_events: 0,
    events_today: 0,
    high_risk_events: 0,
    active_cameras: 0,
    total_cameras: 4,
    total_detections: 0,
    uptime_seconds: 3600, // 1 hour
  },
};

// System Config Mock Data
export const mockSystemConfig = {
  default: {
    batch_window_seconds: 90,
    batch_idle_timeout_seconds: 30,
    retention_days: 30,
  },
  customized: {
    batch_window_seconds: 120,
    batch_idle_timeout_seconds: 45,
    retention_days: 60,
  },
};

// Event Stats Mock Data
export const mockEventStats = {
  normal: {
    total_events: 150,
    events_by_risk_level: { low: 80, medium: 45, high: 20, critical: 5 },
    events_by_camera: { 'cam-1': 50, 'cam-2': 40, 'cam-3': 30, 'cam-4': 30 },
    average_risk_score: 35,
  },
  highAlert: {
    total_events: 100,
    events_by_risk_level: { low: 20, medium: 30, high: 35, critical: 15 },
    events_by_camera: { 'cam-1': 40, 'cam-2': 25, 'cam-4': 35 },
    average_risk_score: 65,
  },
  empty: {
    total_events: 0,
    events_by_risk_level: { low: 0, medium: 0, high: 0, critical: 0 },
    events_by_camera: {},
    average_risk_score: 0,
  },
};

// Logs Mock Data
export const mockLogs = {
  sample: [
    {
      id: 1,
      timestamp: new Date().toISOString(),
      level: 'info',
      component: 'file_watcher',
      message: 'New image detected from Front Door camera',
      details: { camera_id: 'cam-1', filename: 'snapshot_001.jpg' },
    },
    {
      id: 2,
      timestamp: new Date(Date.now() - 60000).toISOString(),
      level: 'warning',
      component: 'rtdetr',
      message: 'Detection confidence below threshold',
      details: { confidence: 0.45, threshold: 0.5 },
    },
    {
      id: 3,
      timestamp: new Date(Date.now() - 120000).toISOString(),
      level: 'error',
      component: 'nemotron',
      message: 'Failed to analyze batch',
      details: { error: 'Timeout', batch_id: 'batch-123' },
    },
    {
      id: 4,
      timestamp: new Date(Date.now() - 180000).toISOString(),
      level: 'debug',
      component: 'api',
      message: 'Request processed successfully',
      details: { endpoint: '/api/events', duration_ms: 45 },
    },
  ],
};

// Log Stats Mock Data
export const mockLogStats = {
  normal: {
    debug: 100,
    info: 500,
    warning: 50,
    error: 10,
    total: 660,
  },
  errorHeavy: {
    debug: 50,
    info: 200,
    warning: 100,
    error: 150,
    total: 500,
  },
  empty: {
    debug: 0,
    info: 0,
    warning: 0,
    error: 0,
    total: 0,
  },
};

// Audit Log Mock Data
export const mockAuditLogs = {
  sample: [
    {
      id: 'audit-1',
      timestamp: new Date().toISOString(),
      action: 'event.reviewed',
      resource_type: 'event',
      resource_id: '123',
      actor: 'user',
      status: 'success',
      details: { notes: 'Marked as false positive' },
    },
    {
      id: 'audit-2',
      timestamp: new Date(Date.now() - 3600000).toISOString(),
      action: 'camera.updated',
      resource_type: 'camera',
      resource_id: 'cam-1',
      actor: 'system',
      status: 'success',
      details: { field: 'status', old: 'offline', new: 'online' },
    },
    {
      id: 'audit-3',
      timestamp: new Date(Date.now() - 7200000).toISOString(),
      action: 'config.changed',
      resource_type: 'system',
      resource_id: 'config',
      actor: 'admin',
      status: 'success',
      details: { setting: 'retention_days', old: 30, new: 60 },
    },
  ],
};

// Audit Stats Mock Data
export const mockAuditStats = {
  normal: {
    total: 150,
    by_action: {
      'event.reviewed': 80,
      'camera.updated': 40,
      'config.changed': 20,
      'system.restart': 10,
    },
    by_resource_type: {
      event: 90,
      camera: 45,
      system: 15,
    },
    by_status: {
      success: 145,
      failed: 5,
    },
    recent_actors: ['user', 'admin', 'system'],
  },
};

// Telemetry Mock Data
export const mockTelemetry = {
  normal: {
    queues: {
      detection_queue: 3,
      analysis_queue: 1,
    },
    latencies: {
      detect: {
        avg_ms: 45,
        p95_ms: 78,
        p99_ms: 120,
      },
      analyze: {
        avg_ms: 250,
        p95_ms: 450,
        p99_ms: 680,
      },
    },
    timestamp: new Date().toISOString(),
  },
  congested: {
    queues: {
      detection_queue: 25,
      analysis_queue: 15,
    },
    latencies: {
      detect: {
        avg_ms: 120,
        p95_ms: 250,
        p99_ms: 400,
      },
      analyze: {
        avg_ms: 800,
        p95_ms: 1500,
        p99_ms: 2500,
      },
    },
    timestamp: new Date().toISOString(),
  },
};

// 1x1 Transparent PNG for camera snapshots
export const transparentPngBase64 =
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==';
