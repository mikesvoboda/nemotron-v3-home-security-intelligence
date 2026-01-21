import { ReactNode, useCallback, useMemo, useState } from 'react';

import Header from './Header';
import MobileBottomNav from './MobileBottomNav';
import Sidebar from './Sidebar';
import {
  CommandPaletteContext,
  CommandPaletteContextType,
} from '../../hooks/useCommandPaletteContext';
import { useConnectionStatus } from '../../hooks/useConnectionStatus';
import { useIsMobile } from '../../hooks/useIsMobile';
import { useKeyboardShortcuts } from '../../hooks/useKeyboardShortcuts';
import { useServiceStatus } from '../../hooks/useServiceStatus';
import { SidebarContext, SidebarContextType } from '../../hooks/useSidebarContext';
import { ConnectionStatusBanner } from '../common';
import CommandPalette from '../common/CommandPalette';
import { ServiceStatusAlert } from '../common/ServiceStatusAlert';
import ShortcutsHelpModal from '../common/ShortcutsHelpModal';
import { SkipLink } from '../common/SkipLink';

interface LayoutProps {
  children: ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  const { services } = useServiceStatus();
  const { summary, isPollingFallback, retryConnection } = useConnectionStatus();
  const [isDismissed, setIsDismissed] = useState(false);
  const [isMobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [isCommandPaletteOpen, setCommandPaletteOpen] = useState(false);
  const [isShortcutsHelpOpen, setShortcutsHelpOpen] = useState(false);
  const isMobile = useIsMobile();

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
        {/* Skip link for keyboard navigation accessibility */}
        <SkipLink />
        <Header />
        <div className="flex flex-1 overflow-hidden">
          {/* Hide sidebar on mobile, show MobileBottomNav instead */}
          {!isMobile && <Sidebar />}

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
            {children}
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
