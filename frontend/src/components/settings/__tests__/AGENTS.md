# Settings Tests

## Purpose

Focused tests for settings panels that need isolation from the rest of the settings page — camera motion-sensitivity behavior and the feature-toggle panel. Most settings components keep `*.test.tsx` next to the component in `../`; these two are the exceptions.

## Test Files

| File                                      | Component Under Test       | Key Coverage                                                        |
| ----------------------------------------- | -------------------------- | ------------------------------------------------------------------- |
| `CamerasSettings.motionSensitivity.test.tsx` | `../CamerasSettings.tsx` | Motion-sensitivity slider: RTSP-only, 0-1 range step 0.01, default 0.5, `motion_sensitivity` in API payload |
| `FeatureTogglesPanel.test.tsx`            | `../FeatureTogglesPanel.tsx` | Toggle rendering, `useSettingsApi` save/invalidate behavior          |

## Test Patterns

- **Mock the barrel, not the leaf hook** (camera test): `vi.mock('../../../hooks', () => ({ useCamerasQuery: vi.fn(), useCameraMutation: vi.fn() }))` — matches how `CamerasSettings` imports.
- **Mock the concrete hook** (toggles test): `vi.mock('../../../hooks/useSettingsApi')` and cast with `as Mock`.
- **Bare `render`** from Testing Library; no provider wrapper needed because the query hooks are mocked.

## Related Files

| File                                | Purpose                                 |
| ----------------------------------- | --------------------------------------- |
| `frontend/src/components/settings/AGENTS.md` | Component directory overview |
| `frontend/src/hooks/index.ts`       | Barrel mocked by the camera test        |
| `frontend/src/hooks/useSettingsApi.ts` | Settings API hook mocked by the toggles test |
