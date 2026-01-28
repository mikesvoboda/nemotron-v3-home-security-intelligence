# Component Library Documentation

Documentation for the React component library used in the home security monitoring dashboard.

## Source Code

Component source code is located at:

```
frontend/src/components/
```

For detailed component navigation, patterns, and architecture, see [AGENTS.md](./AGENTS.md).

## Directory Structure

| Directory                                | Description                                          |
| ---------------------------------------- | ---------------------------------------------------- |
| [common/](./common/)                     | Reusable UI primitives (buttons, modals, indicators) |
| [feature-specific/](./feature-specific/) | Domain-specific component documentation              |
| [layout/](./layout/)                     | Page layout and structure components                 |
| [patterns/](./patterns/)                 | Cross-cutting implementation patterns                |

## Quick Links

### Common Components

- [Buttons](./common/buttons.md) - Button, IconButton variants and usage
- [Modals](./common/modals.md) - Modal dialogs and overlays
- [Loading States](./common/loading-states.md) - Spinners, skeletons, placeholders
- [Notifications](./common/notifications.md) - Toast notifications and alerts
- [Status Indicators](./common/status-indicators.md) - Health, connection, and state indicators
- [Error Boundaries](./common/error-boundaries.md) - Error handling and fallback UI

### Feature-Specific Components

- [Dashboard Widgets](./feature-specific/dashboard-widgets.md) - Main dashboard components
- [Event Components](./feature-specific/event-components.md) - Event list, timeline, details
- [Settings Panels](./feature-specific/settings-panels.md) - Configuration UI components

### Layout

- [Layout](./layout/layout.md) - Page structure, navigation, responsive grid

### Patterns

- [Data Display Patterns](./patterns/data-display-patterns.md) - Lists, tables, cards
- [Error Handling](./patterns/error-handling.md) - Error states and recovery
- [Form Patterns](./patterns/form-patterns.md) - Form components and validation

## Related Documentation

- [Frontend Architecture](../developer/architecture/frontend.md)
- [Testing Patterns](../developer/patterns/AGENTS.md)
- [API Client Documentation](../api/)
