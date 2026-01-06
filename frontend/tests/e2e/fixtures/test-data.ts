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
interface EventStats {
  total_events: number;
  events_by_risk_level: { low: number; medium: number; high: number; critical: number };
  events_by_camera: Record<string, number>;
  average_risk_score: number;
}

export const mockEventStats: Record<string, EventStats> = {
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

// Zone Mock Data
export const mockZones = {
  frontDoorEntry: {
    id: 'zone-1',
    camera_id: 'cam-1',
    name: 'Front Door Entry',
    zone_type: 'entry_point',
    coordinates: [
      [0.1, 0.2],
      [0.4, 0.2],
      [0.4, 0.8],
      [0.1, 0.8],
    ],
    shape: 'rectangle',
    color: '#EF4444',
    enabled: true,
    priority: 90,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  frontDoorDriveway: {
    id: 'zone-2',
    camera_id: 'cam-1',
    name: 'Front Driveway',
    zone_type: 'driveway',
    coordinates: [
      [0.5, 0.5],
      [0.9, 0.5],
      [0.9, 0.9],
      [0.5, 0.9],
    ],
    shape: 'rectangle',
    color: '#F59E0B',
    enabled: true,
    priority: 50,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  backYardFence: {
    id: 'zone-3',
    camera_id: 'cam-2',
    name: 'Back Fence',
    zone_type: 'yard',
    coordinates: [
      [0.1, 0.1],
      [0.9, 0.1],
      [0.9, 0.3],
      [0.1, 0.3],
    ],
    shape: 'polygon',
    color: '#10B981',
    enabled: true,
    priority: 70,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  disabledZone: {
    id: 'zone-4',
    camera_id: 'cam-1',
    name: 'Sidewalk Monitor',
    zone_type: 'sidewalk',
    coordinates: [
      [0.0, 0.85],
      [1.0, 0.85],
      [1.0, 1.0],
      [0.0, 1.0],
    ],
    shape: 'rectangle',
    color: '#3B82F6',
    enabled: false,
    priority: 20,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
};

export const allZones = Object.values(mockZones);

export const zonesByCamera = {
  'cam-1': [mockZones.frontDoorEntry, mockZones.frontDoorDriveway, mockZones.disabledZone],
  'cam-2': [mockZones.backYardFence],
  'cam-3': [],
  'cam-4': [],
};

// 1x1 Transparent PNG for camera snapshots
export const transparentPngBase64 =
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==';

// Alert Rule Mock Data
export const mockAlertRules = {
  nightIntruder: {
    id: 'rule-1',
    name: 'Night Intruder Alert',
    description: 'Detect people during nighttime hours',
    enabled: true,
    severity: 'critical',
    risk_threshold: 70,
    object_types: ['person'],
    camera_ids: ['cam-1', 'cam-2'],
    zone_ids: null,
    min_confidence: 0.8,
    schedule: {
      days: ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'],
      start_time: '22:00',
      end_time: '06:00',
      timezone: 'UTC',
    },
    conditions: null,
    dedup_key_template: '{camera_id}:{rule_id}',
    cooldown_seconds: 300,
    channels: ['email', 'pushover'],
    created_at: new Date(Date.now() - 86400000).toISOString(),
    updated_at: new Date(Date.now() - 86400000).toISOString(),
  },
  vehicleDetection: {
    id: 'rule-2',
    name: 'Vehicle Detection',
    description: 'Alert when vehicles are detected in driveway',
    enabled: true,
    severity: 'medium',
    risk_threshold: 50,
    object_types: ['vehicle'],
    camera_ids: ['cam-4'],
    zone_ids: null,
    min_confidence: 0.7,
    schedule: null,
    conditions: null,
    dedup_key_template: '{camera_id}:{rule_id}',
    cooldown_seconds: 600,
    channels: ['webhook'],
    created_at: new Date(Date.now() - 172800000).toISOString(),
    updated_at: new Date(Date.now() - 172800000).toISOString(),
  },
  animalAlert: {
    id: 'rule-3',
    name: 'Animal Alert',
    description: 'Low priority alert for animal detections',
    enabled: false,
    severity: 'low',
    risk_threshold: null,
    object_types: ['animal'],
    camera_ids: [],
    zone_ids: null,
    min_confidence: 0.6,
    schedule: null,
    conditions: null,
    dedup_key_template: '{camera_id}:{rule_id}',
    cooldown_seconds: 900,
    channels: [],
    created_at: new Date(Date.now() - 259200000).toISOString(),
    updated_at: new Date(Date.now() - 259200000).toISOString(),
  },
  highRiskAlert: {
    id: 'rule-4',
    name: 'High Risk Event',
    description: 'Alert for any high risk events across all cameras',
    enabled: true,
    severity: 'high',
    risk_threshold: 80,
    object_types: null,
    camera_ids: null,
    zone_ids: null,
    min_confidence: null,
    schedule: null,
    conditions: null,
    dedup_key_template: '{camera_id}:{rule_id}',
    cooldown_seconds: 120,
    channels: ['email', 'webhook', 'pushover'],
    created_at: new Date(Date.now() - 345600000).toISOString(),
    updated_at: new Date(Date.now() - 345600000).toISOString(),
  },
};

export const allAlertRules = Object.values(mockAlertRules);

// Rule Test Result Mock Data
export const mockRuleTestResults = {
  withMatches: {
    rule_id: 'rule-1',
    rule_name: 'Night Intruder Alert',
    events_tested: 5,
    events_matched: 3,
    match_rate: 0.6,
    results: [
      {
        event_id: 1,
        camera_id: 'cam-1',
        risk_score: 85,
        object_types: ['person'],
        matches: true,
        matched_conditions: ['risk_threshold', 'object_types'],
        started_at: new Date(Date.now() - 3600000).toISOString(),
      },
      {
        event_id: 2,
        camera_id: 'cam-2',
        risk_score: 72,
        object_types: ['person', 'vehicle'],
        matches: true,
        matched_conditions: ['risk_threshold'],
        started_at: new Date(Date.now() - 7200000).toISOString(),
      },
      {
        event_id: 3,
        camera_id: 'cam-1',
        risk_score: 45,
        object_types: ['animal'],
        matches: false,
        matched_conditions: [],
        started_at: new Date(Date.now() - 10800000).toISOString(),
      },
      {
        event_id: 4,
        camera_id: 'cam-3',
        risk_score: 90,
        object_types: ['person'],
        matches: true,
        matched_conditions: ['risk_threshold', 'object_types'],
        started_at: new Date(Date.now() - 14400000).toISOString(),
      },
      {
        event_id: 5,
        camera_id: 'cam-4',
        risk_score: 30,
        object_types: ['vehicle'],
        matches: false,
        matched_conditions: [],
        started_at: new Date(Date.now() - 18000000).toISOString(),
      },
    ],
  },
  noMatches: {
    rule_id: 'rule-3',
    rule_name: 'Animal Alert',
    events_tested: 3,
    events_matched: 0,
    match_rate: 0.0,
    results: [
      {
        event_id: 1,
        camera_id: 'cam-1',
        risk_score: 85,
        object_types: ['person'],
        matches: false,
        matched_conditions: [],
        started_at: new Date(Date.now() - 3600000).toISOString(),
      },
      {
        event_id: 2,
        camera_id: 'cam-2',
        risk_score: 72,
        object_types: ['vehicle'],
        matches: false,
        matched_conditions: [],
        started_at: new Date(Date.now() - 7200000).toISOString(),
      },
      {
        event_id: 3,
        camera_id: 'cam-4',
        risk_score: 90,
        object_types: ['person'],
        matches: false,
        matched_conditions: [],
        started_at: new Date(Date.now() - 10800000).toISOString(),
      },
    ],
  },
  noEvents: {
    rule_id: 'rule-2',
    rule_name: 'Vehicle Detection',
    events_tested: 0,
    events_matched: 0,
    match_rate: 0.0,
    results: [],
  },
};

// AI Audit Mock Data
export const mockAiAuditStats = {
  normal: {
    total_events: 1000,
    audited_events: 950,
    fully_evaluated_events: 800,
    avg_quality_score: 4.2,
    avg_consistency_rate: 4.0,
    avg_enrichment_utilization: 0.75,
    model_contribution_rates: {
      rtdetr: 1.0,
      florence: 0.85,
      clip: 0.6,
      violence: 0.3,
      clothing: 0.5,
      vehicle: 0.4,
      pet: 0.25,
      weather: 0.2,
      image_quality: 0.7,
      zones: 0.65,
      baseline: 0.55,
      cross_camera: 0.15,
    },
    audits_by_day: [
      { date: '2024-01-01', count: 120 },
      { date: '2024-01-02', count: 135 },
      { date: '2024-01-03', count: 145 },
    ],
  },
  empty: {
    total_events: 0,
    audited_events: 0,
    fully_evaluated_events: 0,
    avg_quality_score: null,
    avg_consistency_rate: null,
    avg_enrichment_utilization: null,
    model_contribution_rates: {},
    audits_by_day: [],
  },
};

export const mockAiAuditLeaderboard = {
  normal: {
    entries: [
      { model_name: 'rtdetr', contribution_rate: 1.0, quality_correlation: null, event_count: 1000 },
      { model_name: 'florence', contribution_rate: 0.85, quality_correlation: 0.75, event_count: 850 },
      { model_name: 'image_quality', contribution_rate: 0.7, quality_correlation: 0.65, event_count: 700 },
      { model_name: 'zones', contribution_rate: 0.65, quality_correlation: null, event_count: 650 },
      { model_name: 'clip', contribution_rate: 0.6, quality_correlation: 0.5, event_count: 600 },
      { model_name: 'baseline', contribution_rate: 0.55, quality_correlation: null, event_count: 550 },
      { model_name: 'clothing', contribution_rate: 0.5, quality_correlation: 0.45, event_count: 500 },
      { model_name: 'vehicle', contribution_rate: 0.4, quality_correlation: null, event_count: 400 },
      { model_name: 'violence', contribution_rate: 0.3, quality_correlation: 0.3, event_count: 300 },
      { model_name: 'pet', contribution_rate: 0.25, quality_correlation: null, event_count: 250 },
      { model_name: 'weather', contribution_rate: 0.2, quality_correlation: null, event_count: 200 },
      { model_name: 'cross_camera', contribution_rate: 0.15, quality_correlation: null, event_count: 150 },
    ],
    period_days: 7,
  },
  empty: {
    entries: [],
    period_days: 7,
  },
};

export const mockAiAuditRecommendations = {
  normal: {
    recommendations: [
      {
        category: 'missing_context',
        suggestion: 'Add time since last motion detection',
        frequency: 50,
        priority: 'high',
      },
      {
        category: 'missing_context',
        suggestion: 'Include historical activity patterns',
        frequency: 35,
        priority: 'medium',
      },
      {
        category: 'unused_data',
        suggestion: 'Weather data not used for indoor cameras',
        frequency: 30,
        priority: 'medium',
      },
      {
        category: 'model_gaps',
        suggestion: 'Violence detection missing from prompt',
        frequency: 20,
        priority: 'high',
      },
      {
        category: 'format_suggestions',
        suggestion: 'Group detections by object type',
        frequency: 15,
        priority: 'low',
      },
    ],
    total_events_analyzed: 800,
  },
  empty: {
    recommendations: [],
    total_events_analyzed: 0,
  },
};

// Activity Baseline Mock Data
export const mockActivityBaseline = {
  normal: {
    camera_id: 'cam-1',
    entries: [
      { day_of_week: 0, hour: 8, avg_count: 5.2, sample_count: 28, is_peak: false },
      { day_of_week: 0, hour: 9, avg_count: 8.1, sample_count: 28, is_peak: false },
      { day_of_week: 0, hour: 10, avg_count: 12.5, sample_count: 28, is_peak: false },
      { day_of_week: 1, hour: 8, avg_count: 4.8, sample_count: 28, is_peak: false },
      { day_of_week: 1, hour: 9, avg_count: 7.5, sample_count: 28, is_peak: false },
      { day_of_week: 1, hour: 10, avg_count: 11.2, sample_count: 28, is_peak: false },
      { day_of_week: 2, hour: 8, avg_count: 5.5, sample_count: 28, is_peak: false },
      { day_of_week: 2, hour: 9, avg_count: 8.8, sample_count: 28, is_peak: false },
      { day_of_week: 3, hour: 12, avg_count: 15.0, sample_count: 28, is_peak: false },
      { day_of_week: 4, hour: 17, avg_count: 20.5, sample_count: 28, is_peak: true },
      { day_of_week: 5, hour: 14, avg_count: 18.2, sample_count: 28, is_peak: true },
      { day_of_week: 6, hour: 10, avg_count: 10.0, sample_count: 28, is_peak: false },
    ],
    total_samples: 672,
    peak_hour: 17,
    peak_day: 4,
    learning_complete: true,
    min_samples_required: 100,
  },
  stillLearning: {
    camera_id: 'cam-1',
    entries: [
      { day_of_week: 0, hour: 8, avg_count: 3.2, sample_count: 5, is_peak: false },
      { day_of_week: 0, hour: 9, avg_count: 5.1, sample_count: 5, is_peak: true },
    ],
    total_samples: 45,
    peak_hour: 9,
    peak_day: 0,
    learning_complete: false,
    min_samples_required: 100,
  },
  empty: {
    camera_id: 'cam-1',
    entries: [],
    total_samples: 0,
    peak_hour: null,
    peak_day: null,
    learning_complete: false,
    min_samples_required: 100,
  },
};

// Class Baseline Mock Data
export const mockClassBaseline = {
  normal: {
    camera_id: 'cam-1',
    entries: [
      { object_class: 'person', hour: 8, frequency: 25, sample_count: 28 },
      { object_class: 'person', hour: 9, frequency: 42, sample_count: 28 },
      { object_class: 'person', hour: 17, frequency: 68, sample_count: 28 },
      { object_class: 'vehicle', hour: 8, frequency: 15, sample_count: 28 },
      { object_class: 'vehicle', hour: 17, frequency: 32, sample_count: 28 },
      { object_class: 'animal', hour: 6, frequency: 8, sample_count: 28 },
      { object_class: 'animal', hour: 20, frequency: 12, sample_count: 28 },
    ],
    unique_classes: ['person', 'vehicle', 'animal'],
    most_common_class: 'person',
    total_samples: 196,
  },
  empty: {
    camera_id: 'cam-1',
    entries: [],
    unique_classes: [],
    most_common_class: null,
    total_samples: 0,
  },
};

// Anomaly Config Mock Data
export const mockAnomalyConfig = {
  default: {
    enabled: true,
    sensitivity: 2.0,
    min_samples: 100,
    time_window_hours: 1,
    cooldown_minutes: 30,
    detection_types: ['activity_spike', 'unusual_class', 'time_anomaly'],
  },
  highSensitivity: {
    enabled: true,
    sensitivity: 1.0,
    min_samples: 50,
    time_window_hours: 0.5,
    cooldown_minutes: 15,
    detection_types: ['activity_spike', 'unusual_class', 'time_anomaly', 'pattern_break'],
  },
  disabled: {
    enabled: false,
    sensitivity: 2.0,
    min_samples: 100,
    time_window_hours: 1,
    cooldown_minutes: 30,
    detection_types: [],
  },
};

// AI Metrics Mock Data (for AI Performance page)
export const mockAIMetrics = {
  normal: {
    rtdetr: {
      status: 'healthy',
      model_name: 'RT-DETRv2-L',
      version: '2.0.0',
      inference_fps: 12.5,
      last_inference_at: new Date().toISOString(),
    },
    nemotron: {
      status: 'healthy',
      model_name: 'Nemotron-Mini-4B-Instruct',
      version: '1.0.0',
      tokens_per_second: 45.2,
      last_inference_at: new Date().toISOString(),
    },
    detectionLatency: {
      avg_ms: 45,
      p50_ms: 42,
      p95_ms: 78,
      p99_ms: 120,
    },
    analysisLatency: {
      avg_ms: 250,
      p50_ms: 230,
      p95_ms: 450,
      p99_ms: 680,
    },
    pipelineLatency: {
      avg_ms: 350,
      p50_ms: 320,
      p95_ms: 580,
      p99_ms: 850,
    },
    detectionQueueDepth: 3,
    analysisQueueDepth: 1,
    totalDetections: 15234,
    totalEvents: 1456,
    detectionsByClass: {
      person: 8500,
      vehicle: 4200,
      animal: 1800,
      unknown: 734,
    },
    pipelineErrors: {
      detection: 12,
      analysis: 5,
      storage: 2,
    },
    queueOverflows: 0,
    dlqItems: 3,
    lastUpdated: new Date().toISOString(),
  },
  degraded: {
    rtdetr: {
      status: 'degraded',
      model_name: 'RT-DETRv2-L',
      version: '2.0.0',
      inference_fps: 5.2,
      last_inference_at: new Date(Date.now() - 30000).toISOString(),
    },
    nemotron: {
      status: 'healthy',
      model_name: 'Nemotron-Mini-4B-Instruct',
      version: '1.0.0',
      tokens_per_second: 45.2,
      last_inference_at: new Date().toISOString(),
    },
    detectionLatency: {
      avg_ms: 150,
      p50_ms: 140,
      p95_ms: 280,
      p99_ms: 450,
    },
    analysisLatency: {
      avg_ms: 400,
      p50_ms: 380,
      p95_ms: 720,
      p99_ms: 1100,
    },
    pipelineLatency: {
      avg_ms: 600,
      p50_ms: 550,
      p95_ms: 1050,
      p99_ms: 1600,
    },
    detectionQueueDepth: 25,
    analysisQueueDepth: 15,
    totalDetections: 15234,
    totalEvents: 1456,
    detectionsByClass: {
      person: 8500,
      vehicle: 4200,
      animal: 1800,
      unknown: 734,
    },
    pipelineErrors: {
      detection: 45,
      analysis: 28,
      storage: 12,
    },
    queueOverflows: 8,
    dlqItems: 25,
    lastUpdated: new Date().toISOString(),
  },
};
