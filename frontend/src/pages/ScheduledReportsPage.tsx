/**
 * ScheduledReportsPage - Scheduled Report Management Page
 *
 * Provides a comprehensive interface for managing scheduled reports.
 * Features:
 * - Report list with status indicators
 * - Create/edit report modal
 * - Enable/disable toggle
 * - Manual trigger functionality
 * - Delete confirmation
 *
 * @module pages/ScheduledReportsPage
 * @see NEM-3667 - Scheduled Reports Frontend UI
 */

import {
  AlertTriangle,
  Calendar,
  CheckCircle,
  Clock,
  FileText,
  Loader2,
  Pause,
  Play,
  Plus,
  RefreshCw,
  Trash2,
  XCircle,
} from 'lucide-react';
import { useCallback, useState } from 'react';

import Button from '../components/common/Button';
import EmptyState from '../components/common/EmptyState';
import { FeatureErrorBoundary } from '../components/common/FeatureErrorBoundary';
import LoadingSpinner from '../components/common/LoadingSpinner';
import ResponsiveModal from '../components/common/ResponsiveModal';
import { ScheduledReportForm } from '../components/reports';
import {
  useScheduledReportsQuery,
  useCreateScheduledReportMutation,
  useUpdateScheduledReportMutation,
  useDeleteScheduledReportMutation,
  useTriggerScheduledReportMutation,
} from '../hooks/useScheduledReports';
import {
  FREQUENCY_LABELS,
  FORMAT_LABELS,
  getScheduleDescription,
} from '../types/scheduledReport';

import type {
  ScheduledReport,
  ScheduledReportCreate,
  ScheduledReportUpdate,
} from '../types/scheduledReport';

// ============================================================================
// Types
// ============================================================================

type ModalMode = 'create' | 'edit' | null;

// ============================================================================
// Helper Components
// ============================================================================

/**
 * StatusBadge displays the enabled/disabled status of a report.
 */
function StatusBadge({ enabled }: { enabled: boolean }) {
  if (enabled) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-green-500/30 bg-green-500/20 px-2.5 py-1 text-xs font-medium text-green-400">
        <CheckCircle className="h-3.5 w-3.5" />
        Enabled
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-gray-500/30 bg-gray-500/20 px-2.5 py-1 text-xs font-medium text-gray-400">
      <Pause className="h-3.5 w-3.5" />
      Disabled
    </span>
  );
}

/**
 * FormatBadge displays the output format of a report.
 */
function FormatBadge({ format }: { format: string }) {
  const colorClass = {
    pdf: 'border-red-500/30 bg-red-500/20 text-red-400',
    csv: 'border-green-500/30 bg-green-500/20 text-green-400',
    json: 'border-blue-500/30 bg-blue-500/20 text-blue-400',
  }[format] ?? 'border-gray-500/30 bg-gray-500/20 text-gray-400';

  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${colorClass}`}
    >
      {FORMAT_LABELS[format as keyof typeof FORMAT_LABELS] ?? format.toUpperCase()}
    </span>
  );
}

/**
 * Format a date for display.
 */
function formatDate(dateStr: string | null): string {
  if (!dateStr) return 'Never';
  return new Date(dateStr).toLocaleString();
}

// ============================================================================
// Report Card Component
// ============================================================================

interface ReportCardProps {
  report: ScheduledReport;
  onEdit: (report: ScheduledReport) => void;
  onDelete: (report: ScheduledReport) => void;
  onToggle: (report: ScheduledReport) => void;
  onTrigger: (report: ScheduledReport) => void;
  isToggling: boolean;
  isTriggering: boolean;
}

function ReportCard({
  report,
  onEdit,
  onDelete,
  onToggle,
  onTrigger,
  isToggling,
  isTriggering,
}: ReportCardProps) {
  return (
    <div
      className="rounded-lg border border-gray-700 bg-gray-800/50 p-4"
      data-testid={`report-card-${report.id}`}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1">
          {/* Header */}
          <div className="flex items-center gap-3">
            <FileText className="h-5 w-5 text-[#76B900]" />
            <h3 className="font-semibold text-white">{report.name}</h3>
            <StatusBadge enabled={report.enabled} />
            <FormatBadge format={report.format} />
          </div>

          {/* Schedule Info */}
          <div className="mt-3 flex flex-wrap items-center gap-4 text-sm text-gray-400">
            <div className="flex items-center gap-1.5">
              <Calendar className="h-4 w-4" />
              <span>{FREQUENCY_LABELS[report.frequency]}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Clock className="h-4 w-4" />
              <span>{getScheduleDescription(report)}</span>
            </div>
            <span className="text-gray-600">|</span>
            <span>{report.timezone}</span>
          </div>

          {/* Run Info */}
          <div className="mt-2 flex flex-wrap gap-4 text-xs text-gray-500">
            <span>
              Last run: <span className="text-gray-400">{formatDate(report.last_run_at)}</span>
            </span>
            <span>
              Next run: <span className="text-gray-400">{formatDate(report.next_run_at)}</span>
            </span>
          </div>

          {/* Recipients */}
          {report.email_recipients && report.email_recipients.length > 0 && (
            <div className="mt-2 text-xs text-gray-500">
              Recipients: {report.email_recipients.join(', ')}
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            leftIcon={
              isTriggering ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Play className="h-4 w-4" />
              )
            }
            onClick={() => onTrigger(report)}
            disabled={isTriggering || !report.enabled}
            title={report.enabled ? 'Run report now' : 'Enable report to trigger'}
          >
            Run Now
          </Button>
          <Button
            variant="ghost"
            size="sm"
            leftIcon={
              isToggling ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : report.enabled ? (
                <Pause className="h-4 w-4" />
              ) : (
                <CheckCircle className="h-4 w-4" />
              )
            }
            onClick={() => onToggle(report)}
            disabled={isToggling}
          >
            {report.enabled ? 'Disable' : 'Enable'}
          </Button>
          <Button variant="ghost" size="sm" onClick={() => onEdit(report)}>
            Edit
          </Button>
          <Button
            variant="ghost"
            size="sm"
            leftIcon={<Trash2 className="h-4 w-4" />}
            onClick={() => onDelete(report)}
            className="text-red-400 hover:text-red-300"
          >
            Delete
          </Button>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * ScheduledReportsPage component for scheduled report management
 */
function ScheduledReportsPageContent() {
  // ============================================================================
  // State
  // ============================================================================

  // Modal state
  const [modalMode, setModalMode] = useState<ModalMode>(null);
  const [selectedReport, setSelectedReport] = useState<ScheduledReport | null>(null);

  // Form error state
  const [formError, setFormError] = useState<string | null>(null);

  // Track which report is being toggled/triggered
  const [togglingId, setTogglingId] = useState<number | null>(null);
  const [triggeringId, setTriggeringId] = useState<number | null>(null);

  // ============================================================================
  // Data Hooks
  // ============================================================================

  // Report list
  const {
    reports,
    isLoading: isLoadingList,
    isRefetching: isRefetchingList,
    error: listError,
    refetch: refetchList,
  } = useScheduledReportsQuery({
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  // Mutations
  const { createReport, isLoading: isCreating, error: createError } =
    useCreateScheduledReportMutation();
  const { updateReport, isLoading: isUpdating, error: updateError } =
    useUpdateScheduledReportMutation();
  const { deleteReport } = useDeleteScheduledReportMutation();
  const { triggerReport } = useTriggerScheduledReportMutation();

  // ============================================================================
  // Handlers
  // ============================================================================

  // Refresh data
  const handleRefresh = useCallback(() => {
    void refetchList();
  }, [refetchList]);

  // Open create modal
  const handleOpenCreate = useCallback(() => {
    setSelectedReport(null);
    setFormError(null);
    setModalMode('create');
  }, []);

  // Open edit modal
  const handleOpenEdit = useCallback((report: ScheduledReport) => {
    setSelectedReport(report);
    setFormError(null);
    setModalMode('edit');
  }, []);

  // Close modal
  const handleCloseModal = useCallback(() => {
    setModalMode(null);
    setSelectedReport(null);
    setFormError(null);
  }, []);

  // Submit form (create or update)
  const handleSubmit = useCallback(
    async (data: ScheduledReportCreate | ScheduledReportUpdate) => {
      setFormError(null);
      try {
        if (modalMode === 'create') {
          await createReport(data as ScheduledReportCreate);
        } else if (modalMode === 'edit' && selectedReport) {
          await updateReport(selectedReport.id, data as ScheduledReportUpdate);
        }
        handleCloseModal();
      } catch (err) {
        setFormError(err instanceof Error ? err.message : 'An error occurred');
      }
    },
    [modalMode, selectedReport, createReport, updateReport, handleCloseModal]
  );

  // Delete report
  const handleDelete = useCallback(
    async (report: ScheduledReport) => {
      if (!window.confirm(`Are you sure you want to delete "${report.name}"?`)) {
        return;
      }
      try {
        await deleteReport(report.id);
      } catch (err) {
        console.error('Failed to delete report:', err);
      }
    },
    [deleteReport]
  );

  // Toggle report enabled state
  const handleToggle = useCallback(
    async (report: ScheduledReport) => {
      setTogglingId(report.id);
      try {
        await updateReport(report.id, { enabled: !report.enabled });
      } catch (err) {
        console.error('Failed to toggle report:', err);
      } finally {
        setTogglingId(null);
      }
    },
    [updateReport]
  );

  // Trigger report
  const handleTrigger = useCallback(
    async (report: ScheduledReport) => {
      setTriggeringId(report.id);
      try {
        await triggerReport(report.id);
      } catch (err) {
        console.error('Failed to trigger report:', err);
      } finally {
        setTriggeringId(null);
      }
    },
    [triggerReport]
  );

  // ============================================================================
  // Render
  // ============================================================================

  // Loading state
  if (isLoadingList) {
    return (
      <div className="flex min-h-[400px] items-center justify-center" data-testid="loading-spinner">
        <LoadingSpinner />
      </div>
    );
  }

  // Error state
  if (listError) {
    return (
      <div className="p-6" data-testid="scheduled-reports-page">
        <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-4">
          <div className="flex items-center gap-2 text-red-400">
            <XCircle className="h-5 w-5" />
            <span className="font-medium">Failed to load scheduled reports</span>
          </div>
          <p className="mt-2 text-sm text-red-300">{listError.message}</p>
          <button
            onClick={handleRefresh}
            className="mt-3 rounded bg-red-500/20 px-3 py-1 text-sm text-red-300 hover:bg-red-500/30"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#121212] p-6" data-testid="scheduled-reports-page">
      <div className="mx-auto max-w-[1400px]">
        {/* Header */}
        <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <Calendar className="h-8 w-8 text-[#76B900]" />
              <h1 className="text-3xl font-bold text-white">Scheduled Reports</h1>
            </div>
            <p className="mt-2 text-gray-400">
              Configure automated reports to be generated and delivered on a schedule
            </p>
          </div>

          <div className="flex gap-2">
            <Button
              variant="ghost"
              size="sm"
              leftIcon={
                <RefreshCw className={`h-4 w-4 ${isRefetchingList ? 'animate-spin' : ''}`} />
              }
              onClick={handleRefresh}
              disabled={isRefetchingList}
            >
              Refresh
            </Button>
            <Button
              variant="primary"
              size="sm"
              leftIcon={<Plus className="h-4 w-4" />}
              onClick={handleOpenCreate}
            >
              Add Report
            </Button>
          </div>
        </div>

        {/* Report List */}
        {reports.length === 0 ? (
          <EmptyState
            icon={Calendar}
            title="No scheduled reports"
            description="Create a scheduled report to automatically generate and deliver reports on a recurring schedule."
            variant="muted"
            actions={[
              {
                label: 'Create Your First Report',
                onClick: handleOpenCreate,
                variant: 'primary',
              },
            ]}
          />
        ) : (
          <div className="space-y-4">
            {reports.map((report) => (
              <ReportCard
                key={report.id}
                report={report}
                onEdit={handleOpenEdit}
                onDelete={(r) => void handleDelete(r)}
                onToggle={(r) => void handleToggle(r)}
                onTrigger={(r) => void handleTrigger(r)}
                isToggling={togglingId === report.id}
                isTriggering={triggeringId === report.id}
              />
            ))}
          </div>
        )}

        {/* Create/Edit Modal */}
        <ResponsiveModal
          isOpen={modalMode === 'create' || modalMode === 'edit'}
          onClose={handleCloseModal}
          size="lg"
          closeOnBackdropClick={false}
        >
          <div className="p-6">
            <h2 className="mb-6 text-xl font-semibold text-white">
              {modalMode === 'create' ? 'Create Scheduled Report' : 'Edit Scheduled Report'}
            </h2>
            <ScheduledReportForm
              report={modalMode === 'edit' ? selectedReport ?? undefined : undefined}
              onSubmit={handleSubmit}
              onCancel={handleCloseModal}
              isSubmitting={isCreating || isUpdating}
              apiError={formError || createError?.message || updateError?.message}
              onClearApiError={() => setFormError(null)}
            />
          </div>
        </ResponsiveModal>
      </div>
    </div>
  );
}

// ============================================================================
// Error Boundary Wrapper
// ============================================================================

/**
 * ScheduledReportsPage with error boundary wrapper
 */
export default function ScheduledReportsPage() {
  return (
    <FeatureErrorBoundary
      feature="Scheduled Reports"
      fallback={
        <div className="flex min-h-[400px] flex-col items-center justify-center rounded-lg border border-red-500/30 bg-red-900/20 p-8 text-center">
          <AlertTriangle className="mb-4 h-12 w-12 text-red-400" />
          <h3 className="mb-2 text-lg font-semibold text-red-400">Scheduled Reports Unavailable</h3>
          <p className="max-w-md text-sm text-gray-400">
            Unable to load scheduled reports management. Please refresh the page or try again later.
          </p>
        </div>
      }
    >
      <ScheduledReportsPageContent />
    </FeatureErrorBoundary>
  );
}
