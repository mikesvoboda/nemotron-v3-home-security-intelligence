import { clsx } from 'clsx';
import { AlertTriangle, Car, Package, PawPrint, User } from 'lucide-react';

export interface ObjectTypeBadgeProps {
  type: string;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

/**
 * Maps object types to their visual properties (icon, color, display name)
 */
const objectTypeConfig: Record<
  string,
  {
    icon: typeof User;
    colors: string;
    displayName: string;
  }
> = {
  person: {
    icon: User,
    colors: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
    displayName: 'Person',
  },
  car: {
    icon: Car,
    colors: 'bg-purple-500/10 text-purple-400 border-purple-500/30',
    displayName: 'Vehicle',
  },
  truck: {
    icon: Car,
    colors: 'bg-purple-500/10 text-purple-400 border-purple-500/30',
    displayName: 'Vehicle',
  },
  bus: {
    icon: Car,
    colors: 'bg-purple-500/10 text-purple-400 border-purple-500/30',
    displayName: 'Vehicle',
  },
  motorcycle: {
    icon: Car,
    colors: 'bg-purple-500/10 text-purple-400 border-purple-500/30',
    displayName: 'Vehicle',
  },
  bicycle: {
    icon: Car,
    colors: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30',
    displayName: 'Bicycle',
  },
  dog: {
    icon: PawPrint,
    colors: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
    displayName: 'Animal',
  },
  cat: {
    icon: PawPrint,
    colors: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
    displayName: 'Animal',
  },
  bird: {
    icon: PawPrint,
    colors: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
    displayName: 'Animal',
  },
  package: {
    icon: Package,
    colors: 'bg-green-500/10 text-green-400 border-green-500/30',
    displayName: 'Package',
  },
};

/**
 * Default config for unknown object types
 */
const defaultConfig = {
  icon: AlertTriangle,
  colors: 'bg-gray-500/10 text-gray-400 border-gray-500/30',
  displayName: 'Unknown',
};

/**
 * ObjectTypeBadge component displays a badge for detected object types
 * with appropriate icon and color coding following NVIDIA dark theme
 */
export default function ObjectTypeBadge({ type, size = 'sm', className }: ObjectTypeBadgeProps) {
  const normalizedType = type.toLowerCase().trim();
  const config = objectTypeConfig[normalizedType] || {
    ...defaultConfig,
    displayName: type.charAt(0).toUpperCase() + type.slice(1),
  };

  const Icon = config.icon;

  // Size-based classes for icon and text
  const sizeClasses = {
    sm: {
      text: 'text-xs px-2 py-0.5',
      icon: 'w-3 h-3',
    },
    md: {
      text: 'text-sm px-2.5 py-1',
      icon: 'w-4 h-4',
    },
    lg: {
      text: 'text-base px-3 py-1.5',
      icon: 'w-5 h-5',
    },
  }[size];

  return (
    <span
      role="status"
      aria-label={`Detected object: ${config.displayName}`}
      className={clsx(
        'inline-flex items-center gap-1 rounded-full border font-medium',
        sizeClasses.text,
        config.colors,
        className
      )}
    >
      <Icon className={sizeClasses.icon} aria-hidden="true" />
      {config.displayName}
    </span>
  );
}
