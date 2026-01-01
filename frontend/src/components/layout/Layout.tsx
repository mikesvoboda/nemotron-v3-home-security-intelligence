import { ReactNode, useCallback, useState } from 'react';

import Header from './Header';
import Sidebar from './Sidebar';
import { useServiceStatus } from '../../hooks/useServiceStatus';
import { SidebarContext, SidebarContextType } from '../../hooks/useSidebarContext';
import { ServiceStatusAlert } from '../common/ServiceStatusAlert';

interface LayoutProps {
  children: ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  const { services } = useServiceStatus();
  const [isDismissed, setIsDismissed] = useState(false);
  const [isMobileMenuOpen, setMobileMenuOpen] = useState(false);

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
        <Header />
        <div className="flex flex-1 overflow-hidden">
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
          <main className="flex-1 overflow-auto">
            {!isDismissed && (
              <ServiceStatusAlert services={services} onDismiss={handleDismiss} />
            )}
            {children}
          </main>
        </div>
      </div>
    </SidebarContext.Provider>
  );
}
