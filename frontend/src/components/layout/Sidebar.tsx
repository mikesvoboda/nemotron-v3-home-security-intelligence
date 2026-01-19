import { ChevronDown, X } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';

import { NavGroup, navGroups, STORAGE_KEY } from './sidebarNav';
import { useSidebarContext } from '../../hooks/useSidebarContext';

/** Helper to load expansion state from localStorage */
function loadExpansionState(): Record<string, boolean> {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      return JSON.parse(stored) as Record<string, boolean>;
    }
  } catch {
    // Ignore parse errors
  }
  return {};
}

/** Helper to save expansion state to localStorage */
function saveExpansionState(state: Record<string, boolean>): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // Ignore storage errors
  }
}

interface NavGroupComponentProps {
  group: NavGroup;
  isExpanded: boolean;
  onToggle: () => void;
  onNavClick: () => void;
}

function NavGroupComponent({ group, isExpanded, onToggle, onNavClick }: NavGroupComponentProps) {
  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        onToggle();
      }
    },
    [onToggle]
  );

  return (
    <div className="mb-2" data-testid={`nav-group-${group.id}`}>
      {/* Group header */}
      <button
        type="button"
        onClick={onToggle}
        onKeyDown={handleKeyDown}
        className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-xs font-semibold uppercase tracking-wider text-gray-400 transition-colors duration-200 hover:bg-gray-800 hover:text-gray-300"
        aria-expanded={isExpanded}
        aria-controls={`nav-group-content-${group.id}`}
        data-testid={`nav-group-header-${group.id}`}
      >
        <span>{group.label}</span>
        <ChevronDown
          className={`h-4 w-4 transition-transform duration-200 ${isExpanded ? 'rotate-0' : '-rotate-90'}`}
          aria-hidden="true"
        />
      </button>

      {/* Group items with animation */}
      <div
        id={`nav-group-content-${group.id}`}
        role="region"
        aria-labelledby={`nav-group-header-${group.id}`}
        className={`overflow-hidden transition-all duration-200 ease-in-out ${
          isExpanded ? 'max-h-96 opacity-100' : 'max-h-0 opacity-0'
        }`}
        data-testid={`nav-group-content-${group.id}`}
      >
        <div className="mt-1 space-y-1 pl-2">
          {group.items.map((item) => {
            const Icon = item.icon;

            return (
              <NavLink
                key={item.id}
                to={item.path}
                end={item.path === '/'}
                onClick={onNavClick}
                data-tour={item.dataTour}
                className={({ isActive }: { isActive: boolean }) =>
                  `flex w-full items-center gap-3 rounded-lg px-4 py-2.5 transition-colors duration-200 ${
                    isActive
                      ? 'bg-[#76B900] font-semibold text-black'
                      : 'text-gray-300 hover:bg-gray-800 hover:text-white'
                  } `
                }
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
        </div>
      </div>
    </div>
  );
}

export default function Sidebar() {
  const { isMobileMenuOpen, setMobileMenuOpen } = useSidebarContext();
  const location = useLocation();

  // Initialize expansion state from localStorage or defaults
  const [expansionState, setExpansionState] = useState<Record<string, boolean>>(() => {
    const stored = loadExpansionState();
    const initial: Record<string, boolean> = {};
    navGroups.forEach((group) => {
      initial[group.id] = stored[group.id] ?? group.defaultExpanded;
    });
    return initial;
  });

  // Auto-expand group when navigating to a route within it
  useEffect(() => {
    const currentPath = location.pathname;
    navGroups.forEach((group) => {
      const hasActiveRoute = group.items.some((item) => {
        if (item.path === '/') {
          return currentPath === '/';
        }
        return currentPath === item.path || currentPath.startsWith(item.path + '/');
      });
      if (hasActiveRoute && !expansionState[group.id]) {
        setExpansionState((prev) => {
          const next = { ...prev, [group.id]: true };
          saveExpansionState(next);
          return next;
        });
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- Intentionally exclude expansionState to avoid infinite loops
  }, [location.pathname]);

  const handleToggleGroup = useCallback((groupId: string) => {
    setExpansionState((prev) => {
      const next = { ...prev, [groupId]: !prev[groupId] };
      saveExpansionState(next);
      return next;
    });
  }, []);

  const handleNavClick = useCallback(() => {
    // Close mobile menu when a link is clicked
    setMobileMenuOpen(false);
  }, [setMobileMenuOpen]);

  return (
    <aside
      className={`fixed inset-y-0 left-0 z-40 flex w-64 transform flex-col border-r border-gray-800 bg-[#1A1A1A] transition-transform duration-300 ease-in-out md:relative md:translate-x-0 ${isMobileMenuOpen ? 'translate-x-0' : '-translate-x-full'} `}
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
      <nav className="flex-1 overflow-y-auto p-4" aria-label="Main navigation">
        {navGroups.map((group) => (
          <NavGroupComponent
            key={group.id}
            group={group}
            isExpanded={expansionState[group.id]}
            onToggle={() => handleToggleGroup(group.id)}
            onNavClick={handleNavClick}
          />
        ))}
      </nav>
    </aside>
  );
}
