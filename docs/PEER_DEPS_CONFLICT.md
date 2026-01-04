# Peer Dependency Conflict: React 19 + Tremor

This document explains the peer dependency conflict in the frontend that requires
`--legacy-peer-deps` and outlines the plan to resolve it.

## Current State

**Project versions (as of January 2026):**

| Package       | Installed Version | Required by Tremor |
| ------------- | ----------------- | ------------------ |
| React         | ^19.2.3           | ^18.0.0            |
| React DOM     | ^19.2.3           | >=16.6.0           |
| @tremor/react | ^3.17.4           | n/a                |

## The Problem

Tremor v3.x (`@tremor/react@3.17.4` through `@tremor/react@3.18.7`) declares a peer
dependency on `react@^18.0.0`, which conflicts with our use of React 19.

When running `npm install` without flags, npm 7+ strictly enforces peer dependencies
and fails with:

```
npm ERR! Could not resolve dependency:
npm ERR! peer react@"^18.0.0" from @tremor/react@3.17.4
npm ERR! node_modules/@tremor/react
npm ERR!   @tremor/react@"^3.17.4" from the root project
```

## Current Workaround

We use `--legacy-peer-deps` to bypass this check:

**Files affected:**

| File                       | Configuration                    |
| -------------------------- | -------------------------------- |
| `frontend/.npmrc`          | `legacy-peer-deps=true`          |
| `frontend/Dockerfile`      | `npm install --legacy-peer-deps` |
| `frontend/Dockerfile.prod` | `npm ci --legacy-peer-deps`      |

This flag tells npm to use npm v6 behavior, which ignores peer dependency conflicts
and installs packages anyway. The application works correctly because:

1. Tremor's internal dependencies (recharts, @headlessui/react) already support React 19
2. React 19's API is backwards-compatible with React 18 patterns

## Why Tremor Works Despite the Conflict

Despite the declared peer dependency mismatch, Tremor functions correctly because:

1. **Recharts** (charting library used by Tremor) already supports React 19:

   ```
   react: '^16.8.0 || ^17.0.0 || ^18.0.0 || ^19.0.0'
   ```

2. **@headlessui/react** (UI primitives used by Tremor) supports React 19:

   ```
   react: '^18 || ^19 || ^19.0.0-rc'
   ```

3. The Tremor components themselves use standard React patterns that work in React 19.

## Resolution Plan

### Option 1: Wait for Tremor v4 Stable (Recommended)

Tremor v4 beta already supports React 19:

```
@tremor/react@4.0.0-beta-tremor-v4.4:
  peerDependencies: { react: '^19.0.0', 'react-dom': '>=16.6.0' }
```

**Timeline:** Tremor v4 betas have been released since December 2024. A stable release
is expected in early 2026.

**Action items:**

1. Monitor [tremorlabs/tremor-npm releases](https://github.com/tremorlabs/tremor-npm/releases)
2. When v4 stable releases, test upgrade in a branch
3. Update package.json and remove `--legacy-peer-deps` workarounds
4. Run full test suite to verify no regressions

**Tracking issues:**

- [Feature: React 19 support (tremorlabs/tremor-npm#1072)](https://github.com/tremorlabs/tremor-npm/issues/1072)
- [Bug: Charts don't render in React 19 RC (tremorlabs/tremor-npm#1054)](https://github.com/tremorlabs/tremor-npm/issues/1054)

### Option 2: Upgrade to Tremor v4 Beta Now

If React 19 compatibility is urgently needed without workarounds:

```bash
npm install @tremor/react@4.0.0-beta-tremor-v4.4
```

**Risks:**

- Beta software may have breaking changes before stable release
- API changes may require component updates
- Less community support for beta issues

**Not recommended** unless the current workaround causes issues.

### Option 3: Downgrade to React 18

If Tremor compatibility is critical and v4 is delayed:

```bash
npm install react@18 react-dom@18 @types/react@18 @types/react-dom@18
```

**Not recommended** because:

- React 19 offers performance improvements and new features
- Other dependencies already support React 19
- The current workaround functions correctly

## Cleanup Checklist (When Tremor v4 Releases)

When upgrading to Tremor v4 stable:

- [ ] Update `package.json`: `"@tremor/react": "^4.x.x"`
- [ ] Remove `frontend/.npmrc` (or set `legacy-peer-deps=false`)
- [ ] Update `frontend/Dockerfile`: remove `--legacy-peer-deps` flag
- [ ] Update `frontend/Dockerfile.prod`: remove `--legacy-peer-deps` flag
- [ ] Run `npm install` without flags to verify clean install
- [ ] Run full test suite: `npm test && npx playwright test`
- [ ] Update this document to reflect resolved state
- [ ] Create Linear issue to track removal of workaround

## Related Documentation

- [npm legacy-peer-deps documentation](https://docs.npmjs.com/cli/v8/using-npm/config#legacy-peer-deps)
- [React 19 upgrade guide](https://react.dev/blog/2024/04/25/react-19-upgrade-guide)
- [Tremor GitHub repository](https://github.com/tremorlabs/tremor-npm)

## Version History

| Date       | Change                                   |
| ---------- | ---------------------------------------- |
| 2026-01-03 | Initial documentation created (NEM-1116) |
