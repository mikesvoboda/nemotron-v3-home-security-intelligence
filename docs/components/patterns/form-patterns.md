# Form Patterns

> Patterns for form validation, submission, and user input.

---

## Overview

Forms in this application use a combination of React Hook Form for state management, Zod for validation schemas, and custom components for consistent styling.

## Form Stack

| Library             | Purpose                   |
| ------------------- | ------------------------- |
| react-hook-form     | Form state and submission |
| @hookform/resolvers | Zod integration           |
| zod                 | Schema validation         |
| Custom components   | FormField, SubmitButton   |

---

## Components

### FormField

Self-contained form field: label, input, error, and help text in one component. It renders its own `<input>` (there is no `children` slot) and spreads the remaining `InputHTMLAttributes` onto it. `FormTextarea` and `FormSelect` (which does take `children` for `<option>` elements) live in the same file.

**Location:** `frontend/src/components/forms/FormField.tsx`

**Props (`FormFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'id'>`):**

| Prop           | Type                  | Default | Description                                                                 |
| -------------- | --------------------- | ------- | --------------------------------------------------------------------------- |
| name           | `string`              | -       | Field name (used for form data)                                             |
| label          | `string`              | -       | Field label                                                                 |
| error          | `string`              | -       | Error message                                                               |
| helpText       | `string`              | -       | Help text displayed below the input                                         |
| required       | `boolean`             | `false` | Required indicator                                                          |
| className      | `string`              | -       | Class for the wrapper                                                       |
| inputClassName | `string`              | -       | Class for the input                                                         |
| leadingIcon    | `ReactNode`           | -       | Leading icon/element                                                        |
| trailingIcon   | `ReactNode`           | -       | Trailing icon/element                                                       |
| data-testid    | `string`              | -       | Test ID                                                                     |
| ...input attrs | `InputHTMLAttributes` | -       | `type`, `placeholder`, `value`, `onChange`, etc. are forwarded to the input |

Like `SubmitButton`, it reads the parent form's pending state via `useFormStatus()` and disables itself while pending.

**Usage:**

```tsx
import { FormField } from '@/components/forms';

<FormField
  name="email"
  label="Email Address"
  type="email"
  error={errors.email?.message}
  required
  helpText="We'll never share your email"
  {...register('email')}
/>;
```

---

### SubmitButton

Form submit button that detects submission automatically through React 19's `useFormStatus()` - there is **no `loading` prop**. It must be rendered inside the `<form>` whose submission it tracks.

**Location:** `frontend/src/components/forms/SubmitButton.tsx`

**Props:**

| Prop        | Type                                   | Default | Description                                |
| ----------- | -------------------------------------- | ------- | ------------------------------------------ |
| children    | `ReactNode`                            | -       | Button content                             |
| variant     | `'primary' \| 'secondary' \| 'danger'` | -       | Visual style variant                       |
| size        | `'sm' \| 'md' \| 'lg'`                 | -       | Button size                                |
| pendingText | `string`                               | -       | Text shown while the form is pending       |
| pendingIcon | `ReactNode`                            | -       | Icon shown while pending (default Loader2) |
| icon        | `ReactNode`                            | -       | Icon before the text                       |
| disabled    | `boolean`                              | -       | Extra disable (besides pending state)      |
| fullWidth   | `boolean`                              | -       | Full-width button                          |
| className   | `string`                               | -       | Additional class names                     |

**Usage:**

```tsx
import { SubmitButton } from '@/components/forms';

<form action={action}>
  <SubmitButton pendingText="Saving...">Save Changes</SubmitButton>
</form>;
```

---

## Form Pattern Examples

### Basic Form with Validation

```tsx
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { FormField, SubmitButton } from '@/components/forms';
import { useToast } from '@/hooks/useToast';

const schema = z.object({
  name: z.string().min(1, 'Name is required'),
  email: z.email('Invalid email address'),
  threshold: z.number().min(0).max(100),
});

type FormData = z.infer<typeof schema>;

function SettingsForm() {
  const { success, error: showError } = useToast();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: '',
      email: '',
      threshold: 50,
    },
  });

  const onSubmit = async (data: FormData) => {
    try {
      await saveSettings(data);
      success('Settings saved');
    } catch (err) {
      showError('Failed to save settings');
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      <FormField
        name="name"
        label="Name"
        error={errors.name?.message}
        required
        {...register('name')}
      />

      <FormField
        name="email"
        label="Email"
        type="email"
        error={errors.email?.message}
        required
        {...register('email')}
      />

      <FormField
        name="threshold"
        label="Risk Threshold"
        type="number"
        error={errors.threshold?.message}
        helpText="0-100 scale"
        min={0}
        max={100}
        {...register('threshold', { valueAsNumber: true })}
      />

      <SubmitButton>Save Settings</SubmitButton>
    </form>
  );
}
```

---

### Form with Server-Side Validation

```tsx
function AlertRuleForm({ ruleId }: { ruleId?: string }) {
  const { success, error: showError } = useToast();
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<AlertRuleFormData>({
    resolver: zodResolver(alertRuleSchema),
  });

  const onSubmit = async (data: AlertRuleFormData) => {
    try {
      const result = await saveAlertRule(data);

      if (result.errors) {
        // Handle server-side validation errors
        Object.entries(result.errors).forEach(([field, message]) => {
          setError(field as keyof AlertRuleFormData, {
            type: 'server',
            message: message as string,
          });
        });
        return;
      }

      success('Alert rule saved');
    } catch (err) {
      showError('Failed to save alert rule');
    }
  };

  return <form onSubmit={handleSubmit(onSubmit)}>{/* Form fields */}</form>;
}
```

---

### Form with Optimistic Updates

```tsx
function EntityLabelForm({ entity }: { entity: Entity }) {
  const queryClient = useQueryClient();
  const { error: showError } = useToast();

  const mutation = useMutation({
    mutationFn: updateEntityLabel,
    onMutate: async (newLabel) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries(['entity', entity.id]);

      // Snapshot previous value
      const previousEntity = queryClient.getQueryData(['entity', entity.id]);

      // Optimistically update
      queryClient.setQueryData(['entity', entity.id], {
        ...entity,
        label: newLabel,
      });

      return { previousEntity };
    },
    onError: (err, newLabel, context) => {
      // Rollback on error
      queryClient.setQueryData(['entity', entity.id], context?.previousEntity);
      showError('Failed to update label');
    },
    onSettled: () => {
      // Refetch to ensure consistency
      queryClient.invalidateQueries(['entity', entity.id]);
    },
  });

  const onSubmit = (data: { label: string }) => {
    mutation.mutate(data.label);
  };

  return <form onSubmit={handleSubmit(onSubmit)}>{/* Form fields */}</form>;
}
```

---

### Multi-Step Form

Generic pattern (the step components below are illustrative names, not components that exist in the tree; camera creation today is a form in `CamerasSettings` calling `createCamera()` from `services/api`):

```tsx
function CameraSetupWizard() {
  const [step, setStep] = useState(1);
  const [formData, setFormData] = useState<CameraSetupData>({});

  const handleStepSubmit = (stepData: Partial<CameraSetupData>) => {
    setFormData((prev) => ({ ...prev, ...stepData }));
    setStep((prev) => prev + 1);
  };

  const handleBack = () => {
    setStep((prev) => prev - 1);
  };

  const handleComplete = async () => {
    await createCamera(formData);
  };

  return (
    <div>
      {step === 1 && <CameraBasicsStep data={formData} onSubmit={handleStepSubmit} />}
      {step === 2 && (
        <CameraStreamStep data={formData} onSubmit={handleStepSubmit} onBack={handleBack} />
      )}
      {step === 3 && (
        <CameraZonesStep data={formData} onSubmit={handleComplete} onBack={handleBack} />
      )}
    </div>
  );
}
```

---

## Validation Patterns

### Common Zod Schemas

This project uses Zod v4 (`frontend/package.json`: `"zod": "^4.3.6"`). In v4 the
`z.string().email()` / `z.string().url()` convenience methods are deprecated in
favor of the top-level `z.email()` / `z.url()` parsers.

```tsx
// Email validation (Zod v4)
const emailSchema = z.email('Invalid email address');

// URL validation (Zod v4)
const urlSchema = z.url('Invalid URL');

// Numeric range
const thresholdSchema = z.number().min(0).max(100);

// Optional with default
const intervalSchema = z.number().optional().default(30);

// String enum
const severitySchema = z.enum(['low', 'medium', 'high', 'critical']);

// Object with refinement
const timeRangeSchema = z
  .object({
    start: z.date(),
    end: z.date(),
  })
  .refine((data) => data.end > data.start, { message: 'End time must be after start time' });
```

---

## Accessibility

- Labels linked to inputs via `htmlFor`
- Error messages linked via `aria-describedby`
- Required fields marked with `aria-required`
- Invalid fields marked with `aria-invalid`
- Focus management on validation errors
- Clear error messages that guide correction

---

## Testing Forms

```tsx
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

describe('SettingsForm', () => {
  it('shows validation errors', async () => {
    render(<SettingsForm />);

    await userEvent.click(screen.getByRole('button', { name: /save/i }));

    await waitFor(() => {
      expect(screen.getByText('Name is required')).toBeInTheDocument();
    });
  });

  it('submits valid data', async () => {
    const onSave = vi.fn();
    render(<SettingsForm onSave={onSave} />);

    await userEvent.type(screen.getByLabelText('Name'), 'Test');
    await userEvent.type(screen.getByLabelText('Email'), 'test@example.com');
    await userEvent.click(screen.getByRole('button', { name: /save/i }));

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith({
        name: 'Test',
        email: 'test@example.com',
        threshold: 50,
      });
    });
  });
});
```
