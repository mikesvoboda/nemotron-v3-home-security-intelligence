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

Reusable form field wrapper with label and error display.

**Location:** `frontend/src/components/forms/FormField.tsx`

**Props:**

| Prop     | Type        | Default | Description        |
| -------- | ----------- | ------- | ------------------ |
| name     | `string`    | -       | Field name         |
| label    | `string`    | -       | Field label        |
| error    | `string`    | -       | Error message      |
| required | `boolean`   | `false` | Required indicator |
| hint     | `string`    | -       | Help text          |
| children | `ReactNode` | -       | Input element      |

**Usage:**

```tsx
import { FormField } from '@/components/forms';

<FormField
  name="email"
  label="Email Address"
  error={errors.email?.message}
  required
  hint="We'll never share your email"
>
  <input type="email" {...register('email')} />
</FormField>;
```

---

### SubmitButton

Form submit button with loading state.

**Location:** `frontend/src/components/forms/SubmitButton.tsx`

**Props:**

| Prop     | Type        | Default  | Description            |
| -------- | ----------- | -------- | ---------------------- |
| loading  | `boolean`   | `false`  | Submission in progress |
| disabled | `boolean`   | `false`  | Disabled state         |
| children | `ReactNode` | `Submit` | Button text            |

**Usage:**

```tsx
import { SubmitButton } from '@/components/forms';

<SubmitButton loading={isSubmitting}>Save Changes</SubmitButton>;
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
  email: z.string().email('Invalid email address'),
  threshold: z.number().min(0).max(100),
});

type FormData = z.infer<typeof schema>;

function SettingsForm() {
  const { toast } = useToast();
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
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
      toast.success('Settings saved');
    } catch (error) {
      toast.error('Failed to save settings');
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      <FormField name="name" label="Name" error={errors.name?.message} required>
        <input type="text" {...register('name')} className="input" />
      </FormField>

      <FormField name="email" label="Email" error={errors.email?.message} required>
        <input type="email" {...register('email')} className="input" />
      </FormField>

      <FormField
        name="threshold"
        label="Risk Threshold"
        error={errors.threshold?.message}
        hint="0-100 scale"
      >
        <input
          type="number"
          {...register('threshold', { valueAsNumber: true })}
          className="input"
          min={0}
          max={100}
        />
      </FormField>

      <SubmitButton loading={isSubmitting}>Save Settings</SubmitButton>
    </form>
  );
}
```

---

### Form with Server-Side Validation

```tsx
function AlertRuleForm({ ruleId }: { ruleId?: string }) {
  const { toast } = useToast();
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

      toast.success('Alert rule saved');
    } catch (error) {
      toast.error('Failed to save alert rule');
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
  const { toast } = useToast();

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
      toast.error('Failed to update label');
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

```tsx
// Email validation
const emailSchema = z.string().email('Invalid email address');

// URL validation
const urlSchema = z.string().url('Invalid URL');

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
