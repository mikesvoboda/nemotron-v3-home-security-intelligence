# Button Components

Common button components for interactive actions throughout the application.

## Button

General-purpose button component with multiple variants, sizes, and states.

**Location:** `frontend/src/components/common/Button.tsx`

### Props

```typescript
interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'outline' | 'outline-primary' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
  leftIcon?: ReactNode;
  rightIcon?: ReactNode;
  isIconOnly?: boolean;
  fullWidth?: boolean;
  children?: ReactNode;
}
```

### Variants

| Variant           | Use Case                                |
| ----------------- | --------------------------------------- |
| `primary`         | Primary actions (submit, save, confirm) |
| `secondary`       | Secondary actions                       |
| `ghost`           | Subtle actions, toolbar buttons         |
| `outline`         | Alternative to ghost with border        |
| `outline-primary` | Outlined with primary color accent      |
| `danger`          | Destructive actions (delete, remove)    |

### Usage Examples

```tsx
import { Button } from '@/components/common';
import { Plus, Save } from 'lucide-react';

<Button>Click me</Button>
<Button variant="secondary" size="lg">Large Secondary</Button>
<Button leftIcon={<Plus />}>Add Item</Button>
<Button isLoading>Saving...</Button>
<Button fullWidth>Submit Form</Button>
<Button variant="danger">Delete Item</Button>
```

### Features

- WCAG 2.1 AA compliant focus indicators
- Smooth hover and active state transitions
- Automatic disabled state when loading
- Accessible aria-busy attribute during loading
- Supports ref forwarding

---

## IconButton

Accessible icon-only button with enforced 44x44px minimum touch target (WCAG 2.5.5 AAA).

**Location:** `frontend/src/components/common/IconButton.tsx`

### Props

```typescript
interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  icon: ReactElement;
  'aria-label': string; // Required
  size?: 'sm' | 'md' | 'lg';
  variant?: 'ghost' | 'outline' | 'solid';
  isLoading?: boolean;
  isActive?: boolean;
  tooltip?: ReactNode;
  tooltipPosition?: 'top' | 'bottom' | 'left' | 'right';
}
```

### Features

- All sizes enforce minimum 44x44px touch target (WCAG 2.5.5 AAA)
- Required aria-label prop for accessibility
- Optional tooltip support with configurable position
- Loading state with spinner
- Active/pressed state styling
