# Frontend Components Directory

## Purpose

Root directory for all React components in the NVIDIA Security Intelligence home security monitoring dashboard. Components are organized by feature domain and shared functionality.

## Directory Structure

- **common/** - Shared UI components used across the application (badges, buttons, cards)
- **dashboard/** - Main dashboard page and related components
- **detection/** - Object detection visualization components (bounding boxes, detection overlays)
- **events/** - Event-related components (currently empty, placeholder for future event cards and modals)
- **layout/** - Application layout components (header, sidebar, main layout wrapper)

## Component Organization

Components are organized by feature domain to maintain clear separation of concerns:

- Layout components handle application structure and navigation
- Detection components handle AI detection visualization
- Dashboard components compose the main monitoring views
- Common components provide reusable UI primitives
- Events components will handle security event displays (Phase 5+)

## Styling Approach

All components use:

- **Tailwind CSS** for utility-first styling
- **Tremor** library for data visualization components (planned for dashboard metrics)
- **Custom dark theme** with NVIDIA brand colors:
  - Background: `#0E0E0E` (darkest) and `#1A1A1A` (panels)
  - Primary: `#76B900` (NVIDIA green)
  - Border: `gray-800` for subtle separations

## Testing

Test files are co-located with their components using the `.test.tsx` extension. All tests use:

- **Vitest** as the test runner
- **React Testing Library** for component testing
- **95% code coverage** requirement (enforced by pre-commit hooks)

## Navigation

For detailed information about components in each subdirectory, see the AGENTS.md file in that directory.
