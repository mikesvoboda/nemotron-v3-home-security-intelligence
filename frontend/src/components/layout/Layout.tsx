import { ReactNode, useCallback, useState } from 'react';

import Header from './Header';
import Sidebar from './Sidebar';
import { useServiceStatus } from '../../hooks/useServiceStatus';
import { ServiceStatusAlert } from '../common/ServiceStatusAlert';

interface LayoutProps {
  children: ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  const { services } = useServiceStatus();
  const [isDismissed, setIsDismissed] = useState(false);

  const handleDismiss = useCallback(() => {
    setIsDismissed(true);
  }, []);

  return (
    <div className="flex min-h-screen flex-col bg-[#0E0E0E]">
      <Header />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-auto">
          {!isDismissed && (
            <ServiceStatusAlert services={services} onDismiss={handleDismiss} />
          )}
          {children}
        </main>
      </div>
    </div>
  );
}
