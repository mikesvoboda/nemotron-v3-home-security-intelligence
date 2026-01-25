/**
 * ThemeToggle - Toggle button component for theme switching
 *
 * Provides a button with sun/moon icons to toggle between light and dark themes.
 * Supports both simple toggle and full mode selection (light/dark/system).
 *
 * @module components/common/ThemeToggle
 * @see NEM-3609
 */

import { Menu, MenuButton, MenuItem, MenuItems, Transition } from '@headlessui/react';
import { Monitor, Moon, Sun, type LucideIcon } from 'lucide-react';
import { Fragment, type ComponentProps } from 'react';

import { type ThemeMode, useTheme } from '../../hooks/useTheme';

/**
 * Props for ThemeToggle component
 */
export interface ThemeToggleProps {
  /** Show dropdown menu with all options instead of simple toggle */
  showMenu?: boolean;
  /** Additional CSS classes */
  className?: string;
  /** Size of the toggle button */
  size?: 'sm' | 'md' | 'lg';
  /** Variant style */
  variant?: 'default' | 'ghost';
  /** Callback when theme changes */
  onThemeChange?: (mode: ThemeMode) => void;
}

/**
 * Size configurations for the toggle button
 */
const sizeConfig = {
  sm: {
    button: 'h-8 w-8',
    icon: 'h-4 w-4',
    iconSun: 'h-4 w-4',
    iconMoon: 'h-4 w-4',
  },
  md: {
    button: 'h-9 w-9',
    icon: 'h-5 w-5',
    iconSun: 'h-5 w-5',
    iconMoon: 'h-5 w-5',
  },
  lg: {
    button: 'h-10 w-10',
    icon: 'h-6 w-6',
    iconSun: 'h-6 w-6',
    iconMoon: 'h-6 w-6',
  },
};

/**
 * Variant configurations for the toggle button
 */
const variantConfig = {
  default:
    'bg-gray-800 hover:bg-gray-700 border border-gray-700 hover:border-gray-600',
  ghost: 'hover:bg-gray-800',
};

/**
 * Theme icon component based on current mode
 */
function ThemeIcon({
  mode,
  resolvedTheme,
  size,
}: {
  mode: ThemeMode;
  resolvedTheme: 'light' | 'dark';
  size: 'sm' | 'md' | 'lg';
}) {
  const config = sizeConfig[size];

  if (mode === 'system') {
    return <Monitor className={config.icon} aria-hidden="true" />;
  }

  // Use resolved theme for the icon display
  if (resolvedTheme === 'dark') {
    return <Moon className={config.iconMoon} aria-hidden="true" />;
  }

  return <Sun className={config.iconSun} aria-hidden="true" />;
}

/**
 * Menu item for theme selection
 */
function ThemeMenuItem({
  mode,
  currentMode,
  label,
  icon: Icon,
  onClick,
}: {
  mode: ThemeMode;
  currentMode: ThemeMode;
  label: string;
  icon: LucideIcon;
  onClick: () => void;
}) {
  const isActive = mode === currentMode;

  return (
    <MenuItem>
      {({ focus }: { focus: boolean }) => (
        <button
          className={`flex w-full items-center gap-2 px-3 py-2 text-sm ${
            focus ? 'bg-gray-700' : ''
          } ${isActive ? 'text-primary-500' : 'text-text-secondary'}`}
          onClick={onClick}
          role="menuitemradio"
          aria-checked={isActive}
        >
          <Icon className="h-4 w-4" aria-hidden="true" />
          <span>{label}</span>
          {isActive && (
            <span className="ml-auto text-xs text-primary-500" aria-hidden="true">
              Active
            </span>
          )}
        </button>
      )}
    </MenuItem>
  );
}

/**
 * Simple toggle button that switches between light and dark
 */
function SimpleToggle({
  className = '',
  size = 'md',
  variant = 'default',
  onThemeChange,
}: Omit<ThemeToggleProps, 'showMenu'>) {
  const { mode, resolvedTheme, toggle } = useTheme();
  const config = sizeConfig[size];
  const variantClasses = variantConfig[variant];

  const handleToggle = () => {
    toggle();
    onThemeChange?.(resolvedTheme === 'dark' ? 'light' : 'dark');
  };

  return (
    <button
      onClick={handleToggle}
      className={`inline-flex items-center justify-center rounded-lg transition-colors ${config.button} ${variantClasses} ${className}`}
      aria-label={`Switch to ${resolvedTheme === 'dark' ? 'light' : 'dark'} theme`}
      data-testid="theme-toggle"
    >
      <ThemeIcon mode={mode} resolvedTheme={resolvedTheme} size={size} />
    </button>
  );
}

/**
 * Dropdown menu toggle with light/dark/system options
 */
function MenuToggle({
  className = '',
  size = 'md',
  variant = 'default',
  onThemeChange,
}: Omit<ThemeToggleProps, 'showMenu'>) {
  const { mode, resolvedTheme, setMode } = useTheme();
  const config = sizeConfig[size];
  const variantClasses = variantConfig[variant];

  const handleModeChange = (newMode: ThemeMode) => {
    setMode(newMode);
    onThemeChange?.(newMode);
  };

  return (
    <Menu as="div" className="relative">
      <MenuButton
        className={`inline-flex items-center justify-center rounded-lg transition-colors ${config.button} ${variantClasses} ${className}`}
        aria-label="Theme options"
        data-testid="theme-toggle"
      >
        <ThemeIcon mode={mode} resolvedTheme={resolvedTheme} size={size} />
      </MenuButton>

      <Transition
        as={Fragment}
        enter="transition ease-out duration-100"
        enterFrom="transform opacity-0 scale-95"
        enterTo="transform opacity-100 scale-100"
        leave="transition ease-in duration-75"
        leaveFrom="transform opacity-100 scale-100"
        leaveTo="transform opacity-0 scale-95"
      >
        <MenuItems
          className="absolute right-0 z-50 mt-2 w-36 origin-top-right rounded-lg border border-gray-700 bg-gray-800 py-1 shadow-lg focus:outline-none"
          data-testid="theme-menu"
        >
          <ThemeMenuItem
            mode="light"
            currentMode={mode}
            label="Light"
            icon={Sun}
            onClick={() => handleModeChange('light')}
          />
          <ThemeMenuItem
            mode="dark"
            currentMode={mode}
            label="Dark"
            icon={Moon}
            onClick={() => handleModeChange('dark')}
          />
          <ThemeMenuItem
            mode="system"
            currentMode={mode}
            label="System"
            icon={Monitor}
            onClick={() => handleModeChange('system')}
          />
        </MenuItems>
      </Transition>
    </Menu>
  );
}

/**
 * ThemeToggle component
 *
 * Renders either a simple toggle button or a dropdown menu with all theme options.
 *
 * @example
 * ```tsx
 * // Simple toggle (light/dark)
 * <ThemeToggle />
 *
 * // Dropdown menu with system option
 * <ThemeToggle showMenu />
 *
 * // Custom size and variant
 * <ThemeToggle size="sm" variant="ghost" />
 * ```
 */
export default function ThemeToggle({ showMenu = false, ...props }: ThemeToggleProps) {
  if (showMenu) {
    return <MenuToggle {...props} />;
  }
  return <SimpleToggle {...props} />;
}

/**
 * Props type for external use
 */
export type ThemeToggleComponentProps = ComponentProps<typeof ThemeToggle>;
