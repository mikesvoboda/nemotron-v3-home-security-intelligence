# Frontend Styles Directory

## Purpose

Global CSS styles and Tailwind CSS configuration for the NVIDIA-themed dark mode security dashboard. Contains the main stylesheet with custom utility classes, component styles, and theme customizations.

## Key Files

| File        | Purpose                                                     |
| ----------- | ----------------------------------------------------------- |
| `index.css` | Main stylesheet with Tailwind directives and custom classes |

## Style Structure (`index.css`)

Uses three Tailwind CSS layers: `@layer base`, `@layer components`, and `@layer utilities`.

### Base Layer (`@layer base`)

**Body Styles:**

- Background: `bg-background` (#0E0E0E)
- Text color: `text-text-primary` (white)
- Font feature settings: ligatures (`liga`) and contextual alternates (`calt`)
- Anti-aliased text rendering

**Scrollbar Customization (WebKit):**

- Track: `bg-gray-900`
- Thumb: `bg-gray-700` with `rounded-lg`
- Thumb hover: `bg-gray-600`
- 12px width/height

**Selection Color:**

- Background: `bg-primary-500/30` (green with 30% opacity)
- Text: `text-text-primary` (white)

### Components Layer (`@layer components`)

#### Card Components

| Class                | Description                                                      |
| -------------------- | ---------------------------------------------------------------- |
| `.nvidia-card`       | Standard card: rounded-xl, gray-800 border, shadow-dark-md       |
| `.nvidia-card-hover` | Card with hover: lighter border, larger shadow, 250ms transition |
| `.nvidia-panel`      | Larger panel: rounded-2xl, gray-850 border, shadow-dark-lg, p-8  |

#### Button Variants

| Class            | Description                                      |
| ---------------- | ------------------------------------------------ |
| `.btn-primary`   | NVIDIA green bg, white text, hover/active states |
| `.btn-secondary` | Gray-800 bg, hover to gray-700, active gray-600  |
| `.btn-ghost`     | Transparent, hover shows gray-800 background     |

All buttons: `rounded-lg`, `px-4 py-2`, `font-medium`, `duration-250` transition

#### Risk Badges

| Class                | Color  | Risk Score Range |
| -------------------- | ------ | ---------------- |
| `.risk-badge-low`    | Green  | 0-29             |
| `.risk-badge-medium` | Yellow | 30-59            |
| `.risk-badge-high`   | Red    | 60-100           |

Badge styling:

- 10% opacity background (`bg-risk-{level}/10`)
- Colored text (`text-risk-{level}`)
- 30% opacity border (`border-risk-{level}/30`)
- `rounded-full`, `px-3 py-1`, `text-sm font-medium`

**Note:** Critical risk level (85-100) uses the same `.risk-badge-high` styling. For visual distinction, RiskBadge component uses different colors for high vs critical programmatically.

#### Input Styles

| Class           | Description                                          |
| --------------- | ---------------------------------------------------- |
| `.nvidia-input` | Dark input: gray-850 bg, gray-700 border, focus ring |

Focus state: `ring-2 ring-primary-500`, transparent border

#### Text Utilities

| Class           | Description                       |
| --------------- | --------------------------------- |
| `.text-heading` | `font-semibold text-text-primary` |
| `.text-body`    | `text-text-secondary` (#A0A0A0)   |
| `.text-muted`   | `text-text-muted` (#707070)       |

#### Loading and Divider

| Class             | Description                         |
| ----------------- | ----------------------------------- |
| `.skeleton`       | `animate-pulse rounded bg-gray-800` |
| `.nvidia-divider` | `border-t border-gray-800`          |

#### Status Indicators

| Class             | Description                               |
| ----------------- | ----------------------------------------- |
| `.status-dot`     | Base: `h-2 w-2 rounded-full inline-block` |
| `.status-online`  | Green with glow, `animate-pulse-glow`     |
| `.status-offline` | Gray-600                                  |
| `.status-warning` | Yellow (`bg-risk-medium`)                 |
| `.status-error`   | Red (`bg-risk-high`)                      |

### Utilities Layer (`@layer utilities`)

#### Glass Morphism

```css
.glass {
  background: rgba(26, 26, 26, 0.8);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}
```

#### Text Effects

| Class                   | Description                              |
| ----------------------- | ---------------------------------------- |
| `.text-gradient-nvidia` | Green gradient text (primary-400 to 600) |

#### Glow Effects

| Class                 | Description                              |
| --------------------- | ---------------------------------------- |
| `.glow-nvidia`        | 20px green glow, 30% opacity             |
| `.glow-nvidia-strong` | Dual-layer: 30px + 60px, 50%/30% opacity |
| `.hover-glow-nvidia`  | Hover-activated glow, 400ms transition   |

#### Text Truncation

| Class               | Description                 |
| ------------------- | --------------------------- |
| `.truncate-2-lines` | Webkit line clamp (2 lines) |
| `.truncate-3-lines` | Webkit line clamp (3 lines) |

#### Scrollbar Control

| Class             | Description                                |
| ----------------- | ------------------------------------------ |
| `.scrollbar-hide` | Hides scrollbar, maintains scroll function |

Works on Firefox (`scrollbar-width: none`) and WebKit (`display: none`)

## Tailwind Theme Configuration

See `frontend/tailwind.config.js` for extended theme configuration.

### Color Palette

**Background Colors:**

- `background`: #0E0E0E (near-black)
- `panel`: #1A1A1A
- `card`: #1E1E1E

**Primary (NVIDIA Green):**

- Full 50-900 scale
- Base: #76B900

**Risk Levels:**

- `low`: #76B900 (green)
- `medium`: #FFB800 (yellow)
- `high`: #E74856 (red)

**Text Hierarchy:**

- `primary`: white (#FFFFFF)
- `secondary`: #A0A0A0
- `muted`: #707070

**Extended Grays:**

- Standard 50-950 scale
- Custom: `850` (#1A1A1A), `950` (#0A0A0A)

### Custom Spacing

| Key   | Value  |
| ----- | ------ |
| `18`  | 4.5rem |
| `88`  | 22rem  |
| `128` | 32rem  |

### Typography

- **Sans**: Inter, system fonts
- **Mono**: JetBrains Mono, Fira Code, Consolas

### Border Radius

| Key   | Value  |
| ----- | ------ |
| `xl`  | 1rem   |
| `2xl` | 1.5rem |

### Custom Shadows

| Shadow        | Description                   |
| ------------- | ----------------------------- |
| `dark-sm`     | Subtle dark shadow            |
| `dark`        | Standard dark shadow          |
| `dark-md`     | Medium dark shadow            |
| `dark-lg`     | Large dark shadow             |
| `dark-xl`     | Extra large dark shadow       |
| `nvidia-glow` | Green glow shadow for accents |

### Animations

| Animation    | Description                  |
| ------------ | ---------------------------- |
| `pulse-glow` | 2s infinite green glow pulse |
| `slide-in`   | 0.3s slide from right        |
| `fade-in`    | 0.2s fade in                 |

### Grid Templates

| Template      | Description                 |
| ------------- | --------------------------- |
| `dashboard`   | Auto-fit minmax(300px, 1fr) |
| `camera-grid` | Auto-fit minmax(280px, 1fr) |

## Usage Examples

### Card Styles

```tsx
<div className="nvidia-card">
  <h2 className="text-heading">Card Title</h2>
  <p className="text-body">Card content</p>
</div>

<div className="nvidia-card-hover cursor-pointer">
  <h2 className="text-heading">Clickable Card</h2>
</div>
```

### Risk Badges

```tsx
<span className="risk-badge-low">Low Risk</span>
<span className="risk-badge-medium">Medium Risk</span>
<span className="risk-badge-high">High Risk</span>
```

### Status Indicators

```tsx
<div className="flex items-center gap-2">
  <span className="status-online" />
  <span>System Online</span>
</div>

<div className="flex items-center gap-2">
  <span className="status-error" />
  <span>Camera Offline</span>
</div>
```

### Glass Effect

```tsx
<div className="glass rounded-xl p-6">Semi-transparent panel with blur</div>
```

### Input with Focus Ring

```tsx
<input type="text" className="nvidia-input w-full" placeholder="Search events..." />
```

### Loading Skeleton

```tsx
<div className="space-y-2">
  <div className="skeleton h-4 w-3/4" />
  <div className="skeleton h-4 w-1/2" />
</div>
```

## Related Files

- `/frontend/tailwind.config.js` - Tailwind theme configuration
- `/frontend/postcss.config.js` - PostCSS configuration
- `/frontend/src/main.tsx` - Imports this stylesheet

## Notes

- All colors follow NVIDIA brand guidelines
- Dark theme optimized for low-light environments (security monitoring)
- GPU-accelerated animations where possible (`transform`, `opacity`)
- Accessibility: proper contrast ratios maintained (WCAG AA)
- Responsive design utilities via Tailwind's built-in classes
- Custom animations use `@keyframes` for performance
- Webkit-specific styles have fallbacks for Firefox
- Transition duration utility classes: `duration-250`, `duration-400`
- Test CSS classes using `toHaveClass()` matcher in Vitest
