/**
 * Tests for Event Clustering Utility
 */

import { describe, it, expect } from 'vitest';

import {
  clusterEvents,
  isEventCluster,
  getClusterStats,
  type EventCluster,
} from './eventClustering';

import type { Event } from '../services/api';

function createMockEvent(overrides: Partial<Event> = {}): Event {
  return {
    id: 1,
    camera_id: 'camera_123',
    started_at: '2024-01-15T10:00:00Z',
    ended_at: '2024-01-15T10:01:00Z',
    risk_score: 50,
    risk_level: 'medium',
    summary: 'Test event',
    thumbnail_url: 'https://example.com/thumb.jpg',
    reviewed: false,
    detection_count: 1,
    notes: null,
    ...overrides,
  };
}

function createMockEvents(
  count: number,
  baseTime: Date = new Date('2024-01-15T10:00:00Z'),
  options: { cameraId?: string; minutesBetween?: number; riskScores?: number[] } = {}
): Event[] {
  const { cameraId = 'camera_123', minutesBetween = 1, riskScores } = options;
  return Array.from({ length: count }, (_, i) => {
    const startTime = new Date(baseTime.getTime() + i * minutesBetween * 60 * 1000);
    return createMockEvent({
      id: i + 1,
      camera_id: cameraId,
      started_at: startTime.toISOString(),
      risk_score: riskScores?.[i] ?? 50,
      thumbnail_url: `https://example.com/thumb_${i + 1}.jpg`,
    });
  });
}

describe('eventClustering', () => {
  describe('isEventCluster', () => {
    it('returns true for valid EventCluster objects', () => {
      const cluster: EventCluster = {
        clusterId: 'cluster-1',
        cameraId: 'camera_123',
        events: [],
        eventCount: 3,
        startTime: '2024-01-15T10:00:00Z',
        endTime: '2024-01-15T10:05:00Z',
        highestRiskScore: 85,
        highestRiskLevel: 'high',
        thumbnails: [],
      };
      expect(isEventCluster(cluster)).toBe(true);
    });

    it('returns false for Event objects', () => {
      const event = createMockEvent();
      expect(isEventCluster(event)).toBe(false);
    });

    it('returns false for null and undefined', () => {
      expect(isEventCluster(null)).toBe(false);
      expect(isEventCluster(undefined)).toBe(false);
    });
  });

  describe('clusterEvents', () => {
    it('returns empty array for empty input', () => {
      expect(clusterEvents([])).toEqual([]);
    });

    it('returns events as-is when clustering is disabled', () => {
      const events = createMockEvents(5);
      const result = clusterEvents(events, { enabled: false });
      expect(result).toHaveLength(5);
      expect(result.every((item) => !isEventCluster(item))).toBe(true);
    });

    it('does not cluster events below minClusterSize', () => {
      const events = createMockEvents(2);
      const result = clusterEvents(events);
      expect(result).toHaveLength(2);
      expect(result.every((item) => !isEventCluster(item))).toBe(true);
    });

    it('clusters events from same camera within time window', () => {
      const events = createMockEvents(5, new Date('2024-01-15T10:00:00Z'), { minutesBetween: 1 });
      const result = clusterEvents(events);
      expect(result).toHaveLength(1);
      expect(isEventCluster(result[0])).toBe(true);
      const cluster = result[0] as EventCluster;
      expect(cluster.eventCount).toBe(5);
    });

    it('creates multiple clusters for events separated by time', () => {
      const group1 = createMockEvents(3, new Date('2024-01-15T10:00:00Z'));
      const group2 = createMockEvents(3, new Date('2024-01-15T10:15:00Z'));
      group2.forEach((e, i) => {
        e.id = 4 + i;
      });
      const events = [...group1, ...group2];
      const result = clusterEvents(events);
      expect(result).toHaveLength(2);
      expect(result.every((item) => isEventCluster(item))).toBe(true);
    });

    it('does not cluster events from different cameras when sameCamera is true', () => {
      const events = [
        createMockEvent({ id: 1, camera_id: 'camera_1', started_at: '2024-01-15T10:00:00Z' }),
        createMockEvent({ id: 2, camera_id: 'camera_2', started_at: '2024-01-15T10:01:00Z' }),
        createMockEvent({ id: 3, camera_id: 'camera_1', started_at: '2024-01-15T10:02:00Z' }),
      ];
      const result = clusterEvents(events, { sameCamera: true });
      expect(result).toHaveLength(3);
      expect(result.every((item) => !isEventCluster(item))).toBe(true);
    });

    it('calculates highest risk score correctly', () => {
      const events = createMockEvents(4, new Date('2024-01-15T10:00:00Z'), {
        riskScores: [30, 85, 50, 60],
      });
      const result = clusterEvents(events);
      const cluster = result[0] as EventCluster;
      expect(cluster.highestRiskScore).toBe(85);
    });

    it('extracts up to 5 thumbnails', () => {
      const events = createMockEvents(7, new Date('2024-01-15T10:00:00Z'));
      const result = clusterEvents(events);
      const cluster = result[0] as EventCluster;
      expect(cluster.thumbnails).toHaveLength(5);
    });

    it('handles events with null risk scores', () => {
      const events = createMockEvents(3, new Date('2024-01-15T10:00:00Z'));
      events[0].risk_score = null;
      events[1].risk_score = null;
      events[2].risk_score = 75;
      const result = clusterEvents(events);
      const cluster = result[0] as EventCluster;
      expect(cluster.highestRiskScore).toBe(75);
    });

    it('handles single event', () => {
      const events = [createMockEvent()];
      const result = clusterEvents(events);
      expect(result).toHaveLength(1);
      expect(isEventCluster(result[0])).toBe(false);
    });
  });

  describe('getClusterStats', () => {
    it('calculates correct stats for clustered events', () => {
      const events = createMockEvents(10);
      const clustered = clusterEvents(events);
      const stats = getClusterStats(events, clustered);
      expect(stats.originalCount).toBe(10);
      expect(stats.displayCount).toBe(1);
      expect(stats.clusterCount).toBe(1);
      expect(stats.compressionRatio).toBe(10);
    });

    it('handles empty inputs', () => {
      const stats = getClusterStats([], []);
      expect(stats.originalCount).toBe(0);
      expect(stats.displayCount).toBe(0);
      expect(stats.compressionRatio).toBe(1);
    });
  });
});
