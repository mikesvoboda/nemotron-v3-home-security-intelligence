# Model Configuration Forms Directory

## Purpose

Contains model-specific configuration form components for each AI model in the prompt management system. Each form provides tailored input controls appropriate for the model's configuration parameters.

## Files

| File                            | Purpose                                                | Status |
| ------------------------------- | ------------------------------------------------------ | ------ |
| `NemotronConfigForm.tsx`        | Form for editing Nemotron model configuration          | Active |
| `NemotronConfigForm.test.tsx`   | Test suite for NemotronConfigForm                      | Active |
| `Florence2ConfigForm.tsx`       | Form for editing Florence-2 model configuration        | Active |
| `Florence2ConfigForm.test.tsx`  | Test suite for Florence2ConfigForm                     | Active |
| `YoloWorldConfigForm.tsx`       | Form for editing YOLO-World model configuration        | Active |
| `YoloWorldConfigForm.test.tsx`  | Test suite for YoloWorldConfigForm                     | Active |
| `XClipConfigForm.tsx`           | Form for editing X-CLIP model configuration            | Active |
| `XClipConfigForm.test.tsx`      | Test suite for XClipConfigForm                         | Active |
| `FashionClipConfigForm.tsx`     | Form for editing Fashion-CLIP model configuration      | Active |
| `FashionClipConfigForm.test.tsx`| Test suite for FashionClipConfigForm                   | Active |
| `index.ts`                      | Barrel exports for model form components               | Active |

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

---

### Florence2ConfigForm.tsx

**Purpose:** Form for editing Florence-2 (scene analysis) configuration

**Props Interface:**

```typescript
interface Florence2ConfigFormProps {
  config: Florence2Config;
  onChange: (config: Florence2Config) => void;
  disabled?: boolean;
}
```

**Configuration Fields:**
- `queries` - List of scene analysis queries (add/remove with Enter key support)

**Usage:**

```tsx
<Florence2ConfigForm
  config={{ queries: ['What objects are in this scene?'] }}
  onChange={setConfig}
/>
```

---

### YoloWorldConfigForm.tsx

**Purpose:** Form for editing YOLO-World (object detection) configuration

**Props Interface:**

```typescript
interface YoloWorldConfigFormProps {
  config: YoloWorldConfig;
  onChange: (config: YoloWorldConfig) => void;
  disabled?: boolean;
}
```

**Configuration Fields:**
- `classes` - Tag input for custom object classes (pill-style tags)
- `confidence_threshold` - Slider for detection confidence (0-1, step 0.05)

**Usage:**

```tsx
<YoloWorldConfigForm
  config={{ classes: ['person', 'car'], confidence_threshold: 0.5 }}
  onChange={setConfig}
/>
```

---

### XClipConfigForm.tsx

**Purpose:** Form for editing X-CLIP (action recognition) configuration

**Props Interface:**

```typescript
interface XClipConfigFormProps {
  config: XClipConfig;
  onChange: (config: XClipConfig) => void;
  disabled?: boolean;
}
```

**Configuration Fields:**
- `action_classes` - Tag input for action recognition classes (pill-style tags)

**Usage:**

```tsx
<XClipConfigForm
  config={{ action_classes: ['walking', 'running', 'standing'] }}
  onChange={setConfig}
/>
```

---

### FashionClipConfigForm.tsx

**Purpose:** Form for editing Fashion-CLIP (clothing analysis) configuration

**Props Interface:**

```typescript
interface FashionClipConfigFormProps {
  config: ExtendedFashionClipConfig;
  onChange: (config: ExtendedFashionClipConfig) => void;
  disabled?: boolean;
}
```

**Configuration Fields:**
- `clothing_categories` - Tag input for clothing categories (gray pills)
- `suspicious_indicators` - Tag input for suspicious clothing indicators (red pills)

**Usage:**

```tsx
<FashionClipConfigForm
  config={{
    clothing_categories: ['hoodie', 'mask', 'uniform'],
    suspicious_indicators: ['face covering', 'all black']
  }}
  onChange={setConfig}
/>
```

## Patterns

### Controlled Components

All forms are controlled components that receive `config` and `onChange` props. State is managed by the parent (`PromptConfigEditor`).

### Tag Input Pattern

Several forms (YoloWorld, XClip, FashionClip) use a consistent tag input pattern:
- Display existing items as pill-style tags with X button for removal
- Text input with Add button for adding new items
- Enter key support for quick addition
- Duplicate prevention

### Callback Memoization

All event handlers are memoized with `useCallback` to prevent unnecessary re-renders.

### Accessibility

All form inputs have associated labels via `htmlFor` or `aria-labelledby` attributes.

## Model Configuration Types

| Model       | Primary Use             | Key Config Parameters                    |
| ----------- | ----------------------- | ---------------------------------------- |
| Nemotron    | Risk analysis LLM       | system_prompt, temperature, max_tokens   |
| Florence-2  | Scene analysis          | queries (VQA questions)                  |
| YOLO-World  | Object detection        | classes, confidence_threshold            |
| X-CLIP      | Action recognition      | action_classes                           |
| Fashion-CLIP| Clothing analysis       | clothing_categories, suspicious_indicators |

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
