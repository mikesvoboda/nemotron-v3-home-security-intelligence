/**
 * Bulk Operation Types for Detection and Event APIs
 *
 * This module provides types for bulk create, update, and delete operations
 * with HTTP 207 Multi-Status support for partial success handling.
 *
 * The types are re-exported from the generated OpenAPI types and provide
 * a convenient, well-documented interface for bulk operations.
 *
 * @module types/bulk
 * @see backend/api/schemas/bulk.py - Backend Pydantic schemas
 */

import type { components } from './generated/api';

// ============================================================================
// Bulk Operation Status Types
// ============================================================================

/**
 * Status of individual items in a bulk operation.
 *
 * - `success`: Operation completed successfully
 * - `failed`: Operation failed (check error field for details)
 * - `skipped`: Operation was skipped (e.g., item not found for update/delete)
 */
export type BulkOperationStatus = components['schemas']['BulkOperationStatus'];

/**
 * Result for a single item in a bulk operation.
 *
 * Each item in the request array gets a corresponding result with:
 * - `index`: The position in the original request array (zero-based)
 * - `status`: Whether this item succeeded, failed, or was skipped
 * - `id`: The created/updated resource ID (only for successful operations)
 * - `error`: Error message explaining the failure (only for failed operations)
 *
 * @example
 * ```typescript
 * const result: BulkItemResult = {
 *   index: 0,
 *   status: 'success',
 *   id: 123,
 * };
 *
 * const failedResult: BulkItemResult = {
 *   index: 1,
 *   status: 'failed',
 *   error: 'Camera not found: cam-unknown',
 * };
 * ```
 */
export type BulkItemResult = components['schemas']['BulkItemResult'];

/**
 * Base response for bulk operations with partial success support.
 *
 * Uses HTTP 207 Multi-Status when some operations succeed and others fail.
 * This allows clients to handle partial failures gracefully.
 *
 * @example
 * ```typescript
 * // HTTP 200: All succeeded
 * { total: 5, succeeded: 5, failed: 0, skipped: 0, results: [...] }
 *
 * // HTTP 207: Partial success
 * { total: 5, succeeded: 3, failed: 2, skipped: 0, results: [...] }
 *
 * // HTTP 400: All failed (validation error)
 * { total: 5, succeeded: 0, failed: 5, skipped: 0, results: [...] }
 * ```
 */
export type BulkOperationResponse = components['schemas']['BulkOperationResponse'];

// ============================================================================
// Detection Bulk Types
// ============================================================================

/**
 * Schema for a single detection in a bulk create request.
 *
 * Contains all required fields to create a new detection record.
 * The enrichment_data field is optional and can contain results
 * from the enrichment pipeline (face recognition, license plate, etc.).
 *
 * @example
 * ```typescript
 * const detection: DetectionBulkCreateItem = {
 *   camera_id: 'cam-front-door',
 *   object_type: 'person',
 *   confidence: 0.95,
 *   detected_at: '2024-01-20T10:30:00Z',
 *   file_path: '/uploads/cam-front-door/2024-01-20/frame_001.jpg',
 *   bbox_x: 100,
 *   bbox_y: 50,
 *   bbox_width: 200,
 *   bbox_height: 400,
 *   enrichment_data: {
 *     pose: { action: 'walking' },
 *   },
 * };
 * ```
 */
export type DetectionBulkCreateItem = components['schemas']['DetectionBulkCreateItem'];

/**
 * Schema for a single detection update in a bulk update request.
 *
 * Only the `id` field is required. All other fields are optional
 * and only provided fields will be updated.
 *
 * @example
 * ```typescript
 * const update: DetectionBulkUpdateItem = {
 *   id: 123,
 *   object_type: 'vehicle', // Correct misclassification
 *   confidence: 0.99,
 * };
 * ```
 */
export type DetectionBulkUpdateItem = components['schemas']['DetectionBulkUpdateItem'];

/**
 * Response for bulk detection creation.
 *
 * Extends BulkOperationResponse with created detection IDs in the results.
 */
export type DetectionBulkCreateResponse = components['schemas']['DetectionBulkCreateResponse'];

// ============================================================================
// Utility Types
// ============================================================================

/**
 * Request payload for bulk detection creation.
 *
 * @internal Used internally by the API functions
 */
export interface DetectionBulkCreateRequest {
  detections: DetectionBulkCreateItem[];
}

/**
 * Request payload for bulk detection update.
 *
 * @internal Used internally by the API functions
 */
export interface DetectionBulkUpdateRequest {
  detections: DetectionBulkUpdateItem[];
}

/**
 * Request payload for bulk detection deletion.
 *
 * @internal Used internally by the API functions
 */
export interface DetectionBulkDeleteRequest {
  detection_ids: number[];
}

// ============================================================================
// Type Guards
// ============================================================================

/**
 * Check if all items in a bulk operation succeeded.
 *
 * @param response - The bulk operation response to check
 * @returns true if all items succeeded, false if any failed or were skipped
 *
 * @example
 * ```typescript
 * const response = await bulkCreateDetections(items);
 * if (isAllSucceeded(response)) {
 *   console.log('All detections created successfully!');
 * } else {
 *   console.log(`${response.failed} detections failed`);
 * }
 * ```
 */
export function isAllSucceeded(response: BulkOperationResponse): boolean {
  return response.succeeded === response.total && response.failed === 0 && response.skipped === 0;
}

/**
 * Check if a bulk operation had any failures.
 *
 * @param response - The bulk operation response to check
 * @returns true if any items failed
 */
export function hasFailures(response: BulkOperationResponse): boolean {
  return response.failed > 0;
}

/**
 * Check if a bulk operation was a partial success (some succeeded, some failed).
 *
 * @param response - The bulk operation response to check
 * @returns true if the operation was a partial success
 */
export function isPartialSuccess(response: BulkOperationResponse): boolean {
  return response.succeeded > 0 && (response.failed > 0 || response.skipped > 0);
}

/**
 * Get only the failed results from a bulk operation response.
 *
 * @param response - The bulk operation response
 * @returns Array of failed BulkItemResult objects
 */
export function getFailedResults(response: BulkOperationResponse): BulkItemResult[] {
  return (response.results ?? []).filter((r) => r.status === 'failed');
}

/**
 * Get only the successful results from a bulk operation response.
 *
 * @param response - The bulk operation response
 * @returns Array of successful BulkItemResult objects with their IDs
 */
export function getSuccessfulResults(response: BulkOperationResponse): BulkItemResult[] {
  return (response.results ?? []).filter((r) => r.status === 'success');
}

/**
 * Get the IDs of successfully created/updated items.
 *
 * @param response - The bulk operation response
 * @returns Array of IDs for successful operations
 */
export function getSuccessfulIds(response: BulkOperationResponse): number[] {
  return getSuccessfulResults(response)
    .map((r) => r.id)
    .filter((id): id is number => id !== null && id !== undefined);
}
