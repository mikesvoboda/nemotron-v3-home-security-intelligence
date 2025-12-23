import { ReactNode, useState } from 'react';

import Header from './Header';
import Sidebar from './Sidebar';

interface LayoutProps {
  children: ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  const [activeNav, setActiveNav] = useState('dashboard');

  return (
    <div className="flex min-h-screen flex-col bg-[#0E0E0E]">
      <Header />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar activeNav={activeNav} onNavChange={setActiveNav} />
        <main className="flex-1 overflow-auto">{children}</main>
      </div>
    </div>
  );
}
