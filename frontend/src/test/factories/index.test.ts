/**
 * Tests for test data factories.
 */

import { describe, it, expect, beforeEach } from 'vitest';

import {
  cameraFactory,
  cameraFactoryList,
  eventFactory,
  eventFactoryList,
  detectionFactory,
  detectionFactoryList,
  gpuStatsFactory,
  gpuStatsFactoryList,
  healthResponseFactory,
  systemStatsFactory,
  uniqueId,
  resetCounter,
} from './index';

// ============================================================================
// Unique ID Tests
// ============================================================================

describe('uniqueId', () => {
  beforeEach(() => {
    resetCounter();
  });

  it('generates unique IDs', () => {
    const id1 = uniqueId('test');
    const id2 = uniqueId('test');
    const id3 = uniqueId('test');

    expect(id1).not.toBe(id2);
    expect(id2).not.toBe(id3);
  });

  it('uses custom prefix', () => {
    const id = uniqueId('camera');
    expect(id).toMatch(/^camera-\d+$/);
  });

  it('increments counter', () => {
    const id1 = uniqueId('test');
    const id2 = uniqueId('test');

    expect(id1).toBe('test-1');
    expect(id2).toBe('test-2');
  });

  it('resets counter', () => {
    uniqueId('test');
    uniqueId('test');
    resetCounter();

    const id = uniqueId('test');
    expect(id).toBe('test-1');
  });
});

// ============================================================================
// Camera Factory Tests
// ============================================================================

describe('cameraFactory', () => {
  it('creates camera with defaults', () => {
    const camera = cameraFactory();

    expect(camera).toHaveProperty('id');
    expect(camera).toHaveProperty('name');
    expect(camera).toHaveProperty('folder_path');
    expect(camera).toHaveProperty('status');
    expect(camera).toHaveProperty('created_at');
    expect(camera).toHaveProperty('last_seen_at');
  });

  it('uses default values', () => {
    const camera = cameraFactory();

    expect(camera.name).toBe('Test Camera');
    expect(camera.status).toBe('online');
  });

  it('allows overrides', () => {
    const camera = cameraFactory({
      name: 'Custom Camera',
      status: 'offline',
    });

    expect(camera.name).toBe('Custom Camera');
    expect(camera.status).toBe('offline');
  });

  it('generates unique IDs', () => {
    const camera1 = cameraFactory();
    const camera2 = cameraFactory();

    expect(camera1.id).not.toBe(camera2.id);
  });
});

describe('cameraFactoryList', () => {
  it('creates multiple cameras', () => {
    const cameras = cameraFactoryList(3);

    expect(cameras).toHaveLength(3);
    cameras.forEach((camera) => {
      expect(camera).toHaveProperty('id');
      expect(camera).toHaveProperty('name');
    });
  });

  it('creates cameras with unique IDs', () => {
    const cameras = cameraFactoryList(5);
    const ids = cameras.map((c) => c.id);
    const uniqueIds = new Set(ids);

    expect(uniqueIds.size).toBe(5);
  });

  it('accepts override function', () => {
    const cameras = cameraFactoryList(3, (i) => ({
      name: `Camera ${i}`,
    }));

    expect(cameras[0].name).toBe('Camera 0');
    expect(cameras[1].name).toBe('Camera 1');
    expect(cameras[2].name).toBe('Camera 2');
  });
});

// ============================================================================
// Event Factory Tests
// ============================================================================

describe('eventFactory', () => {
  it('creates event with defaults', () => {
    const event = eventFactory();

    expect(event).toHaveProperty('id');
    expect(event).toHaveProperty('camera_id');
    expect(event).toHaveProperty('started_at');
    expect(event).toHaveProperty('ended_at');
    expect(event).toHaveProperty('risk_score');
    expect(event).toHaveProperty('risk_level');
    expect(event).toHaveProperty('summary');
  });

  it('uses default values', () => {
    const event = eventFactory();

    expect(event.risk_score).toBe(50);
    expect(event.risk_level).toBe('medium');
    expect(event.reviewed).toBe(false);
  });

  it('allows overrides', () => {
    const event = eventFactory({
      risk_score: 85,
      risk_level: 'high',
      reviewed: true,
    });

    expect(event.risk_score).toBe(85);
    expect(event.risk_level).toBe('high');
    expect(event.reviewed).toBe(true);
  });

  it('generates valid timestamps', () => {
    const event = eventFactory();

    const startedAt = new Date(event.started_at);
    const endedAt = event.ended_at ? new Date(event.ended_at) : new Date();

    expect(startedAt.getTime()).toBeLessThan(endedAt.getTime());
  });
});

describe('eventFactoryList', () => {
  it('creates multiple events', () => {
    const events = eventFactoryList(5);

    expect(events).toHaveLength(5);
    events.forEach((event) => {
      expect(event).toHaveProperty('id');
      expect(event).toHaveProperty('risk_score');
    });
  });

  it('accepts override function', () => {
    const events = eventFactoryList(3, (i) => ({
      risk_score: 10 + i * 10,
    }));

    expect(events[0].risk_score).toBe(10);
    expect(events[1].risk_score).toBe(20);
    expect(events[2].risk_score).toBe(30);
  });
});

// ============================================================================
// Detection Factory Tests
// ============================================================================

describe('detectionFactory', () => {
  it('creates detection with defaults', () => {
    const detection = detectionFactory();

    expect(detection).toHaveProperty('id');
    expect(detection).toHaveProperty('camera_id');
    expect(detection).toHaveProperty('object_type');
    expect(detection).toHaveProperty('confidence');
    expect(detection).toHaveProperty('bbox_x');
    expect(detection).toHaveProperty('bbox_y');
    expect(detection).toHaveProperty('bbox_width');
    expect(detection).toHaveProperty('bbox_height');
  });

  it('uses default values', () => {
    const detection = detectionFactory();

    expect(detection.object_type).toBe('person');
    expect(detection.confidence).toBe(0.85);
    expect(detection.bbox_x).toBe(100);
    expect(detection.bbox_y).toBe(100);
    expect(detection.bbox_width).toBe(200);
    expect(detection.bbox_height).toBe(200);
  });

  it('allows overrides', () => {
    const detection = detectionFactory({
      object_type: 'car',
      confidence: 0.95,
      bbox_x: 50,
      bbox_y: 50,
      bbox_width: 150,
      bbox_height: 150,
    });

    expect(detection.object_type).toBe('car');
    expect(detection.confidence).toBe(0.95);
    expect(detection.bbox_x).toBe(50);
  });

  it('generates valid confidence values', () => {
    const detection = detectionFactory();

    expect(detection.confidence).toBeGreaterThanOrEqual(0);
    expect(detection.confidence).toBeLessThanOrEqual(1);
  });
});

describe('detectionFactoryList', () => {
  it('creates multiple detections', () => {
    const detections = detectionFactoryList(4);

    expect(detections).toHaveLength(4);
    detections.forEach((detection) => {
      expect(detection).toHaveProperty('object_type');
      expect(detection).toHaveProperty('confidence');
    });
  });

  it('accepts override function', () => {
    const detections = detectionFactoryList(3, (i) => ({
      confidence: 0.7 + i * 0.1,
    }));

    expect(detections[0].confidence).toBeCloseTo(0.7);
    expect(detections[1].confidence).toBeCloseTo(0.8);
    expect(detections[2].confidence).toBeCloseTo(0.9);
  });
});

// ============================================================================
// GPU Stats Factory Tests
// ============================================================================

describe('gpuStatsFactory', () => {
  it('creates GPU stats with defaults', () => {
    const stats = gpuStatsFactory();

    expect(stats).toHaveProperty('utilization');
    expect(stats).toHaveProperty('memory_used');
    expect(stats).toHaveProperty('memory_total');
    expect(stats).toHaveProperty('temperature');
    expect(stats).toHaveProperty('power_usage');
  });

  it('allows overrides', () => {
    const stats = gpuStatsFactory({
      utilization: 90.5,
      temperature: 80,
    });

    expect(stats.utilization).toBe(90.5);
    expect(stats.temperature).toBe(80);
  });
});

describe('gpuStatsFactoryList', () => {
  it('creates multiple GPU stats', () => {
    const statsList = gpuStatsFactoryList(5);

    expect(statsList).toHaveLength(5);
    statsList.forEach((stats) => {
      expect(stats).toHaveProperty('utilization');
    });
  });
});

// ============================================================================
// Health Response Factory Tests
// ============================================================================

describe('healthResponseFactory', () => {
  it('creates health response with defaults', () => {
    const health = healthResponseFactory();

    expect(health.status).toBe('healthy');
    expect(health.services.database.status).toBe('healthy');
    expect(health.services.redis.status).toBe('healthy');
    expect(health.services.ai.status).toBe('healthy');
  });

  it('allows overrides', () => {
    const health = healthResponseFactory({
      status: 'degraded',
      services: {
        database: { status: 'healthy', message: 'OK' },
        redis: { status: 'unhealthy', message: 'Connection failed' },
        ai: { status: 'healthy', message: 'OK' },
      },
    });

    expect(health.status).toBe('degraded');
    expect(health.services.redis.status).toBe('unhealthy');
  });
});

// ============================================================================
// System Stats Factory Tests
// ============================================================================

describe('systemStatsFactory', () => {
  it('creates system stats with defaults', () => {
    const stats = systemStatsFactory();

    expect(stats).toHaveProperty('total_cameras');
    expect(stats).toHaveProperty('total_events');
    expect(stats).toHaveProperty('total_detections');
    expect(stats).toHaveProperty('uptime_seconds');
  });

  it('allows overrides', () => {
    const stats = systemStatsFactory({
      total_cameras: 10,
      uptime_seconds: 172800,
    });

    expect(stats.total_cameras).toBe(10);
    expect(stats.uptime_seconds).toBe(172800);
  });
});
