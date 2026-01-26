/**
 * Service Worker Registration Module
 *
 * Provides utilities for registering and managing the PWA service worker
 * using Workbox. Integrates with vite-plugin-pwa for seamless SW management.
 *
 * @module serviceWorkerRegistration
 * @see NEM-3675 - PWA Offline Caching
 */

import { Workbox, messageSW } from 'workbox-window';

/**
 * Service worker registration configuration
 */
export interface ServiceWorkerConfig {
  /** Callback when a new service worker is installed and waiting */
  onUpdate?: (registration: ServiceWorkerRegistration) => void;
  /** Callback when service worker is successfully installed for first time */
  onSuccess?: (registration: ServiceWorkerRegistration) => void;
  /** Callback when service worker registration fails */
  onError?: (error: Error) => void;
  /** Callback when service worker becomes active */
  onActivated?: () => void;
}

/**
 * Service worker state for external consumers
 */
export interface ServiceWorkerState {
  /** Whether a service worker is currently active */
  isActive: boolean;
  /** Whether an update is waiting to be installed */
  isUpdateWaiting: boolean;
  /** Whether a service worker is currently installing */
  isInstalling: boolean;
  /** Reference to the Workbox instance */
  workbox: Workbox | null;
}

// Module-level state
let workboxInstance: Workbox | null = null;
let swRegistration: ServiceWorkerRegistration | null = null;
let isUpdateWaiting = false;
let isInstalling = false;

/**
 * Checks if service workers are supported in the current environment
 * @returns Whether service workers are supported
 */
export function isServiceWorkerSupported(): boolean {
  return 'serviceWorker' in navigator;
}

/**
 * Registers the service worker and sets up event listeners
 *
 * @param config - Configuration options for callbacks
 * @returns Promise resolving to true if registration successful, false otherwise
 *
 * @example
 * ```typescript
 * await registerServiceWorker({
 *   onSuccess: (reg) => console.log('SW registered'),
 *   onUpdate: (reg) => showUpdatePrompt(),
 *   onError: (err) => console.error('SW failed:', err),
 * });
 * ```
 */
export async function registerServiceWorker(
  config: ServiceWorkerConfig = {}
): Promise<boolean> {
  const { onUpdate, onSuccess, onError, onActivated } = config;

  if (!isServiceWorkerSupported()) {
    console.warn('Service workers are not supported in this browser');
    return false;
  }

  try {
    // Create Workbox instance
    workboxInstance = new Workbox('/sw.js', {
      // Scope to entire app
      scope: '/',
    });

    // Handle waiting service worker (update available)
    workboxInstance.addEventListener('waiting', (event) => {
      isUpdateWaiting = true;
      if (event.sw && onUpdate) {
        // Get the registration from the waiting SW
        void navigator.serviceWorker.getRegistration().then((registration) => {
          if (registration) {
            onUpdate(registration);
          }
        });
      }
    });

    // Handle service worker installed (first time)
    workboxInstance.addEventListener('installed', (event) => {
      if (!event.isUpdate) {
        void navigator.serviceWorker.getRegistration().then((registration) => {
          if (registration && onSuccess) {
            onSuccess(registration);
          }
        });
      }
    });

    // Handle service worker activated
    workboxInstance.addEventListener('activated', () => {
      isInstalling = false;
      isUpdateWaiting = false;
      onActivated?.();
    });

    // Handle service worker controlling the page
    workboxInstance.addEventListener('controlling', () => {
      // Service worker is now controlling the page
    });

    // Handle redundant service worker
    workboxInstance.addEventListener('redundant', () => {
      console.warn('Service worker became redundant');
    });

    // Register the service worker
    isInstalling = true;
    const registration = await workboxInstance.register();
    swRegistration = registration ?? null;
    isInstalling = false;

    return true;
  } catch (error) {
    isInstalling = false;
    const err = error instanceof Error ? error : new Error(String(error));
    console.error('Service worker registration failed:', err);
    onError?.(err);
    return false;
  }
}

/**
 * Signals the waiting service worker to skip waiting and become active
 * This will trigger a page reload to load fresh content
 *
 * @returns Promise resolving when skip waiting message is sent
 */
export async function skipWaiting(): Promise<void> {
  if (!workboxInstance) {
    console.warn('No Workbox instance available');
    return;
  }

  const registration = await navigator.serviceWorker.getRegistration();
  if (registration?.waiting) {
    // Send skip waiting message to the waiting SW
    await messageSW(registration.waiting, { type: 'SKIP_WAITING' });
  }
}

/**
 * Unregisters all service workers
 *
 * @returns Promise resolving to true if unregistration successful
 */
export async function unregisterServiceWorker(): Promise<boolean> {
  if (!isServiceWorkerSupported()) {
    return false;
  }

  try {
    const registration = await navigator.serviceWorker.getRegistration();
    if (registration) {
      const result = await registration.unregister();
      if (result) {
        workboxInstance = null;
        swRegistration = null;
        isUpdateWaiting = false;
      }
      return result;
    }
    return false;
  } catch {
    return false;
  }
}

/**
 * Gets the current service worker state
 *
 * @returns Current service worker state
 */
export function getServiceWorkerState(): ServiceWorkerState {
  return {
    isActive: swRegistration?.active !== null && swRegistration?.active !== undefined,
    isUpdateWaiting,
    isInstalling,
    workbox: workboxInstance,
  };
}

/**
 * Checks if a specific URL is cached by the service worker
 *
 * @param url - URL to check
 * @returns Promise resolving to true if cached
 */
export async function isCached(url: string): Promise<boolean> {
  if (!('caches' in window)) {
    return false;
  }

  try {
    const cacheNames = await caches.keys();
    for (const cacheName of cacheNames) {
      const cache = await caches.open(cacheName);
      const response = await cache.match(url);
      if (response) {
        return true;
      }
    }
    return false;
  } catch {
    return false;
  }
}

/**
 * Gets cache storage estimate
 *
 * @returns Promise resolving to storage estimate or null if not available
 */
export async function getCacheStorageEstimate(): Promise<{
  usage: number;
  quota: number;
  usagePercentage: number;
} | null> {
  if (!navigator.storage?.estimate) {
    return null;
  }

  try {
    const estimate = await navigator.storage.estimate();
    const usage = estimate.usage ?? 0;
    const quota = estimate.quota ?? 0;
    const usagePercentage = quota > 0 ? Math.round((usage / quota) * 100) : 0;

    return {
      usage,
      quota,
      usagePercentage,
    };
  } catch {
    return null;
  }
}
