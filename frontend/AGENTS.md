# Frontend Directory - AI Agent Guide

## Purpose

This is the root directory of the React frontend application for the Home Security Intelligence Dashboard. It contains all configuration files, build tooling, dependencies, and the source code for the web-based UI that displays security camera feeds, AI detections, and risk assessments.

## Directory Structure

```
frontend/
  src/                    # Application source code (see src/AGENTS.md)
    components/           # React components organized by feature
    hooks/                # Custom React hooks
    services/             # API client and logging
    styles/               # Global CSS and Tailwind
    test/                 # Test setup
    types/                # TypeScript types (generated from OpenAPI)
    utils/                # Utility functions
    __tests__/            # Additional test files
  public/                 # Static assets (see public/AGENTS.md)
  tests/                  # Test organization
    e2e/                  # Playwright E2E tests
  node_modules/           # Installed dependencies (git-ignored)
  dist/                   # Production build output (git-ignored)
  coverage/               # Test coverage reports (git-ignored)
```

## Key Configuration Files

### Build and Development

| File                   | Purpose                                     |
| ---------------------- | ------------------------------------------- |
| `package.json`         | Project manifest, dependencies, npm scripts |
| `vite.config.ts`       | Vite bundler and test configuration         |
| `tsconfig.json`        | TypeScript compiler settings                |
| `tsconfig.node.json`   | TypeScript config for Node.js tooling       |
| `postcss.config.js`    | PostCSS plugins (Tailwind, Autoprefixer)    |
| `tailwind.config.js`   | Tailwind CSS theme with NVIDIA colors       |
| `playwright.config.ts` | Playwright E2E test configuration           |

### Code Quality

| File              | Purpose                                             |
| ----------------- | --------------------------------------------------- |
| `.eslintrc.cjs`   | ESLint rules (TypeScript, React, a11y, imports)     |
| `.prettierrc`     | Prettier formatting (single quotes, 100 char width) |
| `.prettierignore` | Files excluded from Prettier                        |

### Docker and Deployment

| File              | Purpose                                         |
| ----------------- | ----------------------------------------------- |
| `Dockerfile`      | Development container (Node 20.19.6-alpine3.23) |
| `Dockerfile.prod` | Production multi-stage build with nginx         |
| `nginx.conf`      | Nginx configuration for production              |
| `.dockerignore`   | Files excluded from Docker builds               |

### Entry Point

| File         | Purpose                                 |
| ------------ | --------------------------------------- |
| `index.html` | HTML entry point, loads `/src/main.tsx` |

### Documentation

| File                 | Purpose                                  |
| -------------------- | ---------------------------------------- |
| `TESTING.md`         | Comprehensive testing documentation      |
| `TEST_QUICKSTART.md` | Quick reference for running tests        |
| `verify-eslint.sh`   | ESLint configuration verification script |
| `lighthouserc.js`    | Lighthouse CI configuration              |

## NPM Scripts

```bash
# Development
npm run dev              # Start Vite dev server (port 5173)
npm run preview          # Preview production build

# Build
npm run build            # TypeScript check + production build

# Code Quality
npm run lint             # Run ESLint (max 0 warnings)
npm run lint:fix         # Auto-fix ESLint issues
npm run format           # Format code with Prettier
npm run format:check     # Check formatting without changes
npm run typecheck        # Run TypeScript compiler (no emit)

# Testing
npm test                 # Run Vitest tests in watch mode
npm run test:ui          # Open Vitest UI
npm run test:coverage    # Run tests with coverage report
npm run test:e2e         # Run Playwright E2E tests
npm run test:e2e:headed  # Run E2E tests with browser visible
npm run test:e2e:debug   # Debug E2E tests
npm run test:e2e:report  # Show Playwright test report

# Type Generation
npm run generate-types        # Regenerate TypeScript types from backend OpenAPI
npm run generate-types:check  # Check if types are up to date

# Full Validation
npm run validate         # typecheck + lint + test with coverage
```

## Dependencies

### Production

| Package             | Version  | Purpose                       |
| ------------------- | -------- | ----------------------------- |
| `react`             | ^19.2.3  | UI library                    |
| `react-dom`         | ^19.2.3  | React DOM renderer            |
| `react-router-dom`  | ^7.11.0  | Client-side routing           |
| `@tremor/react`     | ^3.17.4  | Data visualization components |
| `@headlessui/react` | ^2.2.9   | Accessible UI components      |
| `lucide-react`      | ^0.562.0 | Icon library                  |
| `clsx`              | ^2.1.0   | Conditional class names       |
| `tailwind-merge`    | ^3.4.0   | Merge Tailwind classes        |

### Development

| Package                       | Version | Purpose                        |
| ----------------------------- | ------- | ------------------------------ |
| `vite`                        | ^7.3.0  | Build tool and dev server      |
| `vitest`                      | ^4.0.16 | Testing framework              |
| `typescript`                  | ^5.3.3  | Type checking                  |
| `@vitejs/plugin-react`        | ^4.4.1  | Vite React plugin              |
| `tailwindcss`                 | ^3.4.1  | CSS framework                  |
| `eslint`                      | ^8.56.0 | Linting                        |
| `prettier`                    | ^3.2.4  | Code formatting                |
| `@playwright/test`            | ^1.57.0 | E2E testing                    |
| `openapi-typescript`          | ^7.10.1 | OpenAPI to TypeScript types    |
| `@testing-library/react`      | ^16.3.1 | React testing utilities        |
| `@testing-library/jest-dom`   | ^6.2.0  | DOM matchers                   |
| `@testing-library/user-event` | ^14.5.2 | User interaction simulation    |
| `jsdom`                       | ^27.3.0 | Browser environment simulation |
| `@vitest/coverage-v8`         | ^4.0.16 | Code coverage                  |

## Vite Configuration

The `vite.config.ts` configures:

- **Dev Server**: Port 5173 (strictPort: true)
- **API Proxy**: `/api/*` -> `http://localhost:8000`
- **WebSocket Proxy**: `/ws/*` -> `ws://localhost:8000`
- **Test Environment**: jsdom with globals
- **Coverage Thresholds**: 92% statements, 88% branches, 90% functions, 93% lines
- **Memory Optimization**: Uses forks pool with single fork

## TypeScript Configuration

Strict mode enabled with:

- `strict: true`
- `noUnusedLocals: true`
- `noUnusedParameters: true`
- `noFallthroughCasesInSwitch: true`
- Target: ES2020
- Module: ESNext with bundler resolution
- JSX: react-jsx (new transform)

## Tailwind Theme

Custom NVIDIA-themed dark design system:

### Colors

- **Background**: `#0E0E0E` (background), `#1A1A1A` (panel), `#1E1E1E` (card)
- **Primary**: `#76B900` (NVIDIA Green) with full shade range
- **Risk Levels**: low `#76B900`, medium `#FFB800`, high `#E74856`
- **Text**: primary `#FFFFFF`, secondary `#A0A0A0`, muted `#707070`

### Custom Animations

- `pulse-glow`: Pulsing NVIDIA green glow
- `slide-in`: Slide in from right
- `fade-in`: Fade in animation

### Custom Shadows

- `dark-*`: Dark theme shadows
- `nvidia-glow`: Green glow effect

## ESLint Configuration

Extends:

- `eslint:recommended`
- `plugin:@typescript-eslint/recommended`
- `plugin:@typescript-eslint/recommended-requiring-type-checking`
- `plugin:react/recommended`
- `plugin:react-hooks/recommended`
- `plugin:jsx-a11y/recommended`
- `plugin:import/recommended`

Key rules:

- No floating promises
- Import ordering with alphabetical sorting
- No console.log (warn/error allowed)
- Relaxed rules for test files

## Prettier Configuration

```json
{
  "semi": true,
  "singleQuote": true,
  "tabWidth": 2,
  "trailingComma": "es5",
  "printWidth": 100,
  "endOfLine": "lf",
  "plugins": ["prettier-plugin-tailwindcss"],
  "tailwindFunctions": ["clsx", "cn", "twMerge"]
}
```

## Playwright E2E Testing

Configuration in `playwright.config.ts`:

- Test directory: `./tests/e2e`
- Browser: Chromium only (for smoke tests)
- Base URL: `http://localhost:5173`
- Auto-starts dev server before tests
- Captures screenshots/videos on failure
- Trace collection on first retry

## API Types

TypeScript types are **auto-generated from backend OpenAPI specification**:

- Source: Backend Pydantic schemas via OpenAPI
- Generated files: `src/types/generated/api.ts`, `src/types/generated/index.ts`
- Regenerate: `npm run generate-types`
- Check freshness: `npm run generate-types:check`

Import types from `src/services/api.ts` which re-exports all generated types.

## Docker Configuration

### Development (`Dockerfile`)

- Base: node:20.19.6-alpine3.23
- Runs Vite dev server on port 5173
- Runs as non-root user for security

### Production (`Dockerfile.prod`)

- Multi-stage build
- Stage 1: Build with Node.js
- Stage 2: Serve with nginx:1.28.1-alpine3.23
- Includes health check endpoint
- Gzip compression and security headers

## Integration with Backend

- Backend API runs on port 8000 (FastAPI)
- Frontend consumes REST endpoints at `/api/*`
- Real-time updates via WebSocket at `/ws/*`
- Media files served from `/api/media/*`
- Dev server proxies all API/WS requests to backend

## Application Routes

Defined in `src/App.tsx`:

| Path        | Component              | Description                              |
| ----------- | ---------------------- | ---------------------------------------- |
| `/`         | `DashboardPage`        | Main dashboard with real-time monitoring |
| `/timeline` | `EventTimeline`        | Chronological event list                 |
| `/alerts`   | `AlertsPage`           | Alert management                         |
| `/entities` | `EntitiesPage`         | Entity tracking                          |
| `/logs`     | `LogsDashboard`        | Application logs viewer                  |
| `/system`   | `SystemMonitoringPage` | System health and metrics                |
| `/settings` | `SettingsPage`         | Application settings                     |

## Entry Points for Understanding the Code

1. **Start here**: Read this file for configuration overview
2. **Source code**: Navigate to `src/AGENTS.md` for component structure
3. **Configuration**: Check `vite.config.ts`, `tsconfig.json`, `.eslintrc.cjs`
4. **Styling**: Examine `tailwind.config.js` for NVIDIA theme
5. **Testing**: Review `TESTING.md` for test patterns

## Notes for AI Agents

- **Testing is mandatory**: All features need tests with coverage thresholds enforced
- **Pre-commit hooks**: Code must pass ESLint (0 warnings), TypeScript, and Prettier
- **NVIDIA branding**: Use NVIDIA green (`#76B900`) for primary actions
- **Dark theme**: All UI uses dark backgrounds
- **Component co-location**: Test files live alongside source files (`*.test.tsx`)
- **Type safety**: Use generated types from backend OpenAPI spec
- **No inline styles**: Use Tailwind utilities or custom CSS classes
- **Accessibility**: jsx-a11y rules are enforced
