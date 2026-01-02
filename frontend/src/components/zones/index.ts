/**
 * Zone Configuration Components
 *
 * This module provides components for managing camera detection zones.
 * Zones define regions of interest on camera feeds for focused detection
 * and provide context for security analysis.
 *
 * Components:
 * - ZoneEditor: Main modal for zone management
 * - ZoneCanvas: SVG canvas for drawing and displaying zones
 * - ZoneForm: Form for zone properties (name, type, color, etc.)
 * - ZoneList: List view of zones with CRUD actions
 */

export { default as ZoneEditor } from './ZoneEditor';
export { default as ZoneCanvas } from './ZoneCanvas';
export { default as ZoneForm } from './ZoneForm';
export { default as ZoneList } from './ZoneList';

// Re-export types
export type { ZoneEditorProps } from './ZoneEditor';
export type { ZoneCanvasProps, Point } from './ZoneCanvas';
export type { ZoneFormProps, ZoneFormData } from './ZoneForm';
export type { ZoneListProps } from './ZoneList';
