# Styling Patterns

> Tailwind CSS configuration, Tremor components, and NVIDIA dark theme implementation

## Key Files

- `frontend/tailwind.config.js:1-295` - Tailwind CSS configuration
- `frontend/src/styles/index.css:1-664` - Global CSS styles
- `frontend/src/components/common/Button.tsx:1-80` - Styled button component
- `frontend/src/theme/colors.ts:1-60` - Color constants

## Overview

The frontend uses Tailwind CSS for utility-first styling with a custom NVIDIA-inspired dark theme. Tremor provides pre-built data visualization components that integrate with the theme. The design prioritizes WCAG 2.1 AA accessibility compliance with proper contrast ratios.

## Color System

### NVIDIA Brand Colors

The primary brand color is NVIDIA Green (#76B900) with a full shade scale:

```javascript
// frontend/tailwind.config.js:32-44
primary: {
  DEFAULT: '#76B900',
  50: '#E8F5D9',
  100: '#D4EBB3',
  200: '#B8DD80',
  300: '#9CCF4D',
  400: '#89C226',
  500: '#76B900',  // Primary
  600: '#619900',
  700: '#4C7900',
  800: '#375900',
  900: '#223A00',
},
```

### Dark Theme Background Colors

```javascript
// frontend/tailwind.config.js:26-29
background: '#0E0E0E',  // Darkest - page background
panel: '#1A1A1A',       // Panel/card containers
card: '#1E1E1E',        // Card surfaces
```

### Risk Level Colors (WCAG Compliant)

Colors are brightened for 4.5:1 contrast ratio on dark backgrounds:

```javascript
// frontend/tailwind.config.js:46-55
risk: {
  low: '#76B900',      // Green - good contrast
  medium: '#FFB800',   // Amber - good contrast
  high: '#FFCDD2',     // Light coral for contrast on bg-risk-high/10
  critical: '#FFE0E0', // Very light pink for 4.5:1 on blended dark bg
},
```

### Semantic Status Colors

```javascript
// frontend/tailwind.config.js:98-130
status: {
  healthy: {
    DEFAULT: '#10B981',                    // emerald-500
    light: 'rgba(16, 185, 129, 0.1)',     // 10% for backgrounds
    text: '#34D399',                       // emerald-400 for text
    border: 'rgba(16, 185, 129, 0.3)',    // 30% for borders
  },
  warning: {
    DEFAULT: '#F59E0B',
    light: 'rgba(245, 158, 11, 0.1)',
    text: '#FBBF24',
    border: 'rgba(245, 158, 11, 0.3)',
  },
  error: {
    DEFAULT: '#EF4444',
    light: 'rgba(239, 68, 68, 0.1)',
    text: '#F87171',
    border: 'rgba(239, 68, 68, 0.3)',
  },
  inactive: {
    DEFAULT: '#6B7280',
    light: 'rgba(107, 114, 128, 0.1)',
    text: '#9CA3AF',
    border: 'rgba(107, 114, 128, 0.3)',
  },
},
```

## Typography

### Font Families

```javascript
// frontend/tailwind.config.js:142-153
fontFamily: {
  sans: [
    'Inter',
    'system-ui',
    '-apple-system',
    'BlinkMacSystemFont',
    'Segoe UI',
    'Roboto',
    'sans-serif',
  ],
  mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'Monaco', 'monospace'],
},
```

### Font Size Scale

```javascript
// frontend/tailwind.config.js:156-167
fontSize: {
  xs: ['0.75rem', { lineHeight: '1rem' }],      // 12px
  sm: ['0.875rem', { lineHeight: '1.25rem' }],  // 14px
  base: ['1rem', { lineHeight: '1.5rem' }],     // 16px
  lg: ['1.125rem', { lineHeight: '1.75rem' }],  // 18px
  xl: ['1.25rem', { lineHeight: '1.75rem' }],   // 20px
  '2xl': ['1.5rem', { lineHeight: '2rem' }],    // 24px
  '3xl': ['1.875rem', { lineHeight: '2.25rem' }], // 30px
  '4xl': ['2.25rem', { lineHeight: '2.5rem' }], // 36px
},
```

### Text Colors (WCAG Compliant)

```javascript
// frontend/tailwind.config.js:74-80
text: {
  primary: '#FFFFFF',   // White - full contrast
  secondary: '#B0B0B0', // 5.17:1 contrast on gray-700
  muted: '#919191',     // 4.81:1 contrast on #222222
},
```

## Touch Target Compliance

WCAG 2.5.5 AAA minimum touch targets (44px):

```javascript
// frontend/tailwind.config.js:11-23
minHeight: {
  11: '2.75rem',    // 44px - WCAG minimum
  12: '3rem',       // 48px - larger target
  touch: '2.75rem', // alias for 44px
},
minWidth: {
  11: '2.75rem',
  12: '3rem',
  touch: '2.75rem',
},
```

Usage with custom variants:

```javascript
// frontend/tailwind.config.js:286-293
plugins: [
  function ({ addVariant }) {
    addVariant('touch', '@media (pointer: coarse)');
    addVariant('mouse', '@media (pointer: fine)');
  },
],
```

```html
<!-- Touch devices get larger targets -->
<button class="h-10 mouse:h-10 touch:h-12">Click Me</button>
```

## Animations

### Custom Keyframes

```javascript
// frontend/tailwind.config.js:235-272
keyframes: {
  'pulse-glow': {
    '0%, 100%': { boxShadow: '0 0 10px rgba(118, 185, 0, 0.2)' },
    '50%': { boxShadow: '0 0 20px rgba(118, 185, 0, 0.4)' },
  },
  'pulse-critical': {
    '0%, 100%': { boxShadow: '0 0 8px rgba(255, 107, 107, 0.3)' },
    '50%': { boxShadow: '0 0 16px rgba(255, 107, 107, 0.6)' },
  },
  'slide-in': {
    '0%': { transform: 'translateX(100%)', opacity: '0' },
    '100%': { transform: 'translateX(0)', opacity: '1' },
  },
  'fade-in': {
    '0%': { opacity: '0' },
    '100%': { opacity: '1' },
  },
  shimmer: {
    '0%': { transform: 'translateX(-100%)' },
    '100%': { transform: 'translateX(100%)' },
  },
},
```

### Animation Classes

```javascript
// frontend/tailwind.config.js:274-283
animation: {
  'pulse-glow': 'pulse-glow 2s ease-in-out infinite',
  'pulse-critical': 'pulse-critical 2s ease-in-out infinite',
  'pulse-subtle': 'pulse-subtle 2s ease-in-out infinite',
  'slide-in': 'slide-in 0.3s ease-out',
  'fade-in': 'fade-in 0.2s ease-in',
  'ambient-pulse': 'ambient-pulse 2s ease-in-out infinite',
  shimmer: 'shimmer 1.5s ease-in-out infinite',
},
```

## Box Shadows for Dark Theme

```javascript
// frontend/tailwind.config.js:194-201
boxShadow: {
  'dark-sm': '0 1px 2px 0 rgba(0, 0, 0, 0.5)',
  dark: '0 1px 3px 0 rgba(0, 0, 0, 0.6), 0 1px 2px -1px rgba(0, 0, 0, 0.5)',
  'dark-md': '0 4px 6px -1px rgba(0, 0, 0, 0.6), 0 2px 4px -2px rgba(0, 0, 0, 0.5)',
  'dark-lg': '0 10px 15px -3px rgba(0, 0, 0, 0.6), 0 4px 6px -4px rgba(0, 0, 0, 0.5)',
  'dark-xl': '0 20px 25px -5px rgba(0, 0, 0, 0.6), 0 8px 10px -6px rgba(0, 0, 0, 0.5)',
  'nvidia-glow': '0 0 20px rgba(118, 185, 0, 0.3)',
},
```

## Tremor Components

Tremor provides data visualization components that integrate with the dark theme:

### Card Component

```tsx
import { Card, Title, Text, Metric } from '@tremor/react';

<Card className="bg-card border-gray-700">
  <Title className="text-text-primary">Active Cameras</Title>
  <Metric className="text-primary">{count}</Metric>
  <Text className="text-text-secondary">Online and monitoring</Text>
</Card>;
```

### Badge Component

```tsx
import { Badge } from '@tremor/react';

<Badge color="emerald">Healthy</Badge>
<Badge color="amber">Warning</Badge>
<Badge color="red">Critical</Badge>
```

### Chart Components

```tsx
import { AreaChart, BarChart, DonutChart } from '@tremor/react';

<AreaChart
  className="h-72"
  data={data}
  index="date"
  categories={['Events']}
  colors={['primary']}
  showLegend={false}
/>;
```

## Component Styling Patterns

### Card Pattern

```tsx
// Consistent card styling across components
<div className="rounded-lg border border-gray-700 bg-card p-4 shadow-dark">
  <h3 className="text-lg font-semibold text-text-primary">{title}</h3>
  <p className="mt-1 text-sm text-text-secondary">{description}</p>
</div>
```

### Button Variants

```tsx
// frontend/src/components/common/Button.tsx
const variants = {
  primary: 'bg-primary hover:bg-primary-600 text-white',
  secondary: 'bg-gray-700 hover:bg-gray-600 text-text-primary',
  danger: 'bg-danger hover:bg-danger-hover text-white',
  ghost: 'bg-transparent hover:bg-gray-700 text-text-primary',
};

<Button variant="primary">Save Changes</Button>
<Button variant="danger">Delete</Button>
```

### Input Styling

```tsx
// Consistent input styling
<input
  className="w-full rounded-md border border-gray-600 bg-gray-800 px-3 py-2
             text-text-primary placeholder-text-muted
             focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
  placeholder="Search events..."
/>
```

### Status Indicators

```tsx
// Using semantic status colors
<div className="flex items-center gap-2">
  <span
    className={`h-2 w-2 rounded-full ${
      status === 'healthy'
        ? 'bg-status-healthy'
        : status === 'warning'
          ? 'bg-status-warning'
          : 'bg-status-error'
    }`}
  />
  <span
    className={`text-sm ${
      status === 'healthy'
        ? 'text-status-healthy-text'
        : status === 'warning'
          ? 'text-status-warning-text'
          : 'text-status-error-text'
    }`}
  >
    {status}
  </span>
</div>
```

## Responsive Design

### Grid Layouts

```javascript
// frontend/tailwind.config.js:229-232
gridTemplateColumns: {
  dashboard: 'repeat(auto-fit, minmax(300px, 1fr))',
  'camera-grid': 'repeat(auto-fit, minmax(280px, 1fr))',
},
```

### Breakpoint Usage

```tsx
// Mobile-first responsive design
<div
  className="
  grid grid-cols-1          // Mobile: single column
  sm:grid-cols-2            // Small: 2 columns
  lg:grid-cols-3            // Large: 3 columns
  xl:grid-cols-4            // Extra large: 4 columns
  gap-4
"
>
  {cameras.map((camera) => (
    <CameraCard key={camera.id} {...camera} />
  ))}
</div>
```

### Mobile Visibility

```tsx
// Hide on mobile, show on desktop
<Sidebar className="hidden md:block" />

// Show on mobile only
<MobileBottomNav className="md:hidden" />
```

## Accessibility Patterns

### Focus Styles

```css
/* Global focus styles in index.css */
*:focus-visible {
  outline: 2px solid #76b900;
  outline-offset: 2px;
}
```

### Screen Reader Only

```tsx
// Visually hidden but accessible
<span className="sr-only">Loading, please wait</span>
```

### Color Contrast

All text colors meet WCAG 2.1 AA requirements:

| Element        | Color     | Background | Contrast Ratio |
| -------------- | --------- | ---------- | -------------- |
| Primary text   | `#FFFFFF` | `#1A1A1A`  | 15.3:1         |
| Secondary text | `#B0B0B0` | `#1A1A1A`  | 8.5:1          |
| Muted text     | `#919191` | `#1A1A1A`  | 5.8:1          |
| Risk critical  | `#FFE0E0` | `#1A1A1A`  | 12.8:1         |

## Loading States

### Skeleton Components

```tsx
// frontend/src/components/common/Skeleton.tsx
<Skeleton variant="rectangular" width="100%" height={200} className="rounded-lg" />
<Skeleton variant="text" width={192} height={32} />
<Skeleton variant="circular" width={48} height={48} />
```

### Shimmer Animation

```tsx
// Shimmer effect for loading states
<div className="relative overflow-hidden bg-gray-800 rounded-lg">
  <div
    className="absolute inset-0 -translate-x-full animate-shimmer
                  bg-gradient-to-r from-transparent via-gray-700 to-transparent"
  />
</div>
```

## Dark Mode Configuration

The theme uses `class` strategy for dark mode:

```javascript
// frontend/tailwind.config.js:2
darkMode: 'class',
```

The `dark` class is always applied to the root element since this is a dark-theme-only application.

## Related Documentation

- [Component Hierarchy](./component-hierarchy.md) - Component structure
- [Testing Patterns](./testing-patterns.md) - Visual testing
- [Frontend Hub](./README.md) - Overview

---

_Last updated: 2026-01-24 - Initial styling patterns documentation for NEM-3462_
