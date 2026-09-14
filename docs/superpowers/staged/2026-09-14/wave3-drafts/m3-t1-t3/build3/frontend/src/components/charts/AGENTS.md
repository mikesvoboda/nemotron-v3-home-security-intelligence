# Charts Components

## Purpose

Reusable chart and data visualization components for the NVIDIA Security Intelligence dashboard. Provides compact visual representations of security metrics and distributions.

## Key Components

| File                         | Purpose                                                       |
| ---------------------------- | ------------------------------------------------------------- |
| `RiskDistributionMini.tsx`   | Compact horizontal stacked bar chart showing risk distribution |
| `RiskDistributionMini.test.tsx` | Test suite for RiskDistributionMini                         |
| `index.ts`                   | Barrel exports for all chart components                       |

## Component Details

### RiskDistributionMini

A mini horizontal stacked bar chart displaying the distribution of events by risk level (critical, high, medium, low).

**Props:**

| Prop           | Type                      | Description                          |
| -------------- | ------------------------- | ------------------------------------ |
| `distribution` | `RiskDistributionItem[]?` | Risk distribution data from the API  |
| `className`    | `string?`                 | Additional CSS classes               |

**Features:**

- Proportional bar widths based on count values
- Color-coded risk levels (red/orange/yellow/green)
- Accessible with ARIA labels and tooltips
- Empty state handling ("No data")
- Smooth transition animations

**Risk Level Colors:**

- `critical`: `bg-red-500`
- `high`: `bg-orange-500`
- `medium`: `bg-yellow-500`
- `low`: `bg-green-500`

**Usage:**

```tsx
import { RiskDistributionMini } from '@/components/charts';

<RiskDistributionMini
  distribution={[
    { risk_level: 'critical', count: 2 },
    { risk_level: 'high', count: 5 },
    { risk_level: 'medium', count: 12 },
    { risk_level: 'low', count: 25 },
  ]}
/>
```

## Test Coverage

The test suite covers:

- Basic rendering and structure
- Bar width proportional calculations
- Custom className application
- Risk level color mapping
- Edge cases (undefined, empty, zero counts, partial distributions)
- Accessibility (aria-labels on container and individual bars)

## Dependencies

- `clsx` - Conditional class composition
- `../../types/generated` - TypeScript types for `RiskDistributionItem`

## Styling

Uses Tailwind CSS utility classes following the NVIDIA dark theme conventions:

- Background: `bg-gray-800` for the bar container
- Label: `text-gray-400` for the "Risk Distribution" label
- Height: `h-6` fixed height bar
- Rounded corners: `rounded-lg`
