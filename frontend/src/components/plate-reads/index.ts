/**
 * Plate Reads Module
 *
 * License Plate Recognition (LPR/ALPR) UI components for viewing,
 * searching, and analyzing plate read data.
 *
 * @see frontend/src/services/plateReadsApi.ts - API client
 * @see frontend/src/types/plateRead.ts - Type definitions
 * @see backend/api/routes/plate_reads.py - Backend endpoints
 */

// Page Components
export { PlateReadsPage } from './PlateReadsPage';

// Statistics Components
export { PlateStatisticsCards } from './PlateStatisticsCards';

// Trends Components
export { PlateReadTrendsCard } from './PlateReadTrendsCard';

// Modal Components
export { PlateDetailModal, type PlateDetailModalProps } from './PlateDetailModal';

// Search Components
export { default as PlateSearchBar, type PlateSearchFilters, type PlateSearchBarProps } from './PlateSearchBar';

// Table Components
export { default as PlateReadTable, type PlateReadTableProps } from './PlateReadTable';

// Action Components
export { PlateExportButton, type PlateExportButtonProps } from './PlateExportButton';

// Badge Components
export { VehicleMatchBadge, type VehicleMatchBadgeProps } from './VehicleMatchBadge';
