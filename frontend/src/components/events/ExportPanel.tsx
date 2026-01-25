import { Card, Title, Text, Button } from '@tremor/react';
import {
  AlertCircle,
  Calendar,
  Check,
  ChevronDown,
  ChevronUp,
  Download,
  FileSpreadsheet,
  FileText,
  Loader2,
} from 'lucide-react';
import { useEffect, useState } from 'react';

import { exportEventsCSV, exportEventsJSON, fetchCameras, fetchEventStats } from '../../services/api';

import type { Camera, EventStatsResponse, ExportQueryParams } from '../../services/api';

export interface ExportPanelProps {
  /** Pre-populate filters from EventTimeline */
  initialFilters?: ExportQueryParams;
  /** Callback when export starts (for external UI state management) */
  onExportStart?: () => void;
  /** Callback when export completes or fails */
  onExportComplete?: (success: boolean, message?: string) => void;
  /** Whether the panel is collapsible */
  collapsible?: boolean;
  /** Whether the panel starts collapsed */
  defaultCollapsed?: boolean;
  /** Additional CSS classes */
  className?: string;
}

export type ExportFormat = 'csv' | 'json';

/**
 * ExportPanel component provides a comprehensive UI for exporting events data.
 * Features:
 * - Filter options (date range, camera, risk level, reviewed status)
 * - Format selection (CSV, JSON - JSON future expansion)
 * - Export preview showing estimated record count
 * - Progress indicator during export
 * - Success/error feedback
 */
export default function ExportPanel({
  initialFilters,
  onExportStart,
  onExportComplete,
  collapsible = false,
  defaultCollapsed = false,
  className = '',
}: ExportPanelProps) {
  // Panel collapse state
  const [isCollapsed, setIsCollapsed] = useState(defaultCollapsed);

  // Filter state
  const [filters, setFilters] = useState<ExportQueryParams>({
    camera_id: initialFilters?.camera_id,
    risk_level: initialFilters?.risk_level,
    start_date: initialFilters?.start_date,
    end_date: initialFilters?.end_date,
    reviewed: initialFilters?.reviewed,
  });

  // Format selection
  const [format, setFormat] = useState<ExportFormat>('csv');

  // Export state
  const [exporting, setExporting] = useState(false);
  const [exportSuccess, setExportSuccess] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  // Data for filter options
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [stats, setStats] = useState<EventStatsResponse | null>(null);
  const [loadingStats, setLoadingStats] = useState(false);

  // Load cameras for filter dropdown
  useEffect(() => {
    const loadCameras = async () => {
      try {
        const data = await fetchCameras();
        setCameras(data);
      } catch (err) {
        console.error('Failed to load cameras:', err);
      }
    };
    void loadCameras();
  }, []);

  // Load stats when filters change (for preview count)
  useEffect(() => {
    const loadStats = async () => {
      setLoadingStats(true);
      try {
        const data = await fetchEventStats({
          start_date: filters.start_date,
          end_date: filters.end_date,
        });
        setStats(data);
      } catch (err) {
        console.error('Failed to load stats:', err);
        setStats(null);
      } finally {
        setLoadingStats(false);
      }
    };
    void loadStats();
  }, [filters.start_date, filters.end_date]);

  // Handle filter changes
  const handleFilterChange = (
    key: keyof ExportQueryParams,
    value: string | boolean | undefined
  ) => {
    setFilters((prev) => ({
      ...prev,
      [key]: value === '' ? undefined : value,
    }));
    // Clear any previous messages
    setExportSuccess(null);
    setExportError(null);
  };

  // Clear all filters
  const handleClearFilters = () => {
    setFilters({});
    setExportSuccess(null);
    setExportError(null);
  };

  // Calculate estimated count based on filters
  const getEstimatedCount = (): string => {
    if (loadingStats) return 'Calculating...';
    if (!stats) return 'Unknown';

    // If no filters applied, return total
    const hasFilters = filters.camera_id || filters.risk_level || filters.reviewed !== undefined;
    if (!hasFilters) {
      return `~${stats.total_events} events`;
    }

    // With filters, we can only provide a rough estimate
    let estimate = stats.total_events;

    if (filters.risk_level && stats.events_by_risk_level) {
      const levelCount =
        stats.events_by_risk_level[filters.risk_level as keyof typeof stats.events_by_risk_level];
      if (typeof levelCount === 'number') {
        estimate = levelCount;
      }
    }

    if (filters.camera_id && stats.events_by_camera) {
      const cameraStats = stats.events_by_camera.find((c) => c.camera_id === filters.camera_id);
      if (cameraStats) {
        estimate = Math.min(estimate, cameraStats.event_count);
      }
    }

    return `~${estimate} events (filtered)`;
  };

  // Handle export action
  const handleExport = async () => {
    setExporting(true);
    setExportSuccess(null);
    setExportError(null);
    onExportStart?.();

    try {
      if (format === 'csv') {
        await exportEventsCSV(filters);
      } else {
        await exportEventsJSON(filters);
      }
      setExportSuccess('Export completed successfully! Check your downloads folder.');
      onExportComplete?.(true, 'Export completed successfully');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Export failed';
      setExportError(message);
      onExportComplete?.(false, message);
    } finally {
      setExporting(false);
    }

    // Clear success message after 5 seconds
    setTimeout(() => {
      setExportSuccess(null);
    }, 5000);
  };

  // Determine if there are any active filters
  const hasActiveFilters = !!(
    filters.camera_id ||
    filters.risk_level ||
    filters.start_date ||
    filters.end_date ||
    filters.reviewed !== undefined
  );

  // Render the panel content
  const renderContent = () => (
    <div className="space-y-6">
      {/* Export Format Selection */}
      <div>
        <Text className="mb-3 font-medium text-gray-300">Export Format</Text>
        <div className="flex gap-3">
          <button
            onClick={() => setFormat('csv')}
            className={`flex flex-1 items-center justify-center gap-2 rounded-lg border px-4 py-3 text-sm font-medium transition-all ${
              format === 'csv'
                ? 'border-[#76B900] bg-[#76B900]/10 text-[#76B900]'
                : 'border-gray-700 bg-[#1A1A1A] text-gray-400 hover:border-gray-600 hover:bg-[#252525]'
            }`}
            aria-pressed={format === 'csv'}
          >
            <FileSpreadsheet className="h-5 w-5" />
            <span>CSV</span>
            {format === 'csv' && <Check className="h-4 w-4" />}
          </button>
          <button
            onClick={() => setFormat('json')}
            className={`flex flex-1 items-center justify-center gap-2 rounded-lg border px-4 py-3 text-sm font-medium transition-all ${
              format === 'json'
                ? 'border-[#76B900] bg-[#76B900]/10 text-[#76B900]'
                : 'border-gray-700 bg-[#1A1A1A] text-gray-400 hover:border-gray-600 hover:bg-[#252525]'
            }`}
            aria-pressed={format === 'json'}
          >
            <FileText className="h-5 w-5" />
            <span>JSON</span>
            {format === 'json' && <Check className="h-4 w-4" />}
          </button>
        </div>
      </div>

      {/* Filter Options */}
      <div>
        <div className="mb-3 flex items-center justify-between">
          <Text className="font-medium text-gray-300">Filter Options</Text>
          {hasActiveFilters && (
            <button
              onClick={handleClearFilters}
              className="text-xs text-[#76B900] hover:text-[#88d200]"
            >
              Clear all filters
            </button>
          )}
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {/* Camera Filter */}
          <div>
            <label htmlFor="export-camera-filter" className="mb-1 block text-sm text-gray-400">
              Camera
            </label>
            <select
              id="export-camera-filter"
              value={filters.camera_id || ''}
              onChange={(e) => handleFilterChange('camera_id', e.target.value)}
              className="w-full rounded-md border border-gray-700 bg-[#1A1A1A] px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
            >
              <option value="">All Cameras</option>
              {cameras.map((camera) => (
                <option key={camera.id} value={camera.id}>
                  {camera.name}
                </option>
              ))}
            </select>
          </div>

          {/* Risk Level Filter */}
          <div>
            <label htmlFor="export-risk-filter" className="mb-1 block text-sm text-gray-400">
              Risk Level
            </label>
            <select
              id="export-risk-filter"
              value={filters.risk_level || ''}
              onChange={(e) => handleFilterChange('risk_level', e.target.value)}
              className="w-full rounded-md border border-gray-700 bg-[#1A1A1A] px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
            >
              <option value="">All Risk Levels</option>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
              <option value="critical">Critical</option>
            </select>
          </div>

          {/* Start Date Filter */}
          <div>
            <label htmlFor="export-start-date" className="mb-1 block text-sm text-gray-400">
              Start Date
            </label>
            <div className="relative">
              <Calendar className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
              <input
                id="export-start-date"
                type="date"
                value={filters.start_date || ''}
                onChange={(e) => handleFilterChange('start_date', e.target.value)}
                className="w-full rounded-md border border-gray-700 bg-[#1A1A1A] py-2 pl-10 pr-3 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
              />
            </div>
          </div>

          {/* End Date Filter */}
          <div>
            <label htmlFor="export-end-date" className="mb-1 block text-sm text-gray-400">
              End Date
            </label>
            <div className="relative">
              <Calendar className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
              <input
                id="export-end-date"
                type="date"
                value={filters.end_date || ''}
                onChange={(e) => handleFilterChange('end_date', e.target.value)}
                className="w-full rounded-md border border-gray-700 bg-[#1A1A1A] py-2 pl-10 pr-3 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
              />
            </div>
          </div>

          {/* Reviewed Status Filter */}
          <div className="sm:col-span-2">
            <label htmlFor="export-reviewed-filter" className="mb-1 block text-sm text-gray-400">
              Review Status
            </label>
            <select
              id="export-reviewed-filter"
              value={filters.reviewed === undefined ? '' : filters.reviewed ? 'true' : 'false'}
              onChange={(e) =>
                handleFilterChange(
                  'reviewed',
                  e.target.value === '' ? undefined : e.target.value === 'true'
                )
              }
              className="w-full rounded-md border border-gray-700 bg-[#1A1A1A] px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
            >
              <option value="">All Events</option>
              <option value="false">Unreviewed Only</option>
              <option value="true">Reviewed Only</option>
            </select>
          </div>
        </div>
      </div>

      {/* Export Preview */}
      <div className="rounded-lg border border-gray-800 bg-[#151515] p-4">
        <div className="flex items-center justify-between">
          <div>
            <Text className="font-medium text-gray-300">Export Preview</Text>
            <Text className="mt-1 text-sm text-gray-500">
              {loadingStats ? (
                <span className="flex items-center gap-2">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  Calculating...
                </span>
              ) : (
                getEstimatedCount()
              )}
            </Text>
          </div>
          <div className="text-right">
            <Text className="text-sm text-gray-400">Format</Text>
            <Text className="font-medium text-white">{format.toUpperCase()}</Text>
          </div>
        </div>
      </div>

      {/* Success Message */}
      {exportSuccess && (
        <div className="flex items-center gap-2 rounded-lg border border-green-500/30 bg-green-500/10 p-4">
          <Check className="h-5 w-5 flex-shrink-0 text-green-500" />
          <Text className="text-green-500">{exportSuccess}</Text>
        </div>
      )}

      {/* Error Message */}
      {exportError && (
        <div className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-4">
          <AlertCircle className="h-5 w-5 flex-shrink-0 text-red-500" />
          <Text className="text-red-500">{exportError}</Text>
        </div>
      )}

      {/* Export Button */}
      <Button
        onClick={() => void handleExport()}
        disabled={exporting || stats?.total_events === 0}
        className="w-full bg-[#76B900] text-gray-950 hover:bg-[#5c8f00] disabled:cursor-not-allowed disabled:opacity-50"
      >
        {exporting ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Exporting...
          </>
        ) : (
          <>
            <Download className="mr-2 h-4 w-4" />
            Export Events
          </>
        )}
      </Button>
    </div>
  );

  return (
    <Card className={`border-gray-800 bg-[#1A1A1A] shadow-lg ${className}`}>
      {collapsible ? (
        <>
          <button
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="flex w-full items-center justify-between text-left"
            aria-expanded={!isCollapsed}
          >
            <Title className="flex items-center gap-2 text-white">
              <Download className="h-5 w-5 text-[#76B900]" />
              Data Export
            </Title>
            {isCollapsed ? (
              <ChevronDown className="h-5 w-5 text-gray-400" />
            ) : (
              <ChevronUp className="h-5 w-5 text-gray-400" />
            )}
          </button>
          {!isCollapsed && <div className="mt-4">{renderContent()}</div>}
        </>
      ) : (
        <>
          <Title className="mb-4 flex items-center gap-2 text-white">
            <Download className="h-5 w-5 text-[#76B900]" />
            Data Export
          </Title>
          {renderContent()}
        </>
      )}
    </Card>
  );
}
