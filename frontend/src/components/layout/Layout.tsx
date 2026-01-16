import { ReactNode, useCallback, useState } from 'react';

import Header from './Header';
import MobileBottomNav from './MobileBottomNav';
import Sidebar from './Sidebar';
import { useIsMobile } from '../../hooks/useIsMobile';
import { useKeyboardShortcuts } from '../../hooks/useKeyboardShortcuts';
import { useServiceStatus } from '../../hooks/useServiceStatus';
import { SidebarContext, SidebarContextType } from '../../hooks/useSidebarContext';
import CommandPalette from '../common/CommandPalette';
import { ServiceStatusAlert } from '../common/ServiceStatusAlert';
import ShortcutsHelpModal from '../common/ShortcutsHelpModal';

interface LayoutProps {
  children: ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  const { services } = useServiceStatus();
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

  return (
    <SidebarContext.Provider value={sidebarContextValue}>
      <div className="flex min-h-screen flex-col bg-[#0E0E0E]">
        {/* Skip link for keyboard navigation accessibility */}
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-[#76B900] focus:px-4 focus:py-2 focus:font-medium focus:text-black focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#0E0E0E]"
          data-testid="skip-link"
        >
          Skip to main content
        </a>
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
  );
}
