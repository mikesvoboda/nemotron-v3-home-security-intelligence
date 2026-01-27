/**
 * Zone Configuration Components
 *
 * This module provides components for managing camera detection zones.
 * Zones define regions of interest on camera feeds for focused detection
 * and provide context for security analysis.
 *
 * Components:
 * - ZoneEditor: Main modal for zone management with intelligence integration
 * - ZoneEditorSidebar: Tabbed sidebar for Draw/Configure/Analytics modes
 * - ZoneCanvas: SVG canvas for drawing and displaying zones
 * - ZoneForm: Form for zone properties (name, type, color, etc.)
 * - ZoneList: List view of zones with CRUD actions
 * - ZoneStatusCard: Zone intelligence status display
 * - ZoneActivityHeatmap: Zone activity visualization
 * - ZoneOwnershipPanel: Zone ownership and access control management
 * - CameraZoneOverlay: SVG overlay for camera video feeds with zone visualization
 * - ZoneAlertFeed: Unified feed for zone anomaly and trust violation alerts
 * - LineZoneEditor: Component for drawing tripwire/line zones
 * - PolygonZoneEditor: Component for drawing polygon zones with zone type support
 */

export { default as ZoneEditor } from './ZoneEditor';
export { default as ZoneEditorSidebar } from './ZoneEditorSidebar';
export { default as ZoneCanvas } from './ZoneCanvas';
export { default as ZoneForm } from './ZoneForm';
export { default as ZoneList } from './ZoneList';
export { default as ZoneStatusCard } from './ZoneStatusCard';
export { default as ZoneActivityHeatmap } from './ZoneActivityHeatmap';
export { default as ZoneOwnershipPanel } from './ZoneOwnershipPanel';
export { default as CameraZoneOverlay } from './CameraZoneOverlay';
export { default as ZoneAlertFeed, ZoneAlertFeed as ZoneAlertFeedNamed } from './ZoneAlertFeed';
export { default as LineZoneEditor } from './LineZoneEditor';
export { default as PolygonZoneEditor } from './PolygonZoneEditor';

// Re-export types
export type { ZoneEditorProps, ZoneEditorLegacyProps, ZoneEditorEnhancedProps } from './ZoneEditor';
export type { ZoneEditorSidebarProps, SidebarTab } from './ZoneEditorSidebar';
export type { ZoneCanvasProps, Point } from './ZoneCanvas';
export type { ZoneFormProps, ZoneFormData } from './ZoneForm';
export type { ZoneListProps } from './ZoneList';
export type { ZoneStatusCardProps, ActivityLevel, ZoneStatus } from './ZoneStatusCard';
export type {
  ZoneActivityHeatmapProps,
  HeatmapTimeRange,
  HeatmapDataPoint,
  HourlyActivity,
} from './ZoneActivityHeatmap';
export type { ZoneOwnershipPanelProps } from './ZoneOwnershipPanel';
export type { CameraZoneOverlayProps, OverlayMode } from './CameraZoneOverlay';
export type { ZoneAlertFeedProps } from '../../types/zoneAlert';
export type { LineZoneEditorProps } from './LineZoneEditor';
export type { PolygonZoneEditorProps, ExistingZone } from './PolygonZoneEditor';
