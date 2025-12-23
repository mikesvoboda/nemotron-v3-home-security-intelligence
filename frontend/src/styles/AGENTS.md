# Frontend Styles Directory

## Purpose

Global CSS styles and Tailwind CSS configuration for the NVIDIA-themed dark mode security dashboard.

## Key Files

### `index.css`

Main stylesheet with Tailwind directives and custom utility classes.

## Style Structure

### Base Layer (`@layer base`)

**Body Styles:**

- Background: `#0E0E0E` (near-black)
- Text color: White with custom text hierarchy
- Font feature settings for ligatures
- Anti-aliased text rendering

**Scrollbar Customization:**

- Dark theme scrollbars (gray-900 track, gray-700 thumb)
- Hover state: gray-600
- 12px width/height

**Selection Color:**

- Primary green with 30% opacity background
- White text

### Components Layer (`@layer components`)

#### Card Components

- `.nvidia-card`: Standard card with rounded corners, gray-800 border, dark shadow
- `.nvidia-card-hover`: Card with hover effects (lighter border, larger shadow)
- `.nvidia-panel`: Larger panel with more padding and rounded-2xl corners

#### Button Variants

- `.btn-primary`: NVIDIA green buttons with hover/active states
- `.btn-secondary`: Gray buttons for secondary actions
- `.btn-ghost`: Transparent buttons with hover background

#### Risk Badges

- `.risk-badge-low`: Green badge (low risk 0-25)
- `.risk-badge-medium`: Yellow badge (medium risk 26-50)
- `.risk-badge-high`: Orange badge (high risk 51-75)

Badge styling: 10% opacity background, colored text, 30% opacity border, rounded-full

#### Input Styles

- `.nvidia-input`: Dark background, gray border, focus ring with primary-500, rounded-lg

#### Text Utilities

- `.text-heading`: Primary white text, semibold
- `.text-body`: Secondary gray text (A0A0A0)
- `.text-muted`: Muted gray text (707070)

#### Loading & Divider

- `.skeleton`: Animated pulse with gray-800 background
- `.nvidia-divider`: Gray-800 border top

#### Status Indicators

- `.status-dot`: Base 2px dot
- `.status-online`: Green with glow and pulse animation
- `.status-offline`: Gray-600
- `.status-warning`: Medium risk yellow
- `.status-error`: High risk red

### Utilities Layer (`@layer utilities`)

#### Glass Morphism

- `.glass`: Semi-transparent dark background with backdrop blur (12px)

#### Text Effects

- `.text-gradient-nvidia`: Primary-400 to primary-600 gradient text

#### Glow Effects

- `.glow-nvidia`: 20px green glow (30% opacity)
- `.glow-nvidia-strong`: Dual-layer strong glow (30px + 60px)
- `.hover-glow-nvidia`: Hover-activated glow with 400ms transition

#### Text Truncation

- `.truncate-2-lines`: Webkit line clamp (2 lines)
- `.truncate-3-lines`: Webkit line clamp (3 lines)

#### Scrollbar Control

- `.scrollbar-hide`: Hides scrollbar while maintaining scroll functionality

## Tailwind Configuration

See `/home/msvoboda/github/nemotron-v3-home-security-intelligence/frontend/tailwind.config.js` for:

### Color Palette

- **Background colors**: `background` (#0E0E0E), `panel` (#1A1A1A), `card` (#1E1E1E)
- **Primary (NVIDIA Green)**: 50-900 scale, base #76B900
- **Risk levels**: `low` (#76B900), `medium` (#FFB800), `high` (#E74856)
- **Text hierarchy**: `primary` (white), `secondary` (#A0A0A0), `muted` (#707070)
- **Extended grays**: 950-50 scale with custom values (850, 950)

### Custom Spacing

- `18`: 4.5rem
- `88`: 22rem
- `128`: 32rem

### Typography

- **Sans**: Inter, system fonts
- **Mono**: JetBrains Mono, Fira Code, Consolas

### Border Radius

- `xl`: 1rem
- `2xl`: 1.5rem

### Shadows

Custom dark theme shadows:

- `dark-sm`, `dark`, `dark-md`, `dark-lg`, `dark-xl`
- `nvidia-glow`: Green glow shadow

### Animations

- `pulse-glow`: 2s infinite green glow pulse
- `slide-in`: 0.3s slide from right
- `fade-in`: 0.2s fade in

### Grid Templates

- `dashboard`: Auto-fit minmax(300px, 1fr)
- `camera-grid`: Auto-fit minmax(280px, 1fr)

## Usage Examples

### Using Card Styles

```tsx
<div className="nvidia-card">
  <h2 className="text-heading">Card Title</h2>
  <p className="text-body">Card content</p>
</div>
```

### Risk Badge

```tsx
<span className="risk-badge-high">High Risk</span>
```

### Status Indicator

```tsx
<span className="status-online" />
<span className="ml-2">System Online</span>
```

### Glass Effect

```tsx
<div className="glass rounded-xl p-6">Semi-transparent panel with blur</div>
```

## Notes

- All colors follow NVIDIA brand guidelines
- Dark theme optimized for low-light environments
- GPU-accelerated animations where possible
- Accessibility: proper contrast ratios maintained
- Responsive design utilities via Tailwind's built-in classes
- Custom animations use `@keyframes` for performance
