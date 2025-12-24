import { ReactNode, useState, useEffect } from 'react';

import Header from './Header';
import Sidebar from './Sidebar';

interface LayoutProps {
  children: ReactNode;
  onNavChange?: (path: string) => void;
}

export default function Layout({ children, onNavChange }: LayoutProps) {
  const [activeNav, setActiveNav] = useState('dashboard');

  // Update activeNav based on current path
  useEffect(() => {
    const path = window.location.pathname;
    const navId = path === '/' ? 'dashboard' : path.substring(1);
    setActiveNav(navId);
  }, []);

  const handleNavChange = (navId: string) => {
    setActiveNav(navId);

    // Get the path from navItems
    const navPaths: Record<string, string> = {
      dashboard: '/',
      timeline: '/timeline',
      entities: '/entities',
      alerts: '/alerts',
      logs: '/logs',
      settings: '/settings',
    };

    const path = navPaths[navId] || '/';

    if (onNavChange) {
      onNavChange(path);
    }
  };

  return (
    <div className="flex min-h-screen flex-col bg-[#0E0E0E]">
      <Header />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar activeNav={activeNav} onNavChange={handleNavChange} />
        <main className="flex-1 overflow-auto">{children}</main>
      </div>
    </div>
  );
}
