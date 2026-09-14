# Forms Directory - AI Agent Guide

## Purpose

This directory contains React 19 form components that leverage the new form patterns:
- `useActionState` for managing form state with async actions
- `useFormStatus` for automatic pending state detection without prop drilling

## Key Files

| File                     | Purpose                                      |
| ------------------------ | -------------------------------------------- |
| `SubmitButton.tsx`       | Submit button with automatic pending state   |
| `SubmitButton.test.tsx`  | Tests for SubmitButton                       |
| `FormField.tsx`          | Input, textarea, select with error display   |
| `FormField.test.tsx`     | Tests for FormField components               |
| `index.ts`               | Public exports                               |

## React 19 Form Patterns

### useActionState

Replaces useState for form state management with async actions:

```typescript
import { useActionState } from 'react';
import { createFormAction, createInitialState } from '../components/forms';

const submitAction = createFormAction(async (formData) => {
  const email = formData.get('email');
  await api.subscribe(email);
  return { success: true };
});

function NewsletterForm() {
  const [state, action, isPending] = useActionState(submitAction, createInitialState());

  return (
    <form action={action}>
      <FormField
        name="email"
        label="Email"
        type="email"
        error={state.fieldErrors?.email}
        required
      />
      <SubmitButton pendingText="Subscribing...">Subscribe</SubmitButton>
    </form>
  );
}
```

### useFormStatus

Automatically detects pending state from parent form:

```typescript
import { useFormStatus } from 'react-dom';

function SubmitButton({ children }) {
  const { pending } = useFormStatus();

  return (
    <button type="submit" disabled={pending}>
      {pending ? 'Submitting...' : children}
    </button>
  );
}
```

## FormActionState

The state object returned by useActionState:

```typescript
interface FormActionState<TData = unknown> {
  status: 'idle' | 'pending' | 'success' | 'error';
  data?: TData;              // Result data on success
  error?: string;            // Error message on failure
  fieldErrors?: Record<string, string>;  // Field-level validation errors
  timestamp?: number;        // Last state change time
}
```

## Utility Functions

| Function                  | Purpose                                    |
| ------------------------- | ------------------------------------------ |
| `createFormAction`        | Factory for creating form action functions |
| `createInitialState`      | Creates initial FormActionState            |
| `extractValidationErrors` | Extracts field errors from ApiError        |
| `getErrorMessage`         | User-friendly error message extraction     |
| `isActionPending`         | Check if state is pending                  |
| `isActionSuccess`         | Check if state is success                  |
| `isActionError`           | Check if state is error                    |
| `hasFieldErrors`          | Check if state has field-level errors      |
| `getFieldError`           | Get error for specific field               |

## Component Props

### SubmitButton

```typescript
interface SubmitButtonProps {
  children: ReactNode;
  variant?: 'primary' | 'secondary' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  pendingText?: string;    // Text shown while pending
  disabled?: boolean;
  icon?: ReactNode;        // Icon shown when not pending
  pendingIcon?: ReactNode; // Icon shown when pending (defaults to spinner)
  fullWidth?: boolean;
}
```

### FormField

```typescript
interface FormFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  name: string;
  label: string;
  error?: string;          // Error message to display
  helpText?: string;       // Help text below input
  leadingIcon?: ReactNode;
  trailingIcon?: ReactNode;
}
```

## Integration with ActionErrorBoundary

For comprehensive error handling, wrap forms with ActionErrorBoundary:

```typescript
import { ActionErrorBoundary } from '../common';

function SettingsForm() {
  const [state, action] = useActionState(submitSettings, { status: 'idle' });

  return (
    <ActionErrorBoundary
      actionState={state}
      feature="Settings"
      onRetry={() => window.location.reload()}
    >
      <form action={action}>
        {/* form fields */}
      </form>
    </ActionErrorBoundary>
  );
}
```

## Testing Notes

- Mock `useFormStatus` from `react-dom` for unit tests
- Use `renderHook` from @testing-library/react for hook tests
- Test both success and error states
- Verify field error display

## Related Files

- `/frontend/src/hooks/useFormAction.ts` - Core form action utilities
- `/frontend/src/hooks/useFormAction.test.ts` - Hook tests
- `/frontend/src/components/common/ActionErrorBoundary.tsx` - Error boundary
- `/frontend/src/components/common/ActionErrorBoundary.test.tsx` - Error boundary tests

## See Also

- NEM-3356: Implement useActionState and useFormStatus for forms
- NEM-3358: Enhance Error Boundaries with Actions integration
