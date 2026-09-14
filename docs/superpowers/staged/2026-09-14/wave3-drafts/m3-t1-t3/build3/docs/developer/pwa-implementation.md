# PWA Implementation Guide

> Technical documentation for the Progressive Web App features, service worker configuration, push notifications, and offline caching.

**Time to read:** ~12 min
**Prerequisites:** [Local Setup](local-setup.md)

---

This document covers the technical implementation of PWA features in the Nemotron Security Dashboard, including the web app manifest, push notification system, offline caching with IndexedDB, and mobile-responsive components.

---

## Web App Manifest

The manifest file defines how the app appears when installed on a user's device.

### Manifest Location

```
frontend/public/manifest.json
```

### Manifest Structure

```json
{
  "name": "Nemotron Security Dashboard",
  "short_name": "Nemotron",
  "description": "AI-powered home security monitoring dashboard with real-time threat detection",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#1a1a2e",
  "theme_color": "#76B900",
  "orientation": "any",
  "scope": "/",
  "lang": "en",
  "categories": ["security", "utilities", "lifestyle"],
  "icons": [...],
  "shortcuts": [...],
  "prefer_related_applications": false
}
```

### Icon Requirements

The manifest includes icons for various contexts:

| File                      | Size    | Purpose                       |
| ------------------------- | ------- | ----------------------------- |
| `icon-192.png`            | 192x192 | Standard app icon             |
| `icon-192.png` (maskable) | 192x192 | Adaptive icon for Android     |
| `icon-512.png`            | 512x512 | Splash screen / high-res      |
| `icon-512.png` (maskable) | 512x512 | Adaptive splash screen        |
| `badge-72.png`            | 72x72   | Monochrome notification badge |
| `apple-touch-icon.png`    | 180x180 | iOS home screen icon          |
| `favicon.svg`             | any     | Vector fallback               |

### App Shortcuts

The manifest defines shortcuts for quick actions from the app icon context menu:

```json
"shortcuts": [
  {
    "name": "View Events",
    "short_name": "Events",
    "description": "View recent security events",
    "url": "/events",
    "icons": [{ "src": "/icons/icon-192.png", "sizes": "192x192" }]
  },
  {
    "name": "Settings",
    "short_name": "Settings",
    "description": "Configure dashboard settings",
    "url": "/settings",
    "icons": [{ "src": "/icons/icon-192.png", "sizes": "192x192" }]
  }
]
```

### HTML Meta Tags

The `index.html` includes PWA-specific meta tags:

```html
<!-- PWA Meta Tags -->
<meta name="theme-color" content="#76B900" />
<meta name="description" content="AI-powered home security monitoring..." />
<meta name="mobile-web-app-capable" content="yes" />
<meta name="apple-mobile-web-app-capable" content="yes" />
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
<meta name="apple-mobile-web-app-title" content="Nemotron" />

<!-- Icons -->
<link rel="icon" type="image/svg+xml" href="/favicon.svg" />
<link rel="apple-touch-icon" href="/icons/apple-touch-icon.png" />
<link rel="manifest" href="/manifest.json" />
```

---

## Push Notification System

### Hook: `usePushNotifications`

Location: `frontend/src/hooks/usePushNotifications.ts`

The `usePushNotifications` hook manages browser push notification permissions and displays security alerts.

#### Interface

```typescript
interface UsePushNotificationsReturn {
  /** Current notification permission state */
  permission: NotificationPermission;
  /** Whether notifications are supported in this browser */
  isSupported: boolean;
  /** Whether user has granted notification permission */
  hasPermission: boolean;
  /** Whether user has interacted with the permission prompt */
  hasInteracted: boolean;
  /** Whether we have an active push subscription */
  isSubscribed: boolean;
  /** Request notification permission from user */
  requestPermission: () => Promise<NotificationPermission>;
  /** Show a notification (requires permission) */
  showNotification: (title: string, options?: NotificationOptions) => Promise<void>;
  /** Convenience method to show a security alert notification */
  showSecurityAlert: (options: SecurityAlertOptions) => Promise<void>;
}
```

#### Security Alert Options

```typescript
interface SecurityAlertOptions {
  /** Camera name/identifier */
  camera: string;
  /** Risk level of the detection */
  riskLevel: 'low' | 'medium' | 'high' | 'critical';
  /** Brief summary of what was detected */
  summary: string;
  /** Optional event ID for deduplication */
  eventId?: string;
}
```

#### Usage Example

```tsx
const { permission, requestPermission, showSecurityAlert, hasPermission } = usePushNotifications();

// Request permission on button click
const handleEnableNotifications = async () => {
  await requestPermission();
};

// Show security alert when event is received
useEffect(() => {
  if (newEvent && hasPermission) {
    showSecurityAlert({
      camera: newEvent.camera_id,
      riskLevel: newEvent.risk_level,
      summary: newEvent.summary,
      eventId: newEvent.id,
    });
  }
}, [newEvent, hasPermission, showSecurityAlert]);
```

#### Notification Behavior by Risk Level

| Risk Level | Icon         | Require Interaction | Silent |
| ---------- | ------------ | ------------------- | ------ |
| `low`      | icon-192.png | No                  | Yes    |
| `medium`   | icon-192.png | No                  | No     |
| `high`     | badge-72.png | Yes                 | No     |
| `critical` | badge-72.png | Yes                 | No     |

#### Service Worker Integration

The hook attempts to use service worker notifications for better reliability:

```typescript
if ('serviceWorker' in navigator) {
  const registration = await navigator.serviceWorker.ready;
  await registration.showNotification(title, options);
} else {
  // Fallback to regular Notification API
  new Notification(title, options);
}
```

---

## Offline Caching with IndexedDB

### Hook: `useCachedEvents`

Location: `frontend/src/hooks/useCachedEvents.ts`

The `useCachedEvents` hook provides offline caching for security events using IndexedDB.

#### Database Schema

```typescript
// Database configuration
const DB_NAME = 'nemotron-security';
const DB_VERSION = 1;
const STORE_NAME = 'cached-events';

// Object store schema
interface CachedEvent {
  id: string; // Unique event identifier (keyPath)
  camera_id: string; // Camera ID (indexed)
  risk_score: number;
  risk_level: 'low' | 'medium' | 'high' | 'critical';
  summary: string;
  timestamp: string; // ISO 8601 (indexed)
  cachedAt: string; // When cached locally
}
```

#### Indexes

```typescript
store.createIndex('timestamp', 'timestamp', { unique: false });
store.createIndex('camera_id', 'camera_id', { unique: false });
```

#### Interface

```typescript
interface UseCachedEventsReturn {
  /** Array of cached events (sorted by timestamp, newest first) */
  cachedEvents: CachedEvent[];
  /** Number of cached events */
  cachedCount: number;
  /** True when IndexedDB has been initialized */
  isInitialized: boolean;
  /** Error message if IndexedDB operations fail */
  error: string | null;
  /** Cache a new event */
  cacheEvent: (event: CachedEvent) => Promise<void>;
  /** Load all cached events from IndexedDB */
  loadCachedEvents: () => Promise<void>;
  /** Remove a specific cached event by ID */
  removeCachedEvent: (id: string) => Promise<void>;
  /** Clear all cached events */
  clearCache: () => Promise<void>;
}
```

#### Usage Example

```tsx
const { cachedEvents, cachedCount, cacheEvent, clearCache } = useCachedEvents();

// Cache a new event when offline
const handleNewEvent = async (event: SecurityEvent) => {
  if (!navigator.onLine) {
    await cacheEvent({
      ...event,
      cachedAt: new Date().toISOString(),
    });
  }
};

// Display cached events while offline
if (!navigator.onLine && cachedCount > 0) {
  return <CachedEventsList events={cachedEvents} />;
}
```

---

## Network Status Detection

### Hook: `useNetworkStatus`

Location: `frontend/src/hooks/useNetworkStatus.ts`

Tracks browser network connectivity status with callbacks for transitions.

#### Interface

```typescript
interface UseNetworkStatusReturn {
  /** True if browser is currently online */
  isOnline: boolean;
  /** True if browser is currently offline */
  isOffline: boolean;
  /** Timestamp of the last time the browser was online */
  lastOnlineAt: Date | null;
  /** True if browser was offline and has since reconnected */
  wasOffline: boolean;
  /** Clear the wasOffline flag */
  clearWasOffline: () => void;
}
```

#### Usage Example

```tsx
const { isOnline, isOffline, wasOffline, clearWasOffline } = useNetworkStatus({
  onOnline: () => console.log('Back online!'),
  onOffline: () => console.log('Lost connection'),
});

if (isOffline) {
  return <OfflineFallback />;
}

if (wasOffline) {
  return (
    <>
      <ReconnectedBanner onDismiss={clearWasOffline} />
      <MainContent />
    </>
  );
}
```

---

## Mobile-Responsive Components

### Mobile Detection Hook

Location: `frontend/src/hooks/useIsMobile.ts`

```typescript
// Default 768px breakpoint (Tailwind's md breakpoint)
const isMobile = useIsMobile();

// Custom breakpoint
const isTablet = useIsMobile(1024);
```

Uses `MediaQueryList` API for reactive updates on viewport resize.

### Swipe Gesture Hook

Location: `frontend/src/hooks/useSwipeGesture.ts`

```typescript
const swipeRef = useSwipeGesture({
  onSwipe: (direction: 'left' | 'right' | 'up' | 'down') => {
    if (direction === 'left') {
      handleDismiss();
    }
  },
  threshold: 50,  // Minimum pixels to trigger
  timeout: 300,   // Max milliseconds for gesture
});

return <div ref={swipeRef}>Swipeable content</div>;
```

### Mobile Bottom Navigation

Location: `frontend/src/components/layout/MobileBottomNav.tsx`

Displays fixed bottom navigation bar on mobile viewports:

- Uses safe area insets for devices with notches/home indicators
- All touch targets are minimum 44x44px for accessibility
- Shows notification badge on alerts icon
- Active route highlighting with brand color

### Mobile Event Card

Location: `frontend/src/components/events/MobileEventCard.tsx`

Compact event card optimized for mobile:

- Single-line layout with thumbnail, summary, and actions
- Swipe gesture support for quick actions
- Relative timestamps ("5m ago")
- Touch-friendly action buttons

### Offline Fallback

Location: `frontend/src/components/common/OfflineFallback.tsx`

Displays when network is unavailable:

- Cached event count indicator
- Last online timestamp
- Retry button with auto-retry on reconnection
- Troubleshooting tips

---

## Tailwind CSS Configuration

### Safe Area Support

Location: `frontend/tailwind.config.js`

```javascript
spacing: {
  safe: 'env(safe-area-inset-bottom)',
}
```

Used in components:

```html
<nav className="pb-safe">...</nav>
```

### Responsive Breakpoints

Standard Tailwind breakpoints are used:

| Breakpoint | Min Width | Usage               |
| ---------- | --------- | ------------------- |
| `sm`       | 640px     | Small tablets       |
| `md`       | 768px     | Desktop mode begins |
| `lg`       | 1024px    | Larger desktops     |
| `xl`       | 1280px    | Wide screens        |
| `2xl`      | 1536px    | Extra wide          |

### Mobile-First Patterns

Components use mobile-first responsive patterns:

```html
<!-- Mobile: bottom nav, Desktop: sidebar -->
{!isMobile && <Sidebar />} {isMobile && <MobileBottomNav />}

<!-- Mobile: stack, Desktop: grid -->
<div className="flex flex-col md:grid md:grid-cols-2"></div>
```

---

## Layout Component

Location: `frontend/src/components/layout/Layout.tsx`

The main layout handles mobile/desktop switching:

```typescript
export default function Layout({ children }: LayoutProps) {
  const isMobile = useIsMobile();

  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <div className="flex flex-1 overflow-hidden">
        {/* Hide sidebar on mobile */}
        {!isMobile && <Sidebar />}

        <main className={`flex-1 overflow-auto ${isMobile ? 'pb-14' : ''}`}>
          {children}
        </main>
      </div>

      {/* Show mobile bottom nav on mobile viewports */}
      {isMobile && <MobileBottomNav />}
    </div>
  );
}
```

### Sidebar Context

Location: `frontend/src/hooks/useSidebarContext.ts`

Provides mobile menu state management:

```typescript
interface SidebarContextType {
  isMobileMenuOpen: boolean;
  setMobileMenuOpen: (open: boolean) => void;
  toggleMobileMenu: () => void;
}
```

---

## Testing PWA Features

### Unit Tests

Each PWA hook has corresponding test files:

| Hook                   | Test File                      |
| ---------------------- | ------------------------------ |
| `usePushNotifications` | `usePushNotifications.test.ts` |
| `useCachedEvents`      | `useCachedEvents.test.ts`      |
| `useNetworkStatus`     | `useNetworkStatus.test.ts`     |
| `useIsMobile`          | `useIsMobile.test.ts`          |
| `useSwipeGesture`      | `useSwipeGesture.test.ts`      |

### Mocking Browser APIs

```typescript
// Mock Notification API
vi.stubGlobal(
  'Notification',
  class MockNotification {
    static permission = 'default' as NotificationPermission;
    static requestPermission = vi.fn().mockResolvedValue('granted');
    constructor(title: string, options?: NotificationOptions) {
      mockNotification(title, options);
    }
  }
);

// Mock service worker
vi.stubGlobal('navigator', {
  serviceWorker: {
    ready: Promise.resolve({
      pushManager: {
        getSubscription: vi.fn().mockResolvedValue(null),
      },
      showNotification: vi.fn(),
    }),
  },
});
```

### E2E Testing

Playwright can test PWA installation prompts and offline behavior:

```typescript
test('shows offline fallback when network is unavailable', async ({ page, context }) => {
  await page.goto('/');

  // Simulate offline
  await context.setOffline(true);

  // Verify offline fallback appears
  await expect(page.locator('[data-testid="offline-fallback"]')).toBeVisible();
});
```

---

## Next Steps

- [Frontend Hooks](../architecture/frontend-hooks.md) - Complete hooks documentation
- [WebSocket Contracts](api/websocket-contracts.md) - Real-time communication
- [Testing Guide](../development/testing.md) - Testing patterns

---

[Back to Developer Hub](README.md)
