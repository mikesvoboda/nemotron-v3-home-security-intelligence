/**
 * [r204] box 3: "the mounted shell holds one manager connection per channel;
 * neither Layout nor Header opens a socket".
 *
 * This file exists because the claim cannot be made from either component's own
 * suite: `Layout.test.tsx` mocks `./Header` and `Header.test.tsx` mocks
 * `useConnectionStatus`, so neither one ever runs the pair together — which is
 * exactly the arrangement that used to open four sockets over two URLs
 * (Layout.tsx:38 and Header.tsx:171 each built their own session through the
 * now-deleted `useWebSocketStatus`). So this mounts BOTH for real.
 *
 * The fixture mocks as little as it can. Everything that owns a socket stays
 * real: this provider, `Header`'s own `useSceneChangeAlerts` (`/ws/events`) and
 * `usePrometheusAlertWebSocket` (`/ws/system`), and `useWebSocket`, which routes
 * through `webSocketManager` (`useWebSocket.ts:123`) like every manager-era
 * hook. That leaves genuine competition for each URL — if the status path still
 * opened a socket of its own, the counts below would double — instead of a
 * census taken with the other consumers mocked out of sight. What IS mocked is
 * unrelated chrome (`Sidebar`, command palette) and REST-only query hooks
 * (`useServiceStatus`, `useVerdictEngineStatus`, `useKeyboardShortcuts` — the
 * same three `Layout.test.tsx` mocks, the last because it calls `useNavigate` —
 * plus `useHealthStatusQuery` and `useAIServiceStatus`, which answer no socket
 * question and would otherwise need msw handlers).
 */
import { render, screen, act, cleanup } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import Layout from './Layout';
import { ThemeProvider } from '../../contexts';
import { AnnouncementProvider } from '../../contexts/AnnouncementContext';
import { ConnectionStatusProvider } from '../../hooks/ConnectionStatusProvider';
import { webSocketManager } from '../../hooks/webSocketManager';
import { buildWebSocketOptions } from '../../services/api';
import { renderWithProviders } from '../../test-utils/renderWithProviders';

vi.mock('./Sidebar', () => ({ default: () => null }));
vi.mock('./MobileBottomNav', () => ({ default: () => null }));
vi.mock('../common/CommandPalette', () => ({ default: () => null }));
vi.mock('../common/ShortcutsHelpModal', () => ({ default: () => null }));

vi.mock('../../hooks/useServiceStatus', () => ({
  useServiceStatus: () => ({ services: { redis: null, yolo26: null } }),
}));
vi.mock('../../hooks/useVerdictEngineStatus', () => ({
  useVerdictEngineStatus: () => ({ state: 'unknown', isDown: false }),
}));
vi.mock('../../hooks/useKeyboardShortcuts', () => ({ useKeyboardShortcuts: () => undefined }));
vi.mock('../../hooks/useHealthStatusQuery', () => ({
  useHealthStatusQuery: () => ({
    data: undefined,
    isLoading: false,
    isError: false,
    error: null,
    refetch: () => undefined,
  }),
}));
vi.mock('../../hooks/useAIServiceStatus', () => ({
  useAIServiceStatus: () => ({
    degradationMode: 'normal',
    services: {},
    isLoading: false,
    isError: false,
  }),
}));

class MockWebSocket {
  static instances: MockWebSocket[] = [];
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  url: string;
  readyState = MockWebSocket.CONNECTING;
  binaryType: BinaryType = 'blob';
  onopen: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
    setTimeout(() => {
      this.readyState = MockWebSocket.OPEN;
      this.onopen?.({} as Event);
    }, 0);
  }

  send(): void {}

  close(): void {
    this.readyState = MockWebSocket.CLOSED;
  }
}

/* Derived from the same builder production calls, rather than spelled out: the
 * host half comes from `window.location.host` (jsdom's is `localhost:3000`) and
 * a `VITE_WS_BASE_URL` would override the whole origin. The claim under test is
 * "one socket per channel", which is about counting, not about host strings. */
const EVENTS_URL = buildWebSocketOptions('/ws/events').url;
const SYSTEM_URL = buildWebSocketOptions('/ws/system').url;

const urlsOpened = (): string[] => MockWebSocket.instances.map((ws) => ws.url).sort();

/** The contexts the shell normally sits under. `ThemeProvider` is not optional
 * decoration: `useTheme` throws outside it (ThemeContext.tsx). */
function ShellProviders({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider defaultMode="dark">
      <AnnouncementProvider>
        <ConnectionStatusProvider>{children}</ConnectionStatusProvider>
      </AnnouncementProvider>
    </ThemeProvider>
  );
}

function Shell() {
  return (
    <Layout>
      <div data-testid="shell-child" />
    </Layout>
  );
}

describe('mounted shell holds one realtime owner [r204]', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    MockWebSocket.instances = [];
    webSocketManager.reset();
    vi.stubGlobal('WebSocket', MockWebSocket);
  });

  afterEach(() => {
    // Order matters: unmount so each consumer's cleanup unsubscribes, then drop
    // the singleton's map so a later case never inherits this one's sockets.
    cleanup();
    webSocketManager.reset();
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it('the mounted shell holds one connection per channel', async () => {
    renderWithProviders(
      <ShellProviders>
        <Shell />
      </ShellProviders>
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    expect(screen.getByTestId('shell-child')).toBeInTheDocument();

    // Two URLs, one socket each — although two independent consumers are
    // registered on each: this provider plus one of Header's own hooks
    // (`useSceneChangeAlerts` on /ws/events, `usePrometheusAlertWebSocket` on
    // /ws/system). Before [r204] the status path added its own unshared pair to
    // each URL, so this is the count the package exists to produce.
    expect(urlsOpened()).toEqual([EVENTS_URL, SYSTEM_URL]);
    expect(webSocketManager.getSubscriberCount(EVENTS_URL)).toBeGreaterThanOrEqual(2);
    expect(webSocketManager.getSubscriberCount(SYSTEM_URL)).toBeGreaterThanOrEqual(2);
  });

  /**
   * "Neither Layout nor Header opens a socket", proved structurally: the shell
   * cannot render at all without the provider, because the hook the shell calls
   * is a reader now. Before [r204] each of them built a session here — that is
   * what the deleted `useWebSocketStatus` did on every call — and nothing would
   * have thrown.
   */
  it('the shell cannot render without the one provider', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined);

    expect(() =>
      render(
        <ThemeProvider defaultMode="dark">
          <AnnouncementProvider>
            <Shell />
          </AnnouncementProvider>
        </ThemeProvider>
      )
    ).toThrow(/ConnectionStatusProvider/);

    // And it got nowhere near a handshake: the throw happened while reading the
    // session, so no socket was constructed on the way down.
    expect(MockWebSocket.instances).toHaveLength(0);

    consoleError.mockRestore();
  });

  it('Header surfaces read the shared session', async () => {
    renderWithProviders(
      <ShellProviders>
        <Shell />
      </ShellProviders>
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    // Header's indicator is green because the SHARED session connected: the
    // component opens nothing itself, so this colour can only come from the
    // provider's summary. (`connection-label` is not a probe here — it renders
    // only while reconnecting/failed, WebSocketStatus.tsx:326.)
    expect(screen.getByTestId('overall-status-dot')).toHaveClass('bg-green-500');
    expect(MockWebSocket.instances.length).toBe(2);
  });
});
