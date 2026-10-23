import { ReactNode, useCallback, useMemo, useState } from 'react';

import AdvancedBanner from './AdvancedBanner';
import Header from './Header';
import HubTabBar, { LayoutHubTabBarContext } from './HubTabBar';
import MobileBottomNav from './MobileBottomNav';
import Sidebar from './Sidebar';
import {
  CommandPaletteContext,
  CommandPaletteContextType,
} from '../../hooks/useCommandPaletteContext';
import { useConnectionStatus } from '../../hooks/useConnectionStatus';
import { useViewport } from '../../hooks/useIsMobile';
import { useKeyboardShortcuts } from '../../hooks/useKeyboardShortcuts';
import { useServiceStatus } from '../../hooks/useServiceStatus';
import { SidebarContext, SidebarContextType } from '../../hooks/useSidebarContext';
import { useVerdictEngineStatus } from '../../hooks/useVerdictEngineStatus';
import { ConnectionStatusBanner } from '../common';
import CommandPalette from '../common/CommandPalette';
import { ServiceStatusAlert } from '../common/ServiceStatusAlert';
import ShortcutsHelpModal from '../common/ShortcutsHelpModal';
import { SkipLinkGroup, type SkipTarget } from '../common/SkipLink';
import VerdictEngineStatusBanner from '../common/VerdictEngineStatusBanner';

/**
 * Skip link targets for keyboard navigation accessibility
 * These IDs correspond to landmark elements in the layout
 */
const SKIP_TARGETS: SkipTarget[] = [
  { id: 'main-navigation', label: 'Skip to navigation' },
  { id: 'main-content', label: 'Skip to main content' },
];

interface LayoutProps {
  children: ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  const { services } = useServiceStatus();
  const { summary, isPollingFallback, retryConnection } = useConnectionStatus();
  // F1.2 (UR-18): verdict-engine (ai-vlm) availability for the persistent banner
  const verdictEngine = useVerdictEngineStatus();
  const [isDismissed, setIsDismissed] = useState(false);
  const [isMobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [isCommandPaletteOpen, setCommandPaletteOpen] = useState(false);
  const [isShortcutsHelpOpen, setShortcutsHelpOpen] = useState(false);

  // Use viewport hook for responsive layout (NEM-3610)
  // isMobile: Used to conditionally render mobile-only components
  // isTablet: Reserved for future tablet-specific layout adjustments
  const { isMobile } = useViewport();

  // Global keyboard shortcuts
  useKeyboardShortcuts({
    onOpenCommandPalette: useCallback(() => setCommandPaletteOpen(true), []),
    onOpenHelp: useCallback(() => setShortcutsHelpOpen(true), []),
    onEscape: useCallback(() => {
      setCommandPaletteOpen(false);
      setShortcutsHelpOpen(false);
    }, []),
    // Disable shortcuts when modals are open (they handle their own)
    enabled: !isCommandPaletteOpen && !isShortcutsHelpOpen,
  });

  const handleDismiss = useCallback(() => {
    setIsDismissed(true);
  }, []);

  const toggleMobileMenu = useCallback(() => {
    setMobileMenuOpen((prev) => !prev);
  }, []);

  const sidebarContextValue: SidebarContextType = {
    isMobileMenuOpen,
    setMobileMenuOpen,
    toggleMobileMenu,
  };

  const commandPaletteContextValue: CommandPaletteContextType = useMemo(
    () => ({
      openCommandPalette: () => setCommandPaletteOpen(true),
    }),
    []
  );

  return (
    <CommandPaletteContext.Provider value={commandPaletteContextValue}>
      <SidebarContext.Provider value={sidebarContextValue}>
        <div className="flex min-h-screen flex-col bg-[#0E0E0E]">
          {/* Skip links for keyboard navigation accessibility */}
          <SkipLinkGroup targets={SKIP_TARGETS} />
          <Header />
          <div className="flex flex-1 overflow-hidden">
            {/*
              [r130f] F-017: the Sidebar is mounted at EVERY width now; it used to be
              `{!isMobile && <Sidebar />}`. The row's clause "on mobile uses the bottom bar
              AND slide-out menu" needs the drawer below 640, but the drawer IS this component
              (its open/closed translate is the `isMobileMenuOpen` ternary in Sidebar.tsx's
              aside className), so gating its mount on `isMobile` (width < 640,
              useViewport.ts:124) unmounted the very thing the hamburger opens — a tap at
              375px rendered this file's `mobile-overlay` backdrop over an absent drawer. The
              two gates disagreed because they are two different systems: this one was JS at
              640, while the hamburger's hiding is CSS `md:hidden` (Header.tsx:287) and the
              backdrop's, a few lines below, is `md:hidden` too — all Tailwind `md` = 768. So
              CSS already spoke one dialect and this line another.

              The agreement is made by removing the JS gate rather than by moving the hamburger
              to 640, and the reason is dependency direction: MobileBottomNav's More sheet
              (its `handleNavigate`) is the phone's in-page nav, so HIDING the hamburger at 640
              would strand the hamburger's feature with no entry point, while MOUNTING the
              drawer leaves every band with a working control. The Sidebar doubles as the
              desktop rail, so it cannot be unmounted above 768 either — which lands on "always
              mounted", with the existing CSS as the single display contract: `md:relative
              md:translate-x-0` plus `isMobileMenuOpen ? 'translate-x-0' : '-translate-x-full'`
              means flush rail at >=768 and an off-canvas drawer below, exactly as designed.
              `isMobile` still earns its keep in this file: `pb-14` on main and the
              MobileBottomNav mount, both below.

              The row's own evidence named the tell: Sidebar's "Menu / Close" header is gated
              `md:hidden` alone — markup that is only reachable below 768 if the component
              mounts below 768, which this gate forbade.

              One consequence belongs here because it is invisible in a screenshot: a drawer
              hidden by a transform is still in the tab order, so the always-mounted aside
              carries an `inert` gate of its own — see the comment above `drawerIsOffCanvas` in
              Sidebar.tsx.
            */}
            <Sidebar />

            {/* Mobile overlay backdrop */}
            {isMobileMenuOpen && (
              <div
                className="fixed inset-0 z-30 bg-black/50 md:hidden"
                onClick={() => setMobileMenuOpen(false)}
                aria-hidden="true"
                data-testid="mobile-overlay"
              />
            )}
            <main
              id="main-content"
              tabIndex={-1}
              className={`flex-1 overflow-auto focus:outline-none ${isMobile ? 'pb-14' : ''}`}
              data-testid="main-content"
            >
              {/* Connection status banner - shows when WebSocket is disconnected */}
              <div className="px-4 pt-2">
                <ConnectionStatusBanner
                  connectionState={summary.overallState}
                  disconnectedSince={summary.disconnectedSince}
                  reconnectAttempts={summary.totalReconnectAttempts}
                  maxReconnectAttempts={
                    summary.eventsChannel.maxReconnectAttempts +
                    summary.systemChannel.maxReconnectAttempts
                  }
                  onRetry={retryConnection}
                  isPollingFallback={isPollingFallback}
                />
              </div>
              {!isDismissed && <ServiceStatusAlert services={services} onDismiss={handleDismiss} />}
              {/* Gate on loaded: the hook seeds 'unknown' before the first
                  readiness read settles, so an ungated render paints a false
                  engine warning on every healthy page load. */}
              {verdictEngine.loaded && (
                <VerdictEngineStatusBanner
                  className="mx-4 mb-4 mt-2"
                  state={verdictEngine.state}
                  since={verdictEngine.since}
                  reason={verdictEngine.reason}
                />
              )}
              <AdvancedBanner />
              <HubTabBar />
              <LayoutHubTabBarContext.Provider value={true}>
                {children}
              </LayoutHubTabBarContext.Provider>
            </main>
          </div>

          {/* Command Palette */}
          <CommandPalette open={isCommandPaletteOpen} onOpenChange={setCommandPaletteOpen} />

          {/* Keyboard Shortcuts Help Modal */}
          <ShortcutsHelpModal
            open={isShortcutsHelpOpen}
            onClose={() => setShortcutsHelpOpen(false)}
          />

          {/* Show mobile bottom navigation on mobile viewports */}
          {isMobile && <MobileBottomNav />}
        </div>
      </SidebarContext.Provider>
    </CommandPaletteContext.Provider>
  );
}
