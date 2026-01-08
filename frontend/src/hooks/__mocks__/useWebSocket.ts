/**
 * Centralized mock for useWebSocket hook.
 */

import { vi } from 'vitest';

import type { UseWebSocketReturn, WebSocketOptions } from '../useWebSocket';

export interface MockWebSocketState {
  isConnected: boolean;
  hasExhaustedRetries: boolean;
  reconnectCount: number;
  lastHeartbeat: Date | null;
  lastMessage: unknown;
}

const defaultState: MockWebSocketState = {
  isConnected: true,
  hasExhaustedRetries: false,
  reconnectCount: 0,
  lastHeartbeat: null,
  lastMessage: null,
};

let mockState: MockWebSocketState = { ...defaultState };

export const mockSend = vi.fn<(data: unknown) => void>();
export const mockConnect = vi.fn<() => void>();
export const mockDisconnect = vi.fn<() => void>();

let currentOnMessageCallback: ((data: unknown) => void) | undefined;
let currentOnOpenCallback: (() => void) | undefined;
let currentOnCloseCallback: (() => void) | undefined;
let currentOnErrorCallback: ((error: Event) => void) | undefined;

export function setMockConnectionState(state: Partial<MockWebSocketState>): void {
  mockState = { ...mockState, ...state };
}

export function setMockLastMessage(message: unknown): void {
  mockState.lastMessage = message;
}

export function triggerMessage(data: unknown): void {
  mockState.lastMessage = data;
  currentOnMessageCallback?.(data);
}

export function triggerOpen(): void {
  mockState.isConnected = true;
  mockState.reconnectCount = 0;
  mockState.hasExhaustedRetries = false;
  currentOnOpenCallback?.();
}

export function triggerClose(): void {
  mockState.isConnected = false;
  currentOnCloseCallback?.();
}

export function triggerError(error?: Event): void {
  const errorEvent = error ?? new Event('error');
  currentOnErrorCallback?.(errorEvent);
}

export function triggerHeartbeat(): void {
  mockState.lastHeartbeat = new Date();
}

export function resetMocks(): void {
  mockState = { ...defaultState };
  mockSend.mockReset();
  mockConnect.mockReset();
  mockDisconnect.mockReset();
  currentOnMessageCallback = undefined;
  currentOnOpenCallback = undefined;
  currentOnCloseCallback = undefined;
  currentOnErrorCallback = undefined;
}

export const useWebSocket = vi.fn((options: WebSocketOptions): UseWebSocketReturn => {
  currentOnMessageCallback = options.onMessage;
  currentOnOpenCallback = options.onOpen;
  currentOnCloseCallback = options.onClose;
  currentOnErrorCallback = options.onError;

  return {
    isConnected: mockState.isConnected,
    lastMessage: mockState.lastMessage,
    send: mockSend,
    connect: mockConnect,
    disconnect: mockDisconnect,
    hasExhaustedRetries: mockState.hasExhaustedRetries,
    reconnectCount: mockState.reconnectCount,
    lastHeartbeat: mockState.lastHeartbeat,
  };
});

export const isHeartbeatMessage = vi.fn((data: unknown): boolean => {
  if (typeof data !== 'object' || data === null) return false;
  return (data as { type?: string }).type === 'ping';
});

export const calculateBackoffDelay = vi.fn((attempt: number, baseDelay: number = 1000): number => {
  return Math.min(baseDelay * Math.pow(2, attempt), 30000);
});
