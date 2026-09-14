# Webhooks Components

## Purpose

Complete webhook management UI for the NVIDIA Security Intelligence dashboard. Enables users to configure, test, and monitor webhook endpoints for real-time event notifications to external services (Slack, Discord, Teams, Telegram, or generic HTTP endpoints).

**Related Issue:** NEM-3624 - Webhook Management Feature

## Key Components

| File                          | Purpose                                              |
| ----------------------------- | ---------------------------------------------------- |
| `WebhookHealthCard.tsx`       | Dashboard card showing overall webhook health metrics |
| `WebhookList.tsx`             | Table of webhooks with management actions            |
| `WebhookForm.tsx`             | Form for creating and editing webhooks               |
| `WebhookDeliveryHistory.tsx`  | Delivery log table for a specific webhook            |
| `WebhookTestModal.tsx`        | Modal for testing webhook delivery                   |
| `index.ts`                    | Barrel exports for all webhook components            |

## Component Details

### WebhookHealthCard

Dashboard card displaying overall webhook health metrics.

**Props:**

| Prop           | Type                      | Default | Description                    |
| -------------- | ------------------------- | ------- | ------------------------------ |
| `health`       | `WebhookHealthSummary?`   | -       | Health summary data            |
| `isLoading`    | `boolean?`                | `false` | Whether data is loading        |
| `isRefetching` | `boolean?`                | `false` | Whether data is refetching     |
| `className`    | `string?`                 | `''`    | Additional CSS classes         |

**Metrics Displayed:**
- Total webhooks (with enabled count)
- Healthy webhooks (>90% success rate)
- Unhealthy webhooks (<50% success rate)
- 24h delivery count (with success %)
- Failed deliveries (24h)
- Average response time

---

### WebhookList

Table component displaying webhooks with inline management actions.

**Props:**

| Prop            | Type                          | Default | Description                              |
| --------------- | ----------------------------- | ------- | ---------------------------------------- |
| `webhooks`      | `Webhook[]`                   | -       | List of webhooks to display              |
| `isLoading`     | `boolean?`                    | `false` | Whether data is loading                  |
| `onToggle`      | `(id, enabled) => void`       | -       | Handler for toggling enabled state       |
| `onEdit`        | `(webhook) => void`           | -       | Handler for editing a webhook            |
| `onDelete`      | `(webhook) => void`           | -       | Handler for deleting a webhook           |
| `onTest`        | `(webhook) => void`           | -       | Handler for testing a webhook            |
| `onViewHistory` | `(webhook) => void`           | -       | Handler for viewing delivery history     |
| `isToggling`    | `boolean?`                    | `false` | Whether any toggle is in progress        |
| `togglingId`    | `string?`                     | -       | ID of webhook currently being toggled    |
| `className`     | `string?`                     | `''`    | Additional CSS classes                   |

**Table Columns:**
- Webhook (name + integration icon)
- URL (truncated)
- Events (badges, max 2 visible)
- Status (enabled toggle)
- Success Rate (color-coded badge)
- Actions (test, edit, dropdown menu)

**Integration Icons:** Slack, Discord, Telegram, Teams, Generic

---

### WebhookForm

Comprehensive form for creating and editing webhook configurations.

**Props:**

| Prop              | Type                                                  | Default | Description              |
| ----------------- | ----------------------------------------------------- | ------- | ------------------------ |
| `webhook`         | `Webhook?`                                            | -       | Existing webhook for edit |
| `onSubmit`        | `(data: WebhookCreate \| WebhookUpdate) => Promise<void>` | -   | Submit handler           |
| `onCancel`        | `() => void`                                          | -       | Cancel handler           |
| `isSubmitting`    | `boolean?`                                            | `false` | Whether submitting       |
| `apiError`        | `string?`                                             | -       | API error message        |
| `onClearApiError` | `() => void?`                                         | -       | Clear error callback     |

**Form Sections:**

1. **Basic Information**
   - Name (required, max 100 chars)
   - URL (required, valid HTTP/HTTPS)
   - Integration type (auto-detected from URL)
   - Enabled toggle

2. **Event Types** (multi-select)
   - `alert_fired`, `alert_resolved`, `alert_acknowledged`
   - `detection_new`, `risk_escalation`
   - `system_health`, `system_error`

3. **Authentication**
   - None, Bearer Token, Basic Auth, Custom Header

4. **Custom Headers** (key-value pairs)

5. **Retry Configuration**
   - Max retries (0-10)
   - Retry delay (1-3600 seconds, exponential backoff)

---

### WebhookDeliveryHistory

Paginated table showing delivery attempts for a specific webhook.

**Props:**

| Prop           | Type                          | Default | Description                    |
| -------------- | ----------------------------- | ------- | ------------------------------ |
| `webhookName`  | `string`                      | -       | Webhook name for display       |
| `deliveries`   | `WebhookDelivery[]`           | -       | Deliveries to display          |
| `total`        | `number`                      | -       | Total count for pagination     |
| `hasMore`      | `boolean`                     | -       | Whether there are more pages   |
| `page`         | `number`                      | -       | Current page (0-indexed)       |
| `pageSize`     | `number`                      | -       | Items per page                 |
| `isLoading`    | `boolean?`                    | `false` | Loading state                  |
| `isRefetching` | `boolean?`                    | `false` | Refetching state               |
| `onPageChange` | `(page) => void`              | -       | Handler for page change        |
| `onRetry`      | `(deliveryId) => void`        | -       | Handler for retry              |
| `onRefresh`    | `() => void`                  | -       | Handler for refresh            |
| `retryingId`   | `string?`                     | -       | ID of delivery being retried   |
| `onClose`      | `() => void?`                 | -       | Close handler                  |
| `className`    | `string?`                     | `''`    | Additional CSS classes         |

**Table Columns:**
- Time (date/time split)
- Event (event type badge)
- Status (success/failed/retrying/pending)
- Response (HTTP status code badge)
- Duration (formatted ms/s)
- Attempts (retry count)
- Error / Actions (retry button for failed)

---

### WebhookTestModal

Modal for sending test payloads to a webhook.

**Props:**

| Prop      | Type                                                          | Description           |
| --------- | ------------------------------------------------------------- | --------------------- |
| `webhook` | `Webhook \| null`                                             | Webhook to test       |
| `isOpen`  | `boolean`                                                     | Whether modal is open |
| `onClose` | `() => void`                                                  | Close handler         |
| `onTest`  | `(webhookId, eventType) => Promise<WebhookTestResponse>`      | Test handler          |

**Features:**
- Event type selector dropdown
- Send Test button with loading state
- Result display (pass/fail, response code, time)
- Error message display
- Response body preview (truncated)

## Usage Examples

```tsx
import {
  WebhookHealthCard,
  WebhookList,
  WebhookForm,
  WebhookDeliveryHistory,
  WebhookTestModal,
} from '@/components/webhooks';

// Health dashboard
<WebhookHealthCard health={healthSummary} isLoading={isLoading} />

// Webhook table
<WebhookList
  webhooks={webhooks}
  onToggle={handleToggle}
  onEdit={openEditModal}
  onDelete={confirmDelete}
  onTest={openTestModal}
  onViewHistory={openHistoryPanel}
/>

// Create webhook
<WebhookForm onSubmit={createWebhook} onCancel={closeModal} />

// Delivery history
<WebhookDeliveryHistory
  webhookName={selectedWebhook.name}
  deliveries={deliveries}
  total={totalCount}
  hasMore={hasNextPage}
  page={currentPage}
  pageSize={20}
  onPageChange={setPage}
  onRetry={retryDelivery}
  onRefresh={refetchDeliveries}
/>

// Test modal
<WebhookTestModal
  webhook={selectedWebhook}
  isOpen={isTestModalOpen}
  onClose={closeTestModal}
  onTest={testWebhook}
/>
```

## Dependencies

- `clsx` - Conditional class composition
- `lucide-react` - Icons
- `../../types/webhook` - Type definitions and constants
- `../common/Button` - Shared button component
- `../common/EmptyState` - Empty state component
- `../common/AnimatedModal` - Modal component (for WebhookTestModal)

## Styling

Uses Tailwind CSS with NVIDIA dark theme:

- Panel/card backgrounds: `bg-[#1F1F1F]`
- Form input backgrounds: `bg-[#1A1A1A]`
- Borders: `border-gray-800`, `border-gray-700`
- NVIDIA green accent: `#76B900`
- Status colors:
  - Success: `green-400`, `green-500/10`
  - Warning: `yellow-400`, `yellow-500/10`
  - Error: `red-400`, `red-500/10`
  - Info: `blue-400`, `blue-500/10`
