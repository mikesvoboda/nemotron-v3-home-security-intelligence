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
| `vite.config.e2e.ts`   | E2E-specific Vite configuration             |
| `tsconfig.json`        | TypeScript compiler settings                |
| `tsconfig.node.json`   | TypeScript config for Node.js tooling       |
| `postcss.config.js`    | PostCSS plugins (Tailwind, Autoprefixer)    |
| `tailwind.config.js`   | Tailwind CSS theme with NVIDIA colors       |
| `playwright.config.ts` | Playwright E2E test configuration           |
| `bunfig.toml`          | Bun configuration (documents Vitest usage)  |

### Code Quality

| File                | Purpose                                             |
| ------------------- | --------------------------------------------------- |
| `eslint.config.mjs` | ESLint flat config (TypeScript, React, a11y)        |
| `.prettierrc`       | Prettier formatting (single quotes, 100 char width) |
| `.prettierignore`   | Files excluded from Prettier                        |
| `stryker.config.mjs`| Stryker mutation testing configuration              |
| `.size-limit.json`  | Bundle size monitoring configuration                |

### Docker and Deployment

| File                    | Purpose                                                                  |
| ----------------------- | ------------------------------------------------------------------------ |
| `Dockerfile`            | Multi-stage production build (build with Node, serve with nginx)         |
| `docker-entrypoint.sh`  | Container entrypoint script with runtime environment variable injection  |
| `nginx.conf`            | Nginx configuration for production (SPA routing, gzip, security headers) |
| `.dockerignore`         | Files excluded from Docker builds                                        |

### Entry Point

| File         | Purpose                                 |
| ------------ | --------------------------------------- |
| `index.html` | HTML entry point, loads `/src/main.tsx` |

### Environment and Node Version

| File     | Purpose                                          |
| -------- | ------------------------------------------------ |
| `.npmrc` | npm configuration (engine strict mode)           |
| `.nvmrc` | Node.js version specification (22 for this repo) |

### Documentation and Scripts

| File                            | Purpose                                     |
| ------------------------------- | ------------------------------------------- |
| `TESTING.md`                    | Comprehensive testing documentation         |
| `README-TESTING.md`             | Bun vs Vitest compatibility guide           |
| `TEST_QUICKSTART.md`            | Quick reference for running tests           |
| `verify-eslint.sh`              | ESLint configuration verification script    |
| `validate-storage-event-fix.js` | Storage event fix validation script         |

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
npm run test:mutation    # Run Stryker mutation testing

# IMPORTANT: Use 'npm test' or 'bun run test', NOT 'bun test'
# This project uses Vitest, not Bun's native test runner
# See bunfig.toml and TESTING.md for details

# Type Generation
npm run generate-types        # Regenerate TypeScript types from backend OpenAPI
npm run generate-types:check  # Check if types are up to date

# Code Quality
npm run dead-code        # Run Knip dead code detection

# Bundle Analysis
npm run analyze          # Generate bundle size visualization (stats.html)

# Documentation
npm run docs             # Generate TypeDoc documentation
npm run docs:watch       # Watch mode for documentation

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
| `@tanstack/react-query` | ^5.90.16 | Server state management   |
| `lucide-react`      | ^0.562.0 | Icon library                  |
| `clsx`              | ^2.1.0   | Conditional class names       |
| `framer-motion`     | ^12.24.10| Animation library             |
| `sonner`            | ^2.0.7   | Toast notifications           |
| `vite-plugin-pwa`   | ^1.2.0   | PWA service worker            |
| `workbox-window`    | ^7.4.0   | Service worker client         |
| `web-vitals`        | ^5.1.0   | Performance metrics           |

### Development

| Package                         | Version | Purpose                        |
| ------------------------------- | ------- | ------------------------------ |
| `vite`                          | ^7.3.0  | Build tool and dev server      |
| `vitest`                        | ^4.0.16 | Testing framework              |
| `typescript`                    | ^5.3.3  | Type checking                  |
| `@vitejs/plugin-react`          | ^4.4.1  | Vite React plugin              |
| `tailwindcss`                   | ^3.4.1  | CSS framework                  |
| `eslint`                        | ^9.39.2 | Linting (flat config)          |
| `prettier`                      | ^3.2.4  | Code formatting                |
| `@playwright/test`              | ^1.57.0 | E2E testing (multi-browser)    |
| `msw`                           | ^2.12.7 | Mock Service Worker for tests  |
| `@testing-library/react`        | ^16.3.1 | React testing utilities        |
| `@testing-library/jest-dom`     | ^6.2.0  | DOM matchers                   |
| `@testing-library/user-event`   | ^14.5.2 | User interaction simulation    |
| `jsdom`                         | ^27.3.0 | Browser environment simulation |
| `@vitest/coverage-v8`           | ^4.0.16 | Code coverage                  |
| `@stryker-mutator/core`         | ^8.7.1  | Mutation testing core          |
| `@stryker-mutator/vitest-runner`| ^9.4.0  | Stryker Vitest integration     |
| `knip`                          | ^5.79.0 | Dead code detection            |
| `rollup-plugin-visualizer`      | ^6.0.5  | Bundle size analysis           |
| `@axe-core/playwright`          | ^4.11.0 | Accessibility testing          |

## Vite Configuration

The `vite.config.ts` configures:

- **Dev Server**: Port 5173 (strictPort: true) - for local development with `npm run dev`
- **API Proxy**: `/api/*` -> `http://localhost:8000`
- **WebSocket Proxy**: `/ws/*` -> `ws://localhost:8000`
- **Test Environment**: jsdom with globals
- **Coverage Thresholds**: 83% statements, 77% branches, 81% functions, 84% lines
- **Memory Optimization**: Uses forks pool with single fork

> **Production Note:** In production containers (`docker-compose.prod.yml`), nginx serves the built React app (not Vite). HTTP on host port 5173 (internal 8080), HTTPS on host port 8443 (internal 8443). SSL is enabled by default with auto-generated self-signed certificates.

## Source Map Strategy

The production build generates **hidden source maps** for debugging without exposing them publicly:

### Configuration

```typescript
// vite.config.ts
build: {
  sourcemap: 'hidden',  // Generates .map files without //# sourceMappingURL= comment
}
```

### How It Works

1. **Build Output**: Running `npm run build` generates `.map` files in the build output directory
2. **No URL Reference**: The bundles do NOT contain `//# sourceMappingURL=` comments
3. **Private Maps**: Source maps are not served by nginx (only `.js` and `.css` are public)
4. **Debug Access**: Developers can manually load `.map` files in DevTools or use error tracking services

### Using Source Maps for Debugging

**Option 1: Browser DevTools Manual Upload**
1. Open Chrome/Firefox DevTools > Sources panel
2. Right-click on a minified file > "Add source map..."
3. Provide the URL or local path to the `.map` file

**Option 2: Error Tracking Services**
Upload source maps to services like Sentry, Datadog, or Rollbar during CI/CD:
```bash
# Example: Upload to Sentry
sentry-cli releases files <release> upload-sourcemaps ./dist/assets/
```

**Option 3: Local Debugging**
Copy `.map` files to the server temporarily for debugging, then remove them.

### Error Boundary Integration

The `ErrorBoundary` component logs errors with full stack traces to the centralized logger:

```typescript
logger.error('React component error', {
  error: error.message,
  stack: error.stack,  // Full stack trace for source map lookup
  componentStack: errorInfo.componentStack,
  name: error.name,
});
```

Stack traces in production logs can be decoded using source maps via `source-map` CLI or browser tools.

### Security Considerations

- Source maps reveal original source code structure
- **Hidden** mode keeps maps private (not auto-loaded by browsers)
- Do NOT deploy `.map` files to public-facing servers
- Use error tracking service integrations instead of exposing maps publicly

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

## PWA Configuration

The application is a Progressive Web App (PWA) with offline support:

### Manifest (`public/manifest.json`)

| Property           | Value                                    |
| ------------------ | ---------------------------------------- |
| Name               | Nemotron Security Dashboard              |
| Short Name         | Nemotron                                 |
| Theme Color        | `#76B900` (NVIDIA Green)                 |
| Background Color   | `#1a1a2e`                                |
| Display            | standalone                               |
| Orientation        | any                                      |

### Icons

| Icon                   | Size    | Purpose           |
| ---------------------- | ------- | ----------------- |
| `icons/icon-192.png`   | 192x192 | Standard + Maskable |
| `icons/icon-512.png`   | 512x512 | Standard + Maskable |
| `icons/badge-72.png`   | 72x72   | Monochrome badge  |
| `favicon.svg`          | any     | Vector favicon    |

### App Shortcuts

- **View Events** (`/events`) - Quick access to security events
- **Settings** (`/settings`) - Dashboard configuration

### Service Worker (Workbox)

Configured in `vite.config.ts` via `vite-plugin-pwa`:

| Cache Strategy  | URL Pattern              | TTL       | Purpose               |
| --------------- | ------------------------ | --------- | --------------------- |
| CacheFirst      | Google Fonts             | 1 year    | Font caching          |
| NetworkFirst    | `/api/*`                 | 5 minutes | API with offline fallback |
| CacheFirst      | Images (png, jpg, svg)   | 30 days   | Asset caching         |

**Features:**
- Auto-update registration (`registerType: 'autoUpdate'`)
- Skip waiting and claim clients immediately
- Precaches app shell (JS, CSS, HTML, icons)
- PWA enabled in development for testing

## Stryker Mutation Testing

Mutation testing verifies test effectiveness by introducing code mutations:

### Configuration (`stryker.config.mjs`)

```bash
npm run test:mutation
```

### Target Modules

| Module                    | Purpose                           |
| ------------------------- | --------------------------------- |
| `src/utils/risk.ts`       | Risk score to level conversion    |
| `src/utils/time.ts`       | Time formatting utilities         |
| `src/utils/confidence.ts` | Confidence score utilities        |

### Thresholds

| Level | Score | Meaning                        |
| ----- | ----- | ------------------------------ |
| High  | 80%   | Excellent test coverage        |
| Low   | 60%   | Acceptable but needs improvement |
| Break | null  | No CI gate (informational)     |

### Output

- **Console**: Progress and clear-text summary
- **HTML Report**: `reports/mutation/mutation-report.html`

### Performance Settings

- **Concurrency**: 4 parallel mutants
- **Timeout**: 30 seconds per mutant
- **TypeScript checker**: Validates type correctness

## Knip Dead Code Detection

Knip finds unused code, exports, and dependencies:

```bash
npm run dead-code
```

### What It Detects

- Unused exports (functions, types, constants)
- Unused dependencies in `package.json`
- Unused files not referenced by any entry point
- Unused devDependencies
- Duplicate exports

### Integration with CI

Knip runs in CI to catch dead code before merge. Fix findings by:

1. Removing unused exports/files
2. Moving dev-only deps to `devDependencies`
3. Adding legitimate entry points to configuration

## Bundle Size Monitoring

Track and optimize production bundle sizes:

```bash
npm run analyze
```

### Target Sizes (NEM-1562)

| Metric              | Target    | Purpose                    |
| ------------------- | --------- | -------------------------- |
| Main bundle         | < 500KB   | Vendor + app (gzipped)     |
| Largest chunk       | < 250KB   | Single chunk limit         |
| Total initial load  | < 750KB   | First contentful paint     |

### Bundle Analysis

The visualizer generates `stats.html` with:

- **Treemap view**: Size proportional blocks
- **Gzip sizes**: Realistic transfer sizes
- **Brotli sizes**: Modern compression comparison

### Manual Chunk Splitting

Configured in `vite.config.ts`:

| Chunk          | Contents                                       |
| -------------- | ---------------------------------------------- |
| `vendor-react` | react, react-dom, react-router-dom             |
| `vendor-ui`    | @tremor/react, @headlessui/react, lucide-react |
| `vendor-utils` | clsx, tailwind-merge                           |

### Monitoring Workflow

1. Run `npm run analyze` after significant changes
2. Review `stats.html` for bundle growth
3. Add manual chunks for new large dependencies
4. Keep chunk sizes under warning limit (500KB)

## Playwright E2E Testing

Configuration in `playwright.config.ts`:

- **Test directory**: `./tests/e2e`
- **Base URL**: `http://localhost:5173`
- **Auto-starts dev server**: Uses `npm run dev:e2e` before tests
- **Artifacts**: Screenshots, videos, and traces on failure
- **Global setup**: Disables product tour via `tests/e2e/global-setup.ts`

### Multi-Browser Configuration

The project runs E2E tests across multiple browsers:

| Project          | Browser          | Purpose                              |
| ---------------- | ---------------- | ------------------------------------ |
| `chromium`       | Desktop Chrome   | Primary browser, 4 CI shards         |
| `firefox`        | Desktop Firefox  | Cross-browser compatibility          |
| `webkit`         | Desktop Safari   | macOS/iOS compatibility              |
| `mobile-chrome`  | Pixel 5          | Mobile Android viewport              |
| `mobile-safari`  | iPhone 12        | Mobile iOS viewport                  |
| `tablet`         | iPad (gen 7)     | Tablet viewport                      |
| `visual-chromium`| Desktop Chrome   | Visual regression tests              |
| `smoke`          | Desktop Chrome   | Tests tagged with `@smoke`           |
| `critical`       | Desktop Chrome   | Tests tagged with `@critical`        |

### Test Tagging

Tests can be tagged in titles for selective execution:

- `@smoke` - Critical path tests (run on every commit)
- `@critical` - High-priority core functionality
- `@slow` - Long-running tests
- `@flaky` - Known flaky tests (tracked for stability)
- `@network` - Network simulation tests

```bash
# Run by tag
npm run test:e2e -- --grep @smoke
npm run test:e2e -- --grep @critical
npm run test:e2e -- --grep-invert @slow

# Run specific browser
npm run test:e2e -- --project=chromium
npm run test:e2e -- --project=firefox
npm run test:e2e -- --project=webkit
```

### CI Sharding

In CI, Chromium tests are sharded across 4 parallel jobs:

```bash
npx playwright test --project=chromium --shard=1/4
npx playwright test --project=chromium --shard=2/4
npx playwright test --project=chromium --shard=3/4
npx playwright test --project=chromium --shard=4/4
```

### Browser-Specific Timeouts

| Browser  | Action Timeout | Navigation Timeout | Test Timeout |
| -------- | -------------- | ------------------ | ------------ |
| Chromium | 5s             | 10s                | 15s          |
| Firefox  | 8s             | 20s                | 30s          |
| WebKit   | 8s             | 10s                | 30s          |

### Retry Configuration

- **CI**: 2 retries with complete browser isolation
- **Local**: No retries for faster feedback
- **Flaky detection**: JSON reporter enables post-run analysis

## API Types

TypeScript types are **auto-generated from backend OpenAPI specification**:

- Source: Backend Pydantic schemas via OpenAPI
- Generated files: `src/types/generated/api.ts`, `src/types/generated/index.ts`
- Regenerate: `npm run generate-types`
- Check freshness: `npm run generate-types:check`

Import types from `src/services/api.ts` which re-exports all generated types.

## Docker Configuration

### Production Docker Build

The `Dockerfile` uses a multi-stage build:

- **Stage 1 (build)**: Node 22.16.0-alpine for building the React app
- **Stage 2 (production)**: nginx:1.28.1-alpine3.23 for serving
- Uses `docker-entrypoint.sh` for runtime environment variable injection
- Includes health check endpoint
- Gzip compression and security headers
- Runs as non-root user (nginx) for security

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
| `/alerts`   | `AlertsPage`           | Alert management (modular architecture)  |
| `/entities` | `EntitiesPage`         | Entity tracking                          |
| `/logs`     | `LogsDashboard`        | Application logs viewer                  |
| `/audit`    | `AuditLogPage`         | Audit log viewer                         |
| `/operations` | `SystemMonitoringPage` | Operations and pipeline controls        |
| `/settings` | `SettingsPage`         | Application settings                     |

## Entry Points for Understanding the Code

1. **Start here**: Read this file for configuration overview
2. **Source code**: Navigate to `src/AGENTS.md` for component structure
3. **Configuration**: Check `vite.config.ts`, `tsconfig.json`, `eslint.config.mjs`
4. **Styling**: Examine `tailwind.config.js` for NVIDIA theme
5. **Testing**: Review `TESTING.md` for test patterns
6. **PWA**: Check `public/manifest.json` and Workbox config in `vite.config.ts`

## Notes for AI Agents

- **Testing is mandatory**: All features need tests with coverage thresholds enforced
- **Pre-commit hooks**: Code must pass ESLint (0 warnings), TypeScript, and Prettier
- **NVIDIA branding**: Use NVIDIA green (`#76B900`) for primary actions
- **Dark theme**: All UI uses dark backgrounds
- **Component co-location**: Test files live alongside source files (`*.test.tsx`)
- **Type safety**: Use generated types from backend OpenAPI spec
- **No inline styles**: Use Tailwind utilities or custom CSS classes
- **Accessibility**: jsx-a11y rules are enforced
- **PWA support**: App works offline with Workbox service worker caching
- **Multi-browser E2E**: Tests run on Chromium, Firefox, and WebKit in CI
- **Dead code detection**: Run `npm run dead-code` before PRs to catch unused exports
- **Bundle monitoring**: Run `npm run analyze` after adding large dependencies
- **Mutation testing**: Run `npm run test:mutation` to verify test effectiveness
