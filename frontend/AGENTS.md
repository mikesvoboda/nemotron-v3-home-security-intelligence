# Frontend Directory - AI Agent Guide

## Purpose

This is the root directory of the React frontend application for the Home Security Intelligence Dashboard. It contains all configuration files, build tooling, dependencies, and the source code for the web-based UI that displays security camera feeds, AI detections, and risk assessments.

## Key Configuration Files

### Build & Development

- **`package.json`** - Project manifest defining dependencies and npm scripts

  - Name: `home-security-dashboard`
  - Type: ES Module (`"type": "module"`)
  - Main dependencies: React 18.2, Tremor React (data viz), Tailwind CSS
  - Dev dependencies: Vite, Vitest, TypeScript, ESLint, Prettier

- **`vite.config.ts`** - Vite bundler configuration

  - Dev server runs on port 5173 (strictPort: true)
  - Proxies `/api` requests to backend at `http://localhost:8000`
  - Proxies WebSocket `/ws` connections to backend
  - Test configuration with jsdom environment
  - Coverage thresholds: 95% for statements, 94% branches, 95% functions/lines
  - Test setup file: `./src/test/setup.ts`
  - Coverage excludes: test files, config files, main.tsx, type definitions

- **`tsconfig.json`** - TypeScript compiler configuration
  - Target: ES2020
  - Strict mode enabled with all checks
  - Module resolution: bundler
  - JSX: react-jsx (new JSX transform)
  - Types: vite/client, @testing-library/jest-dom

### Styling

- **`tailwind.config.js`** - Tailwind CSS configuration with NVIDIA theme

  - Dark backgrounds: `#0E0E0E` (background), `#1A1A1A` (panel), `#1E1E1E` (card)
  - Primary brand color: NVIDIA Green `#76B900`
  - Risk level colors: low (green), medium (yellow), high (red)
  - Custom animations: pulse-glow, slide-in, fade-in
  - Custom utilities: glass morphism, NVIDIA glow effects

- **`postcss.config.js`** - PostCSS configuration for Tailwind processing

- **`.prettierrc`** - Prettier code formatting configuration
  - Single quotes, 2-space tabs, 100 character line width
  - Tailwind plugin for class sorting
  - ES5 trailing commas, LF line endings
  - Custom functions: clsx, cn, twMerge

### Code Quality

- **`.eslintrc.cjs`** - ESLint configuration

  - TypeScript + React + Hooks + Accessibility (jsx-a11y)
  - Enforces import ordering with alphabetical sorting
  - Requires type-checked rules from @typescript-eslint
  - Warns on console.log, errors on console usage (allows warn/error)
  - Test files have relaxed rules for `any` types
  - Uses Node resolver for imports (avoids TypeScript resolver issues)

- **`.prettierignore`** - Files excluded from Prettier formatting

### Docker & Deployment

- **`Dockerfile`** - Development container configuration

  - Base image: node:20-alpine
  - Installs wget for healthcheck
  - Installs dependencies with npm install
  - Exposes port 3000
  - Runs dev server with `--host` flag for container networking

- **`Dockerfile.prod`** - Production multi-stage build

  - Stage 1: Build with node:20-alpine
  - Stage 2: Serve with nginx:alpine
  - Uses `npm ci --only=production` for clean install
  - Copies built assets from dist/ to nginx html directory
  - Exposes port 80 with health check endpoint
  - Includes gzip compression and security headers

- **`nginx.conf`** - Nginx configuration for production serving

  - SPA routing with fallback to index.html
  - Static asset caching (1 year)
  - Gzip compression for text resources
  - Security headers (X-Frame-Options, X-Content-Type-Options, X-XSS-Protection)
  - Health check endpoint at `/health`

- **`.dockerignore`** - Files excluded from Docker builds

### HTML Entry Point

- **`index.html`** - Application entry point
  - Title: "Home Security Intelligence Dashboard"
  - Body background: `#0E0E0E` (dark theme via Tailwind class)
  - Loads `/src/main.tsx` as module script
  - Favicon: `/vite.svg` (default Vite icon, should be replaced)

### Documentation

- **`TESTING.md`** - Comprehensive testing documentation

  - Testing stack overview (Vitest, RTL, jsdom)
  - Test file locations and coverage details
  - Best practices and examples
  - Configuration and troubleshooting

- **`TEST_QUICKSTART.md`** - Quick reference for running tests

## NPM Scripts

```bash
npm run dev          # Start Vite dev server (port 3000)
npm run build        # TypeScript check + production build
npm run lint         # Run ESLint (max 0 warnings)
npm run lint:fix     # Auto-fix ESLint issues
npm run format       # Format code with Prettier
npm run format:check # Check formatting without changes
npm run typecheck    # Run TypeScript compiler (no emit)
npm run preview      # Preview production build
npm test             # Run Vitest tests in watch mode
npm run test:ui      # Open Vitest UI
npm run test:coverage # Run tests with coverage report
npm run validate     # Full validation: typecheck + lint + test with coverage
```

## Directory Structure

- **`src/`** - All application source code (see `src/AGENTS.md`)
  - `components/` - React components organized by feature
  - `hooks/` - Custom React hooks
  - `services/` - API client and external service wrappers
  - `styles/` - Global CSS and Tailwind imports
  - `test/` - Test setup and configuration
  - `utils/` - Utility functions and helpers
- **`public/`** - Static assets served at root (see `public/AGENTS.md`)
- **`tests/`** - Test organization directory (see `tests/AGENTS.md`)
  - `e2e/` - End-to-end tests with Playwright (planned)
  - `integration/` - Integration tests (planned)
  - `fixtures/` - Test data and mocks (planned)
- **`data/`** - Local data directory for development
  - `thumbnails/` - Camera snapshot thumbnails
- **`node_modules/`** - Installed npm dependencies (do not edit, git-ignored)
- **`dist/`** - Production build output (generated by Vite, git-ignored)
- **`coverage/`** - Test coverage reports (generated by Vitest, git-ignored)

## Testing Infrastructure

- **Test Runner**: Vitest (Vite-native test runner)
- **Testing Library**: React Testing Library for component tests
- **Environment**: jsdom (simulates browser DOM)
- **Setup File**: `src/test/setup.ts` (configures jest-dom matchers)
- **Coverage Provider**: v8
- **Coverage Reports**: text, json, html formats

See `TESTING.md` for detailed testing documentation.

## Key Dependencies

### Production

- **react** (18.2) - UI library
- **react-dom** (18.2) - React DOM renderer
- **@tremor/react** (3.17.4) - Data visualization components
- **@headlessui/react** (1.7.18) - Unstyled accessible UI components
- **lucide-react** (0.312) - Icon library
- **clsx** + **tailwind-merge** - Utility for merging Tailwind classes

### Development

- **vite** (5.0.11) - Build tool and dev server
- **vitest** (1.2.0) - Testing framework
- **typescript** (5.3.3) - Type checking
- **@vitejs/plugin-react** (4.2.1) - Vite React plugin
- **tailwindcss** (3.4.1) - CSS framework
- **eslint** (8.56.0) - Linting
- **prettier** (3.2.4) - Code formatting
- **@testing-library/react** (14.1.2) - React testing utilities
- **@testing-library/jest-dom** (6.2.0) - DOM matchers
- **@testing-library/user-event** (14.5.2) - User interaction simulation
- **jsdom** (23.2.0) - Browser environment simulation

## Development Workflow

1. **Install dependencies**: `npm install`
2. **Start dev server**: `npm run dev` (opens on http://localhost:5173)
3. **Make changes**: Edit files in `src/`
4. **Run tests**: `npm test` (watch mode)
5. **Check types**: `npm run typecheck`
6. **Lint code**: `npm run lint`
7. **Format code**: `npm run format`
8. **Full validation**: `npm run validate` (runs typecheck + lint + test:coverage)

## Proxy Configuration

The Vite dev server proxies API and WebSocket requests to the backend:

- **HTTP API**: `http://localhost:5173/api/*` → `http://localhost:8000/api/*`
- **WebSocket**: `ws://localhost:5173/ws/*` → `ws://localhost:8000/ws/*`

This allows frontend code to use relative URLs like `/api/cameras` without CORS issues during development.

## Build Output

Production build creates optimized static files in `dist/`:

- Minified JavaScript bundles with code splitting
- Processed CSS with Tailwind utilities
- Copied static assets from `public/`
- Source maps for debugging

## Integration with Backend

- Backend API runs on port 8000 (FastAPI + Python)
- Frontend consumes REST endpoints at `/api/*`
- Real-time updates via WebSocket at `/ws/*`
- Media files served from `/api/media/*`

## Entry Points for Understanding the Code

1. **Start here**: Read this file (you're here now!)
2. **Configuration**: Check `vite.config.ts`, `tsconfig.json`, `.eslintrc.cjs`
3. **Source code**: Navigate to `src/AGENTS.md` for component structure
4. **Testing**: Review `TESTING.md` for test coverage and patterns
5. **Styling**: Examine `tailwind.config.js` for NVIDIA theme customization

## Notes for AI Agents

- **File structure is locked**: Do not add new top-level files without understanding the existing structure
- **Testing is mandatory**: All features must have tests with 95% coverage thresholds
- **Pre-commit hooks**: Code must pass ESLint (max 0 warnings), TypeScript, and tests before committing
- **NVIDIA branding**: Use NVIDIA green (`#76B900`) for primary actions and highlights
- **Dark theme**: All UI uses dark backgrounds (`#0E0E0E`, `#1A1A1A`, `#1E1E1E`)
- **Component organization**: See `src/AGENTS.md` for detailed component directory structure
- **Unit tests co-located**: Test files live alongside source files (`*.test.tsx`)
- **Integration/E2E tests**: Planned in `tests/` directory (currently placeholder)
- **Port configuration**: Dev server on 5173, backend on 8000, prod nginx on 80
- **Docker**: Use `Dockerfile` for dev, `Dockerfile.prod` for production builds
