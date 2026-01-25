/**
 * TanStack Query Hooks for Webhook Management
 *
 * This module provides hooks for fetching and mutating webhook data
 * using TanStack Query. It includes:
 *
 * Queries:
 * - useWebhookList: Fetch list of webhooks
 * - useWebhook: Fetch single webhook by ID
 * - useWebhookDeliveries: Fetch delivery history for a webhook
 * - useWebhookHealth: Fetch webhook health summary
 *
 * Mutations:
 * - useCreateWebhook: Create a new webhook
 * - useUpdateWebhook: Update an existing webhook
 * - useDeleteWebhook: Delete a webhook
 * - useTestWebhook: Test a webhook with sample payload
 * - useToggleWebhook: Enable/disable a webhook
 * - useRetryDelivery: Retry a failed delivery
 *
 * Benefits:
 * - Automatic request deduplication across components
 * - Built-in caching with automatic cache invalidation
 * - Proper error handling
 * - Optimistic updates where appropriate
 *
 * @module hooks/useWebhooks
 * @see NEM-3624 - Webhook Management Feature
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

import { DEFAULT_STALE_TIME, REALTIME_STALE_TIME } from '../services/queryClient';
import * as webhookApi from '../services/webhookApi';

import type {
  Webhook,
  WebhookCreate,
  WebhookUpdate,
  WebhookListResponse,
  WebhookDeliveryListResponse,
  WebhookDeliveryQueryParams,
  WebhookTestRequest,
  WebhookTestResponse,
  WebhookHealthSummary,
  WebhookDelivery,
} from '../types/webhook';

// Re-export types for convenience
export type {
  Webhook,
  WebhookCreate,
  WebhookUpdate,
  WebhookListResponse,
  WebhookDeliveryListResponse,
  WebhookTestResponse,
  WebhookHealthSummary,
  WebhookDelivery,
} from '../types/webhook';

// ============================================================================
// Query Keys
// ============================================================================

/**
 * Query keys for webhook-related queries.
 * Follows the hierarchical pattern for cache invalidation.
 *
 * @example
 * ```typescript
 * // Invalidate all webhook queries
 * queryClient.invalidateQueries({ queryKey: WEBHOOK_QUERY_KEYS.all });
 *
 * // Invalidate specific webhook
 * queryClient.invalidateQueries({ queryKey: WEBHOOK_QUERY_KEYS.detail('123...') });
 *
 * // Invalidate deliveries for a webhook
 * queryClient.invalidateQueries({ queryKey: WEBHOOK_QUERY_KEYS.deliveries('123...') });
 * ```
 */
export const WEBHOOK_QUERY_KEYS = {
  /** Base key for all webhook queries - use for bulk invalidation */
  all: ['webhooks'] as const,
  /** Webhook list */
  list: ['webhooks', 'list'] as const,
  /** Single webhook by ID */
  detail: (id: string) => ['webhooks', 'detail', id] as const,
  /** Deliveries for a webhook */
  deliveries: (webhookId: string) => ['webhooks', 'deliveries', webhookId] as const,
  /** Health summary */
  health: ['webhooks', 'health'] as const,
} as const;

// ============================================================================
// useWebhookList - Fetch list of webhooks
// ============================================================================

/**
 * Options for configuring the useWebhookList hook.
 */
export interface UseWebhookListOptions {
  /**
   * Whether to enable the query.
   * @default true
   */
  enabled?: boolean;

  /**
   * Custom stale time in milliseconds.
   * @default DEFAULT_STALE_TIME (30 seconds)
   */
  staleTime?: number;

  /**
   * Refetch interval in milliseconds.
   * @default false
   */
  refetchInterval?: number | false;
}

/**
 * Return type for the useWebhookList hook.
 */
export interface UseWebhookListReturn {
  /** Webhook list response data */
  data: WebhookListResponse | undefined;
  /** List of webhooks (convenience accessor) */
  webhooks: Webhook[];
  /** Total webhook count */
  total: number;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether a background refetch is in progress */
  isRefetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Hook to fetch list of webhooks using TanStack Query.
 *
 * @param options - Configuration options
 * @returns Webhook list and query state
 *
 * @example
 * ```tsx
 * const { webhooks, isLoading, error } = useWebhookList();
 *
 * if (isLoading) return <Spinner />;
 * if (error) return <Error message={error.message} />;
 *
 * return (
 *   <div>
 *     {webhooks.map(webhook => (
 *       <WebhookCard key={webhook.id} webhook={webhook} />
 *     ))}
 *   </div>
 * );
 * ```
 */
export function useWebhookList(options: UseWebhookListOptions = {}): UseWebhookListReturn {
  const { enabled = true, staleTime = DEFAULT_STALE_TIME, refetchInterval = false } = options;

  const query = useQuery({
    queryKey: WEBHOOK_QUERY_KEYS.list,
    queryFn: webhookApi.listWebhooks,
    enabled,
    staleTime,
    refetchInterval,
    retry: 1,
  });

  return {
    data: query.data,
    webhooks: query.data?.webhooks ?? [],
    total: query.data?.total ?? 0,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    refetch: query.refetch,
  };
}

// ============================================================================
// useWebhook - Fetch single webhook by ID
// ============================================================================

/**
 * Options for configuring the useWebhook hook.
 */
export interface UseWebhookOptions {
  /**
   * Whether to enable the query.
   * @default true
   */
  enabled?: boolean;

  /**
   * Custom stale time in milliseconds.
   * @default DEFAULT_STALE_TIME (30 seconds)
   */
  staleTime?: number;
}

/**
 * Return type for the useWebhook hook.
 */
export interface UseWebhookReturn {
  /** Webhook data */
  data: Webhook | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Hook to fetch a single webhook by ID using TanStack Query.
 *
 * @param id - Webhook UUID
 * @param options - Configuration options
 * @returns Webhook data and query state
 *
 * @example
 * ```tsx
 * const { data: webhook, isLoading } = useWebhook('123...');
 *
 * if (isLoading) return <Spinner />;
 *
 * return (
 *   <div>
 *     <h1>{webhook?.name}</h1>
 *     <p>URL: {webhook?.url}</p>
 *   </div>
 * );
 * ```
 */
export function useWebhook(id: string, options: UseWebhookOptions = {}): UseWebhookReturn {
  const { enabled = true, staleTime = DEFAULT_STALE_TIME } = options;

  const query = useQuery({
    queryKey: WEBHOOK_QUERY_KEYS.detail(id),
    queryFn: () => webhookApi.getWebhook(id),
    enabled: enabled && Boolean(id),
    staleTime,
    retry: 1,
  });

  return {
    data: query.data,
    isLoading: query.isLoading,
    error: query.error,
    refetch: query.refetch,
  };
}

// ============================================================================
// useWebhookDeliveries - Fetch delivery history for a webhook
// ============================================================================

/**
 * Options for configuring the useWebhookDeliveries hook.
 */
export interface UseWebhookDeliveriesOptions extends WebhookDeliveryQueryParams {
  /**
   * Whether to enable the query.
   * @default true
   */
  enabled?: boolean;

  /**
   * Custom stale time in milliseconds.
   * @default REALTIME_STALE_TIME (5 seconds)
   */
  staleTime?: number;

  /**
   * Refetch interval in milliseconds.
   * @default false
   */
  refetchInterval?: number | false;
}

/**
 * Return type for the useWebhookDeliveries hook.
 */
export interface UseWebhookDeliveriesReturn {
  /** Delivery list response data */
  data: WebhookDeliveryListResponse | undefined;
  /** List of deliveries (convenience accessor) */
  deliveries: WebhookDelivery[];
  /** Total delivery count */
  total: number;
  /** Whether more deliveries are available */
  hasMore: boolean;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether a background refetch is in progress */
  isRefetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Hook to fetch delivery history for a webhook using TanStack Query.
 *
 * @param webhookId - Webhook UUID
 * @param options - Configuration options including pagination
 * @returns Delivery list and query state
 *
 * @example
 * ```tsx
 * const { deliveries, isLoading, hasMore } = useWebhookDeliveries('123...', {
 *   limit: 20,
 *   offset: 0,
 * });
 *
 * if (isLoading) return <Spinner />;
 *
 * return (
 *   <div>
 *     {deliveries.map(delivery => (
 *       <DeliveryRow key={delivery.id} delivery={delivery} />
 *     ))}
 *     {hasMore && <LoadMoreButton />}
 *   </div>
 * );
 * ```
 */
export function useWebhookDeliveries(
  webhookId: string,
  options: UseWebhookDeliveriesOptions = {}
): UseWebhookDeliveriesReturn {
  const {
    enabled = true,
    staleTime = REALTIME_STALE_TIME,
    refetchInterval = false,
    limit,
    offset,
  } = options;

  const query = useQuery({
    queryKey: [...WEBHOOK_QUERY_KEYS.deliveries(webhookId), { limit, offset }],
    queryFn: () => webhookApi.getDeliveries(webhookId, { limit, offset }),
    enabled: enabled && Boolean(webhookId),
    staleTime,
    refetchInterval,
    retry: 1,
  });

  return {
    data: query.data,
    deliveries: query.data?.deliveries ?? [],
    total: query.data?.total ?? 0,
    hasMore: query.data?.has_more ?? false,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    refetch: query.refetch,
  };
}

// ============================================================================
// useWebhookHealth - Fetch webhook health summary
// ============================================================================

/**
 * Options for configuring the useWebhookHealth hook.
 */
export interface UseWebhookHealthOptions {
  /**
   * Whether to enable the query.
   * @default true
   */
  enabled?: boolean;

  /**
   * Custom stale time in milliseconds.
   * @default REALTIME_STALE_TIME (5 seconds)
   */
  staleTime?: number;

  /**
   * Refetch interval in milliseconds.
   * @default false
   */
  refetchInterval?: number | false;
}

/**
 * Return type for the useWebhookHealth hook.
 */
export interface UseWebhookHealthReturn {
  /** Health summary data */
  data: WebhookHealthSummary | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether a background refetch is in progress */
  isRefetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Hook to fetch webhook health summary using TanStack Query.
 *
 * @param options - Configuration options
 * @returns Health summary and query state
 *
 * @example
 * ```tsx
 * const { data: health, isLoading } = useWebhookHealth({
 *   refetchInterval: 30000, // Refresh every 30 seconds
 * });
 *
 * if (isLoading) return <Spinner />;
 *
 * return (
 *   <HealthDashboard
 *     healthy={health?.healthy_webhooks ?? 0}
 *     unhealthy={health?.unhealthy_webhooks ?? 0}
 *     total={health?.total_webhooks ?? 0}
 *   />
 * );
 * ```
 */
export function useWebhookHealth(options: UseWebhookHealthOptions = {}): UseWebhookHealthReturn {
  const { enabled = true, staleTime = REALTIME_STALE_TIME, refetchInterval = false } = options;

  const query = useQuery({
    queryKey: WEBHOOK_QUERY_KEYS.health,
    queryFn: webhookApi.getHealthSummary,
    enabled,
    staleTime,
    refetchInterval,
    retry: 1,
  });

  return {
    data: query.data,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    refetch: query.refetch,
  };
}

// ============================================================================
// useCreateWebhook - Create a new webhook
// ============================================================================

/**
 * Return type for the useCreateWebhook hook.
 */
export interface UseCreateWebhookReturn {
  /** The mutation object */
  mutation: ReturnType<typeof useMutation<Webhook, Error, WebhookCreate>>;
  /** Convenience method to create webhook */
  createWebhook: (data: WebhookCreate) => Promise<Webhook>;
  /** Whether the mutation is in progress */
  isLoading: boolean;
  /** Error if the mutation failed */
  error: Error | null;
}

/**
 * Hook providing mutation for creating a new webhook.
 *
 * Automatically invalidates the webhook list query on success.
 *
 * @returns Mutation for creating webhook
 *
 * @example
 * ```tsx
 * const { createWebhook, isLoading, error } = useCreateWebhook();
 *
 * const handleSubmit = async (data: WebhookCreate) => {
 *   try {
 *     const webhook = await createWebhook(data);
 *     toast.success(`Webhook "${webhook.name}" created!`);
 *   } catch (err) {
 *     toast.error(`Failed to create webhook: ${err.message}`);
 *   }
 * };
 * ```
 */
export function useCreateWebhook(): UseCreateWebhookReturn {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: webhookApi.createWebhook,
    onSuccess: () => {
      // Invalidate list query to refetch with new webhook
      void queryClient.invalidateQueries({
        queryKey: WEBHOOK_QUERY_KEYS.list,
      });
      // Also invalidate health since counts may have changed
      void queryClient.invalidateQueries({
        queryKey: WEBHOOK_QUERY_KEYS.health,
      });
    },
  });

  return {
    mutation,
    createWebhook: mutation.mutateAsync,
    isLoading: mutation.isPending,
    error: mutation.error,
  };
}

// ============================================================================
// useUpdateWebhook - Update an existing webhook
// ============================================================================

/**
 * Variables for the update webhook mutation.
 */
export interface UpdateWebhookVariables {
  /** Webhook ID to update */
  id: string;
  /** Fields to update */
  data: WebhookUpdate;
}

/**
 * Return type for the useUpdateWebhook hook.
 */
export interface UseUpdateWebhookReturn {
  /** The mutation object */
  mutation: ReturnType<typeof useMutation<Webhook, Error, UpdateWebhookVariables>>;
  /** Convenience method to update webhook */
  updateWebhook: (id: string, data: WebhookUpdate) => Promise<Webhook>;
  /** Whether the mutation is in progress */
  isLoading: boolean;
  /** Error if the mutation failed */
  error: Error | null;
}

/**
 * Hook providing mutation for updating an existing webhook.
 *
 * Automatically invalidates the webhook list and detail queries on success.
 *
 * @returns Mutation for updating webhook
 *
 * @example
 * ```tsx
 * const { updateWebhook, isLoading } = useUpdateWebhook();
 *
 * const handleSave = async () => {
 *   await updateWebhook(webhookId, {
 *     name: newName,
 *     event_types: selectedEvents,
 *   });
 *   toast.success('Webhook updated!');
 * };
 * ```
 */
export function useUpdateWebhook(): UseUpdateWebhookReturn {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: ({ id, data }: UpdateWebhookVariables) => webhookApi.updateWebhook(id, data),
    onSuccess: (updatedWebhook) => {
      // Invalidate list query
      void queryClient.invalidateQueries({
        queryKey: WEBHOOK_QUERY_KEYS.list,
      });
      // Invalidate specific webhook detail query
      void queryClient.invalidateQueries({
        queryKey: WEBHOOK_QUERY_KEYS.detail(updatedWebhook.id),
      });
      // Invalidate health since stats may have changed
      void queryClient.invalidateQueries({
        queryKey: WEBHOOK_QUERY_KEYS.health,
      });
    },
  });

  return {
    mutation,
    updateWebhook: (id: string, data: WebhookUpdate) => mutation.mutateAsync({ id, data }),
    isLoading: mutation.isPending,
    error: mutation.error,
  };
}

// ============================================================================
// useDeleteWebhook - Delete a webhook
// ============================================================================

/**
 * Return type for the useDeleteWebhook hook.
 */
export interface UseDeleteWebhookReturn {
  /** The mutation object */
  mutation: ReturnType<typeof useMutation<void, Error, string>>;
  /** Convenience method to delete webhook */
  deleteWebhook: (id: string) => Promise<void>;
  /** Whether the mutation is in progress */
  isLoading: boolean;
  /** Error if the mutation failed */
  error: Error | null;
}

/**
 * Hook providing mutation for deleting a webhook.
 *
 * Automatically invalidates the webhook list query on success.
 *
 * @returns Mutation for deleting webhook
 *
 * @example
 * ```tsx
 * const { deleteWebhook, isLoading } = useDeleteWebhook();
 *
 * const handleDelete = async () => {
 *   if (confirm('Delete this webhook?')) {
 *     await deleteWebhook(webhookId);
 *     toast.success('Webhook deleted');
 *   }
 * };
 * ```
 */
export function useDeleteWebhook(): UseDeleteWebhookReturn {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: webhookApi.deleteWebhook,
    onSuccess: (_data, webhookId) => {
      // Invalidate list query
      void queryClient.invalidateQueries({
        queryKey: WEBHOOK_QUERY_KEYS.list,
      });
      // Remove the specific webhook from cache
      queryClient.removeQueries({
        queryKey: WEBHOOK_QUERY_KEYS.detail(webhookId),
      });
      // Invalidate health since counts have changed
      void queryClient.invalidateQueries({
        queryKey: WEBHOOK_QUERY_KEYS.health,
      });
    },
  });

  return {
    mutation,
    deleteWebhook: mutation.mutateAsync,
    isLoading: mutation.isPending,
    error: mutation.error,
  };
}

// ============================================================================
// useTestWebhook - Test a webhook with sample payload
// ============================================================================

/**
 * Variables for the test webhook mutation.
 */
export interface TestWebhookVariables {
  /** Webhook ID to test */
  id: string;
  /** Test request with event type */
  request: WebhookTestRequest;
}

/**
 * Return type for the useTestWebhook hook.
 */
export interface UseTestWebhookReturn {
  /** The mutation object */
  mutation: ReturnType<typeof useMutation<WebhookTestResponse, Error, TestWebhookVariables>>;
  /** Convenience method to test webhook */
  testWebhook: (id: string, request: WebhookTestRequest) => Promise<WebhookTestResponse>;
  /** Whether the mutation is in progress */
  isLoading: boolean;
  /** Error if the mutation failed */
  error: Error | null;
  /** The test result from the last successful test */
  data: WebhookTestResponse | undefined;
}

/**
 * Hook providing mutation for testing a webhook.
 *
 * Does not invalidate any queries since testing doesn't create
 * persistent delivery records.
 *
 * @returns Mutation for testing webhook
 *
 * @example
 * ```tsx
 * const { testWebhook, isLoading, data } = useTestWebhook();
 *
 * const handleTest = async () => {
 *   const result = await testWebhook(webhookId, { event_type: 'alert_fired' });
 *   if (result.success) {
 *     toast.success(`Test passed! Response time: ${result.response_time_ms}ms`);
 *   } else {
 *     toast.error(`Test failed: ${result.error_message}`);
 *   }
 * };
 * ```
 */
export function useTestWebhook(): UseTestWebhookReturn {
  const mutation = useMutation({
    mutationFn: ({ id, request }: TestWebhookVariables) => webhookApi.testWebhook(id, request),
  });

  return {
    mutation,
    testWebhook: (id: string, request: WebhookTestRequest) => mutation.mutateAsync({ id, request }),
    isLoading: mutation.isPending,
    error: mutation.error,
    data: mutation.data,
  };
}

// ============================================================================
// useToggleWebhook - Enable/disable a webhook
// ============================================================================

/**
 * Variables for the toggle webhook mutation.
 */
export interface ToggleWebhookVariables {
  /** Webhook ID to toggle */
  id: string;
  /** Whether to enable (true) or disable (false) */
  enabled: boolean;
}

/**
 * Return type for the useToggleWebhook hook.
 */
export interface UseToggleWebhookReturn {
  /** The mutation object */
  mutation: ReturnType<typeof useMutation<Webhook, Error, ToggleWebhookVariables>>;
  /** Convenience method to enable a webhook */
  enableWebhook: (id: string) => Promise<Webhook>;
  /** Convenience method to disable a webhook */
  disableWebhook: (id: string) => Promise<Webhook>;
  /** Convenience method to toggle webhook state */
  toggleWebhook: (id: string, enabled: boolean) => Promise<Webhook>;
  /** Whether the mutation is in progress */
  isLoading: boolean;
  /** Error if the mutation failed */
  error: Error | null;
}

/**
 * Hook providing mutation for enabling/disabling a webhook.
 *
 * Automatically invalidates the webhook list and detail queries on success.
 *
 * @returns Mutation for toggling webhook state
 *
 * @example
 * ```tsx
 * const { toggleWebhook, enableWebhook, disableWebhook, isLoading } = useToggleWebhook();
 *
 * // Toggle based on current state
 * const handleToggle = async () => {
 *   await toggleWebhook(webhook.id, !webhook.enabled);
 *   toast.success(webhook.enabled ? 'Webhook disabled' : 'Webhook enabled');
 * };
 *
 * // Or use convenience methods
 * await enableWebhook(webhook.id);
 * await disableWebhook(webhook.id);
 * ```
 */
export function useToggleWebhook(): UseToggleWebhookReturn {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: ({ id, enabled }: ToggleWebhookVariables) =>
      enabled ? webhookApi.enableWebhook(id) : webhookApi.disableWebhook(id),
    onSuccess: (updatedWebhook) => {
      // Invalidate list query
      void queryClient.invalidateQueries({
        queryKey: WEBHOOK_QUERY_KEYS.list,
      });
      // Invalidate specific webhook detail query
      void queryClient.invalidateQueries({
        queryKey: WEBHOOK_QUERY_KEYS.detail(updatedWebhook.id),
      });
      // Invalidate health since enabled counts have changed
      void queryClient.invalidateQueries({
        queryKey: WEBHOOK_QUERY_KEYS.health,
      });
    },
  });

  return {
    mutation,
    enableWebhook: (id: string) => mutation.mutateAsync({ id, enabled: true }),
    disableWebhook: (id: string) => mutation.mutateAsync({ id, enabled: false }),
    toggleWebhook: (id: string, enabled: boolean) => mutation.mutateAsync({ id, enabled }),
    isLoading: mutation.isPending,
    error: mutation.error,
  };
}

// ============================================================================
// useRetryDelivery - Retry a failed delivery
// ============================================================================

/**
 * Return type for the useRetryDelivery hook.
 */
export interface UseRetryDeliveryReturn {
  /** The mutation object */
  mutation: ReturnType<typeof useMutation<WebhookDelivery, Error, string>>;
  /** Convenience method to retry delivery */
  retryDelivery: (deliveryId: string) => Promise<WebhookDelivery>;
  /** Whether the mutation is in progress */
  isLoading: boolean;
  /** Error if the mutation failed */
  error: Error | null;
}

/**
 * Hook providing mutation for retrying a failed delivery.
 *
 * Automatically invalidates delivery-related queries on success.
 *
 * @param webhookId - Optional webhook ID for targeted cache invalidation
 * @returns Mutation for retrying delivery
 *
 * @example
 * ```tsx
 * const { retryDelivery, isLoading } = useRetryDelivery(webhook.id);
 *
 * const handleRetry = async () => {
 *   const delivery = await retryDelivery(deliveryId);
 *   toast.info(`Retry queued (attempt ${delivery.attempt_count})`);
 * };
 * ```
 */
export function useRetryDelivery(webhookId?: string): UseRetryDeliveryReturn {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: webhookApi.retryDelivery,
    onSuccess: (delivery) => {
      // Invalidate deliveries for the webhook if known
      if (webhookId) {
        void queryClient.invalidateQueries({
          queryKey: WEBHOOK_QUERY_KEYS.deliveries(webhookId),
        });
      } else if (delivery.webhook_id) {
        void queryClient.invalidateQueries({
          queryKey: WEBHOOK_QUERY_KEYS.deliveries(delivery.webhook_id),
        });
      }
      // Invalidate webhook detail to update stats
      const targetWebhookId = webhookId ?? delivery.webhook_id;
      if (targetWebhookId) {
        void queryClient.invalidateQueries({
          queryKey: WEBHOOK_QUERY_KEYS.detail(targetWebhookId),
        });
      }
      // Invalidate list to update delivery stats
      void queryClient.invalidateQueries({
        queryKey: WEBHOOK_QUERY_KEYS.list,
      });
      // Invalidate health summary
      void queryClient.invalidateQueries({
        queryKey: WEBHOOK_QUERY_KEYS.health,
      });
    },
  });

  return {
    mutation,
    retryDelivery: mutation.mutateAsync,
    isLoading: mutation.isPending,
    error: mutation.error,
  };
}
