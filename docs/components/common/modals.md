# Modal Components

Modal and dialog components for overlaying content above the main interface.

## AnimatedModal

Modal dialog with smooth open/close animations and multiple animation variants.

**Location:** `frontend/src/components/common/AnimatedModal.tsx`

### Props

```typescript
interface AnimatedModalProps {
  isOpen: boolean;
  onClose: () => void;
  children: ReactNode;
  variant?: 'scale' | 'slideUp' | 'slideDown' | 'fade';
  size?: 'sm' | 'md' | 'lg' | 'xl' | 'full';
  closeOnBackdropClick?: boolean; // default: true
  closeOnEscape?: boolean; // default: true
  className?: string;
  backdropClassName?: string;
  'aria-labelledby'?: string;
  'aria-describedby'?: string;
  modalName?: string; // For interaction tracking
}
```

### Features

- Respects prefers-reduced-motion user preference
- Renders in portal for proper z-index stacking
- Prevents body scroll when open
- Escape key closes modal (configurable)
- Backdrop click closes modal (configurable)

---

## ResponsiveModal

Wrapper that auto-switches between AnimatedModal on desktop and BottomSheet on mobile.

**Location:** `frontend/src/components/common/ResponsiveModal.tsx`

---

## BottomSheet

Mobile-optimized modal that slides up from the bottom with drag-to-dismiss.

**Location:** `frontend/src/components/common/BottomSheet.tsx`

### Features

- Spring animation on open/close
- Drag-to-dismiss with 100px threshold
- Safe area padding for notched devices
- 44x44px close button touch target
- Prevents body scroll when open

## Best Practices

1. **Always provide ARIA attributes** for accessibility
2. **Use ResponsiveModal** unless you need desktop-only or mobile-only behavior
3. **Set appropriate size** based on content
4. **Include a visible close mechanism**
