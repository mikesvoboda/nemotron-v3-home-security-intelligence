/**
 * Entity Re-Identification Types
 *
 * Types for entity tracking and re-identification across cameras.
 * These types are re-exported from the auto-generated OpenAPI types.
 *
 * Entity re-identification allows tracking the same person or vehicle
 * across multiple cameras using CLIP embeddings.
 *
 * @see backend/api/schemas/entities.py - Backend Pydantic schemas
 * @see NEM-1895
 */

import type { components } from './generated/api';

// ============================================================================
// Core Entity Types
// ============================================================================

/**
 * Entity appearance at a specific time and camera.
 *
 * Represents one sighting of an entity, including the detection it came from
 * and additional attributes extracted from the image.
 */
export type EntityAppearance = components['schemas']['EntityAppearance'];

/**
 * Entity summary for list responses.
 *
 * Provides an overview of a tracked entity without the full appearance history.
 * Used in paginated list responses for efficient loading.
 */
export type EntitySummary = components['schemas']['EntitySummary'];

/**
 * Detailed entity information including appearance history.
 *
 * Extends EntitySummary with the full list of appearances.
 * Used when viewing a single entity's complete tracking history.
 */
export type EntityDetail = components['schemas']['EntityDetail'];

// ============================================================================
// Response Types
// ============================================================================

/**
 * Paginated entity list response.
 *
 * Uses standardized pagination envelope with 'items' and 'pagination' fields
 * following the NEM-2075 pagination standard.
 */
export type EntityListResponse = components['schemas']['EntityListResponse'];

/**
 * Entity appearance history response.
 *
 * Contains a chronological list of all appearances for an entity
 * across all cameras, useful for movement pattern analysis.
 */
export type EntityHistoryResponse = components['schemas']['EntityHistoryResponse'];

// ============================================================================
// Query Parameters Types
// ============================================================================

/**
 * Query parameters for listing tracked entities.
 */
export interface EntityQueryParams {
  /** Filter by entity type: 'person' or 'vehicle' */
  entity_type?: 'person' | 'vehicle';
  /** Filter by camera ID */
  camera_id?: string;
  /** Filter entities seen since this ISO timestamp */
  since?: string;
  /** Maximum number of results (1-1000, default 50) */
  limit?: number;
  /** Number of results to skip for pagination (default 0) */
  offset?: number;
}

// ============================================================================
// Pagination Types (re-exported for convenience)
// ============================================================================

/**
 * Pagination metadata for list responses.
 *
 * Standard pagination info following NEM-2075 pagination envelope.
 */
export type PaginationInfo = components['schemas']['PaginationInfo'];

// ============================================================================
// Type Aliases for Task Compatibility
// ============================================================================

/**
 * Entity type - alias for EntitySummary for backward compatibility with task specification.
 *
 * The task requested an 'Entity' interface, but the backend schema uses 'EntitySummary'
 * for the list response items. This alias provides the expected interface name.
 */
export type Entity = EntitySummary;

/**
 * EntityMatch type for cross-camera entity matching.
 *
 * This represents a match when comparing an entity across cameras.
 * Uses EntityAppearance as the base with matching semantics.
 */
export interface EntityMatch {
  /** Entity ID that was matched */
  entity_id: string;
  /** Detection ID from the matching detection */
  detection_id: string;
  /** Camera ID where the match was found */
  camera_id: string;
  /** Human-readable camera name */
  camera_name: string | null;
  /** Similarity score between 0 and 1 */
  similarity: number;
  /** Timestamp of the matching appearance */
  timestamp: string;
  /** Additional attributes from the detection */
  attributes: Record<string, unknown>;
}

/**
 * EntityHistory type - alias for EntityHistoryResponse.
 *
 * Provides the expected interface name from the task specification.
 */
export type EntityHistory = EntityHistoryResponse;
