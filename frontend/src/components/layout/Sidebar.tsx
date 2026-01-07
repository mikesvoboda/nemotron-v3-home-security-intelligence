import { Home, Clock, BarChart3, Users, Bell, Settings, ScrollText, Server, Shield, X, Brain, ClipboardCheck } from 'lucide-react';
import { NavLink } from 'react-router-dom';

import { useSidebarContext } from '../../hooks/useSidebarContext';

interface NavItem {
  id: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string;
  path: string;
  /** Data attribute for product tour targeting */
  dataTour?: string;
}

const navItems: NavItem[] = [
  { id: 'dashboard', label: 'Dashboard', icon: Home, path: '/' },
  { id: 'timeline', label: 'Timeline', icon: Clock, path: '/timeline', dataTour: 'timeline-link' },
  { id: 'analytics', label: 'Analytics', icon: BarChart3, path: '/analytics' },
  { id: 'entities', label: 'Entities', icon: Users, path: '/entities' },
  { id: 'alerts', label: 'Alerts', icon: Bell, path: '/alerts' },
  { id: 'logs', label: 'Logs', icon: ScrollText, path: '/logs' },
  { id: 'audit', label: 'Audit Log', icon: Shield, path: '/audit' },
  { id: 'ai', label: 'AI Performance', icon: Brain, path: '/ai' },
  { id: 'ai-audit', label: 'AI Audit', icon: ClipboardCheck, path: '/ai-audit' },
  { id: 'system', label: 'System', icon: Server, path: '/system' },
  { id: 'settings', label: 'Settings', icon: Settings, path: '/settings', dataTour: 'settings-link' },
];

export default function Sidebar() {
  const { isMobileMenuOpen, setMobileMenuOpen } = useSidebarContext();

  const handleNavClick = () => {
    // Close mobile menu when a link is clicked
    setMobileMenuOpen(false);
  };

  return (
    <aside
      className={`
        fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-gray-800 bg-[#1A1A1A]
        transform transition-transform duration-300 ease-in-out
        md:relative md:translate-x-0
        ${isMobileMenuOpen ? 'translate-x-0' : '-translate-x-full'}
      `}
      data-testid="sidebar"
    >
      {/* Mobile close button */}
      <div className="flex items-center justify-between border-b border-gray-800 px-4 py-4 md:hidden">
        <span className="text-lg font-semibold text-white">Menu</span>
        <button
          onClick={() => setMobileMenuOpen(false)}
          className="rounded-lg p-2 text-text-secondary hover:bg-gray-800 hover:text-white"
          aria-label="Close menu"
          data-testid="close-menu-button"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-2 overflow-y-auto p-4">
        {navItems.map((item) => {
          const Icon = item.icon;

          return (
            <NavLink
              key={item.id}
              to={item.path}
              end={item.path === '/'}
              onClick={handleNavClick}
              data-tour={item.dataTour}
              className={({ isActive }: { isActive: boolean }) => `
                flex w-full items-center gap-3 rounded-lg px-4 py-3
                transition-colors duration-200
                ${
                  isActive
                    ? 'bg-[#76B900] font-semibold text-black'
                    : 'text-gray-300 hover:bg-gray-800 hover:text-white'
                }
              `}
            >
              <Icon className="h-5 w-5" />
              <span className="flex-1 text-left">{item.label}</span>
              {item.badge && (
                <span className="rounded bg-yellow-500 px-2 py-0.5 text-xs font-medium text-black">
                  {item.badge}
                </span>
              )}
            </NavLink>
          );
        })}
      </nav>
    </aside>
  );
}
