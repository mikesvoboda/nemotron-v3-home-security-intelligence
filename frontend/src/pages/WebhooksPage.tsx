/**
 * WebhooksPage - Webhook Management Page
 *
 * Provides a comprehensive interface for managing outbound webhooks.
 * Features:
 * - Health summary dashboard
 * - Webhook list with status indicators
 * - Create/edit webhook modal
 * - Delivery history view
 * - Test webhook functionality
 *
 * @module pages/WebhooksPage
 * @see NEM-3624 - Webhook Management Feature
 */

import { AlertTriangle, Plus, RefreshCw, Webhook as WebhookIcon } from 'lucide-react';
import { useCallback, useState } from 'react';

import AnimatedModal from '../components/common/AnimatedModal';
import Button from '../components/common/Button';
import { FeatureErrorBoundary } from '../components/common/FeatureErrorBoundary';
import ResponsiveModal from '../components/common/ResponsiveModal';
import {
  WebhookHealthCard,
  WebhookList,
  WebhookForm,
  WebhookDeliveryHistory,
  WebhookTestModal,
} from '../components/webhooks';
import {
  useWebhookList,
  useWebhookHealth,
  useWebhookDeliveries,
  useCreateWebhook,
  useUpdateWebhook,
  useDeleteWebhook,
  useTestWebhook,
  useToggleWebhook,
  useRetryDelivery,
} from '../hooks/useWebhooks';

import type {
  Webhook,
  WebhookCreate,
  WebhookUpdate,
  WebhookEventType,
} from '../types/webhook';

// ============================================================================
// Types
// ============================================================================

type ModalMode = 'create' | 'edit' | 'history' | null;

// ============================================================================
// Constants
// ============================================================================

const PAGE_SIZE = 20;

// ============================================================================
// Main Component
// ============================================================================

/**
 * WebhooksPage component for webhook management
 */
function WebhooksPageContent() {
  // ============================================================================
  // State
  // ============================================================================

  // Modal state
  const [modalMode, setModalMode] = useState<ModalMode>(null);
  const [selectedWebhook, setSelectedWebhook] = useState<Webhook | null>(null);
  const [testingWebhook, setTestingWebhook] = useState<Webhook | null>(null);

  // Delivery history pagination
  const [deliveryPage, setDeliveryPage] = useState(0);

  // Form error state
  const [formError, setFormError] = useState<string | null>(null);

  // ============================================================================
  // Data Hooks
  // ============================================================================

  // Webhook list
  const {
    webhooks,
    isLoading: isLoadingList,
    isRefetching: isRefetchingList,
    refetch: refetchList,
  } = useWebhookList({
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  // Health summary
  const {
    data: health,
    isLoading: isLoadingHealth,
    isRefetching: isRefetchingHealth,
    refetch: refetchHealth,
  } = useWebhookHealth({
    refetchInterval: 30000,
  });

  // Deliveries (only when viewing history)
  const webhookIdForDeliveries = modalMode === 'history' ? selectedWebhook?.id : undefined;
  const {
    deliveries,
    total: deliveryTotal,
    hasMore: hasMoreDeliveries,
    isLoading: isLoadingDeliveries,
    isRefetching: isRefetchingDeliveries,
    refetch: refetchDeliveries,
  } = useWebhookDeliveries(webhookIdForDeliveries ?? '', {
    enabled: Boolean(webhookIdForDeliveries),
    limit: PAGE_SIZE,
    offset: deliveryPage * PAGE_SIZE,
    refetchInterval: 10000, // Refresh every 10 seconds when viewing
  });

  // Mutations
  const { createWebhook, isLoading: isCreating, error: createError } = useCreateWebhook();
  const { updateWebhook, isLoading: isUpdating, error: updateError } = useUpdateWebhook();
  const { deleteWebhook } = useDeleteWebhook();
  const { testWebhook } = useTestWebhook();
  const { toggleWebhook, isLoading: isToggling } = useToggleWebhook();
  const { retryDelivery } = useRetryDelivery(webhookIdForDeliveries);

  // Track which webhook is being toggled
  const [togglingId, setTogglingId] = useState<string | null>(null);
  const [retryingId, setRetryingId] = useState<string | null>(null);

  // ============================================================================
  // Handlers
  // ============================================================================

  // Refresh all data
  const handleRefresh = useCallback(() => {
    void refetchList();
    void refetchHealth();
  }, [refetchList, refetchHealth]);

  // Open create modal
  const handleOpenCreate = useCallback(() => {
    setSelectedWebhook(null);
    setFormError(null);
    setModalMode('create');
  }, []);

  // Open edit modal
  const handleOpenEdit = useCallback((webhook: Webhook) => {
    setSelectedWebhook(webhook);
    setFormError(null);
    setModalMode('edit');
  }, []);

  // Open history modal
  const handleViewHistory = useCallback((webhook: Webhook) => {
    setSelectedWebhook(webhook);
    setDeliveryPage(0);
    setModalMode('history');
  }, []);

  // Close modal
  const handleCloseModal = useCallback(() => {
    setModalMode(null);
    setSelectedWebhook(null);
    setFormError(null);
  }, []);

  // Open test modal
  const handleOpenTest = useCallback((webhook: Webhook) => {
    setTestingWebhook(webhook);
  }, []);

  // Close test modal
  const handleCloseTest = useCallback(() => {
    setTestingWebhook(null);
  }, []);

  // Submit form (create or update)
  const handleSubmit = useCallback(
    async (data: WebhookCreate | WebhookUpdate) => {
      setFormError(null);
      try {
        if (modalMode === 'create') {
          await createWebhook(data as WebhookCreate);
        } else if (modalMode === 'edit' && selectedWebhook) {
          await updateWebhook(selectedWebhook.id, data as WebhookUpdate);
        }
        handleCloseModal();
      } catch (err) {
        setFormError(err instanceof Error ? err.message : 'An error occurred');
      }
    },
    [modalMode, selectedWebhook, createWebhook, updateWebhook, handleCloseModal]
  );

  // Delete webhook
  const handleDelete = useCallback(
    async (webhook: Webhook) => {
      if (!window.confirm(`Are you sure you want to delete "${webhook.name}"?`)) {
        return;
      }
      try {
        await deleteWebhook(webhook.id);
      } catch (err) {
        console.error('Failed to delete webhook:', err);
      }
    },
    [deleteWebhook]
  );

  // Toggle webhook enabled state
  const handleToggle = useCallback(
    async (id: string, enabled: boolean) => {
      setTogglingId(id);
      try {
        await toggleWebhook(id, enabled);
      } catch (err) {
        console.error('Failed to toggle webhook:', err);
      } finally {
        setTogglingId(null);
      }
    },
    [toggleWebhook]
  );

  // Test webhook
  const handleTest = useCallback(
    async (webhookId: string, eventType: WebhookEventType) => {
      return testWebhook(webhookId, { event_type: eventType });
    },
    [testWebhook]
  );

  // Retry delivery
  const handleRetry = useCallback(
    async (deliveryId: string) => {
      setRetryingId(deliveryId);
      try {
        await retryDelivery(deliveryId);
        void refetchDeliveries();
      } catch (err) {
        console.error('Failed to retry delivery:', err);
      } finally {
        setRetryingId(null);
      }
    },
    [retryDelivery, refetchDeliveries]
  );

  // Handle delivery page change
  const handleDeliveryPageChange = useCallback((page: number) => {
    setDeliveryPage(page);
  }, []);

  // ============================================================================
  // Render
  // ============================================================================

  return (
    <div className="min-h-screen bg-[#121212] p-6" data-testid="webhooks-page">
      <div className="mx-auto max-w-[1400px]">
        {/* Header */}
        <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <WebhookIcon className="h-8 w-8 text-[#76B900]" />
              <h1 className="text-3xl font-bold text-white">Webhooks</h1>
            </div>
            <p className="mt-2 text-gray-400">
              Configure outbound webhooks to receive real-time notifications
            </p>
          </div>

          <div className="flex gap-2">
            <Button
              variant="ghost"
              size="sm"
              leftIcon={<RefreshCw className={`h-4 w-4 ${isRefetchingList ? 'animate-spin' : ''}`} />}
              onClick={handleRefresh}
              disabled={isRefetchingList || isRefetchingHealth}
            >
              Refresh
            </Button>
            <Button
              variant="primary"
              size="sm"
              leftIcon={<Plus className="h-4 w-4" />}
              onClick={handleOpenCreate}
            >
              Add Webhook
            </Button>
          </div>
        </div>

        {/* Health Summary */}
        <WebhookHealthCard
          health={health}
          isLoading={isLoadingHealth}
          isRefetching={isRefetchingHealth}
          className="mb-8"
        />

        {/* Webhook List */}
        <WebhookList
          webhooks={webhooks}
          isLoading={isLoadingList}
          onToggle={(id, enabled) => void handleToggle(id, enabled)}
          onEdit={handleOpenEdit}
          onDelete={(webhook) => void handleDelete(webhook)}
          onTest={handleOpenTest}
          onViewHistory={handleViewHistory}
          isToggling={isToggling}
          togglingId={togglingId}
        />

        {/* Create/Edit Modal */}
        <ResponsiveModal
          isOpen={modalMode === 'create' || modalMode === 'edit'}
          onClose={handleCloseModal}
          size="lg"
          closeOnBackdropClick={false}
        >
          <div className="p-6">
            <h2 className="mb-6 text-xl font-semibold text-white">
              {modalMode === 'create' ? 'Create Webhook' : 'Edit Webhook'}
            </h2>
            <WebhookForm
              webhook={modalMode === 'edit' ? selectedWebhook ?? undefined : undefined}
              onSubmit={handleSubmit}
              onCancel={handleCloseModal}
              isSubmitting={isCreating || isUpdating}
              apiError={formError || createError?.message || updateError?.message}
              onClearApiError={() => setFormError(null)}
            />
          </div>
        </ResponsiveModal>

        {/* Delivery History Modal */}
        <AnimatedModal
          isOpen={modalMode === 'history'}
          onClose={handleCloseModal}
          size="xl"
          variant="slideUp"
          modalName="webhook-history"
        >
          {selectedWebhook && (
            <WebhookDeliveryHistory
              webhookName={selectedWebhook.name}
              deliveries={deliveries}
              total={deliveryTotal}
              hasMore={hasMoreDeliveries}
              page={deliveryPage}
              pageSize={PAGE_SIZE}
              isLoading={isLoadingDeliveries}
              isRefetching={isRefetchingDeliveries}
              onPageChange={handleDeliveryPageChange}
              onRetry={(id) => void handleRetry(id)}
              onRefresh={() => void refetchDeliveries()}
              retryingId={retryingId}
              onClose={handleCloseModal}
            />
          )}
        </AnimatedModal>

        {/* Test Modal */}
        <WebhookTestModal
          webhook={testingWebhook}
          isOpen={testingWebhook !== null}
          onClose={handleCloseTest}
          onTest={handleTest}
        />
      </div>
    </div>
  );
}

// ============================================================================
// Error Boundary Wrapper
// ============================================================================

/**
 * WebhooksPage with error boundary wrapper
 */
export default function WebhooksPage() {
  return (
    <FeatureErrorBoundary
      feature="Webhooks"
      fallback={
        <div className="flex min-h-[400px] flex-col items-center justify-center rounded-lg border border-red-500/30 bg-red-900/20 p-8 text-center">
          <AlertTriangle className="mb-4 h-12 w-12 text-red-400" />
          <h3 className="mb-2 text-lg font-semibold text-red-400">Webhooks Unavailable</h3>
          <p className="max-w-md text-sm text-gray-400">
            Unable to load webhook management. Please refresh the page or try again later.
          </p>
        </div>
      }
    >
      <WebhooksPageContent />
    </FeatureErrorBoundary>
  );
}
