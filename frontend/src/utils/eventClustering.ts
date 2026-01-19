/**
 * Event Clustering Utility
 *
 * Groups related events from the same camera within a time window into clusters.
 * This reduces visual noise on the timeline by combining rapid-fire events.
 *
 * @module eventClustering
 */

import type { RiskLevel } from './risk';
import type { Event } from '../services/api';

/**
 * Represents a cluster of related events
 */
export interface EventCluster {
  /** Unique cluster identifier */
  clusterId: string;
  /** Camera ID for all events in cluster */
  cameraId: string;
  /** Camera name for display */
  cameraName?: string;
  /** All events in the cluster */
  events: Event[];
  /** Number of events in cluster */
  eventCount: number;
  /** Start time of first event in cluster */
  startTime: string;
  /** End time of last event in cluster */
  endTime: string;
  /** Highest risk score among all events */
  highestRiskScore: number;
  /** Highest risk level among all events */
  highestRiskLevel: RiskLevel;
  /** Thumbnail URLs from events (up to 5) */
  thumbnails: string[];
}

/**
 * Options for configuring event clustering behavior
 */
export interface ClusteringOptions {
  /** Maximum time gap between events to be clustered (in minutes). Default: 5 */
  maxTimeGapMinutes?: number;
  /** Minimum number of events required to form a cluster. Default: 3 */
  minClusterSize?: number;
  /** Whether to only cluster events from the same camera. Default: true */
  sameCamera?: boolean;
  /** Whether clustering is enabled. Default: true */
  enabled?: boolean;
}

/**
 * Statistics about clustering compression
 */
export interface ClusterStats {
  /** Total number of original events */
  originalCount: number;
  /** Number of items after clustering (clusters + individual events) */
  displayCount: number;
  /** Number of clusters created */
  clusterCount: number;
  /** Compression ratio (originalCount / displayCount) */
  compressionRatio: number;
}

/** Type for items in the clustered result array */
export type ClusteredItem = Event | EventCluster;

/**
 * Risk level priority for comparison (higher = more severe)
 */
const RISK_LEVEL_PRIORITY: Record<string, number> = {
  low: 1,
  medium: 2,
  high: 3,
  critical: 4,
};

/**
 * Default clustering options
 */
const DEFAULT_OPTIONS: Required<ClusteringOptions> = {
  maxTimeGapMinutes: 5,
  minClusterSize: 3,
  sameCamera: true,
  enabled: true,
};

/**
 * Type guard to check if an item is an EventCluster
 */
export function isEventCluster(item: ClusteredItem | null | undefined): item is EventCluster {
  if (!item) return false;
  return 'clusterId' in item && 'events' in item && 'eventCount' in item;
}

/**
 * Get the highest risk level from a set of risk levels
 */
function getHighestRiskLevel(levels: (string | null | undefined)[]): RiskLevel {
  let maxPriority = 0;
  let highestLevel: RiskLevel = 'low';

  for (const level of levels) {
    if (level && RISK_LEVEL_PRIORITY[level]) {
      const priority = RISK_LEVEL_PRIORITY[level];
      if (priority > maxPriority) {
        maxPriority = priority;
        highestLevel = level as RiskLevel;
      }
    }
  }

  return highestLevel;
}

/**
 * Create a cluster from a group of events
 */
function createCluster(events: Event[], cameraName?: string): EventCluster {
  // Sort events by timestamp
  const sortedEvents = [...events].sort(
    (a, b) => new Date(a.started_at).getTime() - new Date(b.started_at).getTime()
  );

  // Calculate highest risk score (handle null values)
  const riskScores = sortedEvents
    .map((e) => e.risk_score)
    .filter((score): score is number => score !== null && score !== undefined);
  const highestRiskScore = riskScores.length > 0 ? Math.max(...riskScores) : 0;

  // Get highest risk level
  const riskLevels = sortedEvents.map((e) => e.risk_level);
  const highestRiskLevel = getHighestRiskLevel(riskLevels);

  // Extract thumbnails (up to 5, skip nulls)
  const thumbnails = sortedEvents
    .map((e) => e.thumbnail_url)
    .filter((url): url is string => url !== null && url !== undefined)
    .slice(0, 5);

  // Generate unique cluster ID
  const firstEvent = sortedEvents[0];
  const lastEvent = sortedEvents[sortedEvents.length - 1];
  const clusterId = `cluster-${firstEvent.id}-${lastEvent.id}-${Date.now()}`;

  return {
    clusterId,
    cameraId: firstEvent.camera_id,
    cameraName,
    events: sortedEvents,
    eventCount: sortedEvents.length,
    startTime: firstEvent.started_at,
    endTime: lastEvent.started_at,
    highestRiskScore,
    highestRiskLevel,
    thumbnails,
  };
}

/**
 * Group events into potential clusters based on camera and time window.
 * Preserves the input order of events - does not re-sort them.
 * Groups consecutive events from the same camera within the time window.
 */
function groupEventsForClustering(
  events: Event[],
  options: Required<ClusteringOptions>
): Event[][] {
  if (events.length === 0) return [];

  const maxGapMs = options.maxTimeGapMinutes * 60 * 1000;
  const groups: Event[][] = [];
  let currentGroup: Event[] = [];

  for (const event of events) {
    if (currentGroup.length === 0) {
      currentGroup.push(event);
      continue;
    }

    const lastEvent = currentGroup[currentGroup.length - 1];
    // Use absolute time difference since events may be in any sort order
    const timeDiff = Math.abs(
      new Date(event.started_at).getTime() - new Date(lastEvent.started_at).getTime()
    );
    const sameCamera = !options.sameCamera || event.camera_id === lastEvent.camera_id;

    if (timeDiff <= maxGapMs && sameCamera) {
      currentGroup.push(event);
    } else {
      groups.push(currentGroup);
      currentGroup = [event];
    }
  }

  // Don't forget the last group
  if (currentGroup.length > 0) {
    groups.push(currentGroup);
  }

  return groups;
}

/**
 * Cluster events based on camera and time proximity
 *
 * @param events - Array of events to cluster
 * @param options - Clustering configuration options
 * @returns Array of clusters and individual events
 */
export function clusterEvents(
  events: Event[],
  options?: ClusteringOptions
): ClusteredItem[] {
  const opts: Required<ClusteringOptions> = { ...DEFAULT_OPTIONS, ...options };

  // If clustering is disabled, return events as-is
  if (!opts.enabled) {
    return events;
  }

  // Empty array check
  if (events.length === 0) {
    return [];
  }

  // Process events while preserving input order
  const groups = groupEventsForClustering(events, opts);
  const results: ClusteredItem[] = [];

  for (const group of groups) {
    if (group.length >= opts.minClusterSize) {
      results.push(createCluster(group));
    } else {
      results.push(...group);
    }
  }

  return results;
}

/**
 * Calculate statistics about clustering compression
 *
 * @param originalEvents - Original events before clustering
 * @param clusteredItems - Result from clusterEvents()
 * @returns Statistics about the clustering
 */
export function getClusterStats(
  originalEvents: Event[],
  clusteredItems: ClusteredItem[]
): ClusterStats {
  const originalCount = originalEvents.length;
  const displayCount = clusteredItems.length;
  const clusterCount = clusteredItems.filter(isEventCluster).length;

  return {
    originalCount,
    displayCount,
    clusterCount,
    compressionRatio: displayCount > 0 ? originalCount / displayCount : 1,
  };
}
