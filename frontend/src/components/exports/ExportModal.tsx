/**
 * ExportModal Component
 *
 * Modal dialog for initiating and tracking export jobs.
 * Provides:
 * - Export type and format selection
 * - Filter options
 * - Progress tracking via ExportProgress component
 * - Success/error feedback
 *
 * @see NEM-2386
 */

import { Button, Select, SelectItem, Card, Title, Text } from '@tremor/react';
import { AlertCircle, Download, FileSpreadsheet, FileText, Loader2, X } from 'lucide-react';
import { useState, useEffect, useCallback } from 'react';

import ExportProgress from './ExportProgress';
import { useDateRangeState } from '../../hooks/useDateRangeState';
import { startExportJob, fetchCameras } from '../../services/api';

import type { Camera } from '../../services/api';
import type { ExportJobCreateParams, ExportType, ExportFormat } from '../../types/export';

export interface ExportModalProps {
  /** Whether the modal is open */
  isOpen: boolean;
  /** Callback to close the modal */
  onClose: () => void;
  /** Pre-populate filters */
  initialFilters?: Partial<ExportJobCreateParams>;
  /** Callback when export completes */
  onExportComplete?: (success: boolean) => void;
}

/**
 * Modal for initiating export jobs with progress tracking.
 */
export default function ExportModal({
  isOpen,
  onClose,
  initialFilters,
  onExportComplete,
}: ExportModalProps) {
  // Date range state WITHOUT URL persistence (modal shouldn't affect URL)
  const {
    range: dateRange,
    apiParams: dateRangeApiParams,
    setCustomRange: setDateRangeCustom,
    reset: resetDateRange,
  } = useDateRangeState({
    defaultPreset: 'all',
    persistToUrl: false,
  });

  // Form state
  const [exportType, setExportType] = useState<ExportType>('events');
  const [exportFormat, setExportFormat] = useState<ExportFormat>('csv');
  const [cameraId, setCameraId] = useState<string>(initialFilters?.camera_id ?? '');
  const [riskLevel, setRiskLevel] = useState<string>(initialFilters?.risk_level ?? '');
  const [reviewed, setReviewed] = useState<string>('');

  // State
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);

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

  // Reset state when modal opens
  useEffect(() => {
    if (isOpen) {
      setError(null);
      setJobId(null);
      // Apply initial filters
      if (initialFilters) {
        setCameraId(initialFilters.camera_id ?? '');
        setRiskLevel(initialFilters.risk_level ?? '');
        // Set custom date range if initial filters have dates
        if (initialFilters.start_date && initialFilters.end_date) {
          const startDate = new Date(initialFilters.start_date);
          const endDate = new Date(initialFilters.end_date);
          setDateRangeCustom(startDate, endDate);
        } else {
          resetDateRange();
        }
      } else {
        resetDateRange();
      }
    }
  }, [isOpen, initialFilters, setDateRangeCustom, resetDateRange]);

  // Handle custom date range change
  const handleStartDateChange = useCallback(
    (value: string) => {
      if (value) {
        const startDate = new Date(value + 'T00:00:00');
        const endDate = dateRange.endDate;
        setDateRangeCustom(startDate, endDate);
      }
    },
    [dateRange.endDate, setDateRangeCustom]
  );

  const handleEndDateChange = useCallback(
    (value: string) => {
      if (value) {
        const startDate = dateRange.startDate;
        const endDate = new Date(value + 'T23:59:59');
        setDateRangeCustom(startDate, endDate);
      }
    },
    [dateRange.startDate, setDateRangeCustom]
  );

  // Handle form submission
  const handleStartExport = async () => {
    setLoading(true);
    setError(null);

    try {
      const params: ExportJobCreateParams = {
        export_type: exportType,
        export_format: exportFormat,
        camera_id: cameraId || null,
        risk_level: riskLevel || null,
        start_date: dateRangeApiParams.start_date || null,
        end_date: dateRangeApiParams.end_date || null,
        reviewed: reviewed === '' ? null : reviewed === 'true',
      };

      const response = await startExportJob(params);
      setJobId(response.job_id);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to start export';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  // Handle export completion
  const handleExportComplete = () => {
    if (onExportComplete) {
      onExportComplete(true);
    }
  };

  // Handle export error
  const handleExportError = (errorMessage: string) => {
    setError(errorMessage);
    if (onExportComplete) {
      onExportComplete(false);
    }
  };

  // Handle export cancel
  const handleExportCancel = () => {
    setJobId(null);
  };

  // Handle close
  const handleClose = () => {
    // Don't allow closing during active export
    if (jobId && !error) {
      return;
    }
    onClose();
  };

  if (!isOpen) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <Card className="mx-4 w-full max-w-lg">
        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <Title>Export Data</Title>
          {!jobId && (
            <button
              onClick={handleClose}
              className="text-gray-400 transition-colors hover:text-gray-600"
              aria-label="Close"
            >
              <X className="h-5 w-5" />
            </button>
          )}
        </div>

        {/* Show progress if job is running */}
        {jobId ? (
          <div>
            <ExportProgress
              jobId={jobId}
              onComplete={handleExportComplete}
              onError={handleExportError}
              onCancel={handleExportCancel}
            />
            <div className="mt-6 flex justify-end gap-3">
              <Button variant="secondary" onClick={handleClose}>
                Close
              </Button>
            </div>
          </div>
        ) : (
          <>
            {/* Export Configuration Form */}
            <div className="space-y-4">
              {/* Export Type */}
              <div>
                <Text className="mb-1">Export Type</Text>
                <Select
                  value={exportType}
                  onValueChange={(val) => setExportType(val as ExportType)}
                >
                  <SelectItem value="events" icon={FileSpreadsheet}>
                    Events
                  </SelectItem>
                  <SelectItem value="alerts" icon={AlertCircle}>
                    Alerts
                  </SelectItem>
                  <SelectItem value="full_backup" icon={Download}>
                    Full Backup
                  </SelectItem>
                </Select>
              </div>

              {/* Export Format */}
              <div>
                <Text className="mb-1">Format</Text>
                <Select
                  value={exportFormat}
                  onValueChange={(val) => setExportFormat(val as ExportFormat)}
                >
                  <SelectItem value="csv" icon={FileSpreadsheet}>
                    CSV
                  </SelectItem>
                  <SelectItem value="json" icon={FileText}>
                    JSON
                  </SelectItem>
                  <SelectItem value="excel" icon={FileSpreadsheet}>
                    Excel
                  </SelectItem>
                  <SelectItem value="zip" icon={Download}>
                    ZIP Archive
                  </SelectItem>
                </Select>
              </div>

              {/* Camera Filter */}
              {exportType === 'events' && (
                <div>
                  <Text className="mb-1">Camera (optional)</Text>
                  <Select value={cameraId} onValueChange={setCameraId} placeholder="All cameras">
                    <SelectItem value="">All cameras</SelectItem>
                    {cameras.map((camera) => (
                      <SelectItem key={camera.id} value={camera.id}>
                        {camera.name || camera.id}
                      </SelectItem>
                    ))}
                  </Select>
                </div>
              )}

              {/* Risk Level Filter */}
              {exportType === 'events' && (
                <div>
                  <Text className="mb-1">Risk Level (optional)</Text>
                  <Select value={riskLevel} onValueChange={setRiskLevel} placeholder="All levels">
                    <SelectItem value="">All levels</SelectItem>
                    <SelectItem value="low">Low</SelectItem>
                    <SelectItem value="medium">Medium</SelectItem>
                    <SelectItem value="high">High</SelectItem>
                    <SelectItem value="critical">Critical</SelectItem>
                  </Select>
                </div>
              )}

              {/* Date Range */}
              {exportType === 'events' && (
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Text className="mb-1">Start Date (optional)</Text>
                    <input
                      type="date"
                      value={dateRangeApiParams.start_date || ''}
                      onChange={(e) => handleStartDateChange(e.target.value)}
                      className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    />
                  </div>
                  <div>
                    <Text className="mb-1">End Date (optional)</Text>
                    <input
                      type="date"
                      value={dateRangeApiParams.end_date || ''}
                      onChange={(e) => handleEndDateChange(e.target.value)}
                      className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    />
                  </div>
                </div>
              )}

              {/* Reviewed Filter */}
              {exportType === 'events' && (
                <div>
                  <Text className="mb-1">Review Status (optional)</Text>
                  <Select value={reviewed} onValueChange={setReviewed} placeholder="All events">
                    <SelectItem value="">All events</SelectItem>
                    <SelectItem value="true">Reviewed only</SelectItem>
                    <SelectItem value="false">Unreviewed only</SelectItem>
                  </Select>
                </div>
              )}
            </div>

            {/* Error display */}
            {error && (
              <div className="mt-4 flex items-center gap-2 text-sm text-red-500">
                <AlertCircle className="h-4 w-4" />
                <span>{error}</span>
              </div>
            )}

            {/* Actions */}
            <div className="mt-6 flex justify-end gap-3">
              <Button variant="secondary" onClick={handleClose}>
                Cancel
              </Button>
              <Button
                icon={loading ? Loader2 : Download}
                onClick={() => void handleStartExport()}
                loading={loading}
              >
                Start Export
              </Button>
            </div>
          </>
        )}
      </Card>
    </div>
  );
}
