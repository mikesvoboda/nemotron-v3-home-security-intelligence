# Model Configuration Forms Directory

## Purpose

Contains model-specific configuration form components for each AI model in the prompt management system. Each form provides tailored input controls appropriate for the model's configuration parameters.

## Files

| File                          | Purpose                                       | Status |
| ----------------------------- | --------------------------------------------- | ------ |
| `NemotronConfigForm.tsx`      | Form for editing Nemotron model configuration | Active |
| `NemotronConfigForm.test.tsx` | Test suite for NemotronConfigForm             | Active |
| `index.ts`                    | Barrel exports for model form components      | Active |

(B3.3 box 4 / R2a row 27 retired the Florence2/YoloWorld/XClip/FashionClip forms with their enum
values — nemotron is the only editable model left.)

## Key Components

### NemotronConfigForm.tsx

**Purpose:** Form for editing Nemotron (risk analysis LLM) configuration

**Props Interface:**

```typescript
interface NemotronConfigFormProps {
  config: ExtendedNemotronConfig;
  onChange: (config: ExtendedNemotronConfig) => void;
  disabled?: boolean;
}
```

**Configuration Fields:**

- `system_prompt` - Textarea for the AI system prompt (10 rows)
- `temperature` - Slider for generation temperature (0-2, step 0.1)
- `max_tokens` - Number input for maximum tokens (100-8192)

**Usage:**

```tsx
<NemotronConfigForm
  config={{ system_prompt: 'You are...', temperature: 0.7 }}
  onChange={setConfig}
/>
```

## Patterns

### Controlled Components

The form is a controlled component that receives `config` and `onChange` props. State is managed by the parent (`PromptConfigEditor`).

### Callback Memoization

All event handlers are memoized with `useCallback` to prevent unnecessary re-renders.

### Accessibility

All form inputs have associated labels via `htmlFor` or `aria-labelledby` attributes.

## Model Configuration Types

| Model    | Primary Use       | Key Config Parameters                  |
| -------- | ----------------- | -------------------------------------- |
| Nemotron | Risk analysis LLM | system_prompt, temperature, max_tokens |

## Dependencies

- `@tremor/react` - Textarea, NumberInput, TextInput, Button
- `lucide-react` - Plus, X icons
- `react` - useCallback, useState, useMemo
- `../../../../types/promptManagement` - Config type definitions

## Entry Points

**Start here:** `index.ts` - Barrel exports for all forms
**Parent component:** `../PromptConfigEditor.tsx` - Renders these forms based on model type

## Related Issues

- NEM-2697 - Build Prompt Management page
