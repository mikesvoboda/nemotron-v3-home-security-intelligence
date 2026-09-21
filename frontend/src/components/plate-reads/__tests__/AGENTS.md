# Plate Reads Tests

## Purpose

Tests for the license-plate-recognition components whose test files live here instead of next to the component. The sibling `PlateReadsPage.test.tsx`, `PlateDetailModal.test.tsx`, `PlateStatisticsCards.test.tsx`, `PlateReadTrendsCard.test.tsx` and `VehicleMatchBadge.test.tsx` in `../` cover the rest — check both places before adding a test.

## Test Files

| File                      | Component Under Test        | Key Coverage                                                    |
| ------------------------- | --------------------------- | --------------------------------------------------------------- |
| `PlateSearchBar.test.tsx` | `../PlateSearchBar.tsx`     | Text input, exact-match toggle, advanced filter panel, camera list |
| `PlateReadTable.test.tsx` | `../PlateReadTable.tsx`     | Paginated rows, pagination controls, row click, empty state, vehicle-match badges |
| `PlateExportButton.test.tsx` | `../PlateExportButton.tsx` | Export menu, progress tracking, error states                     |

## Test Patterns

- **Two render helpers:** `renderWithProviders` from `../../../test-utils/renderWithProviders` (table — needs React Query), bare `render` from Testing Library (export button — hooks mocked).
- **MSW for HTTP:** `server.use(http.get(\`${BASE_URL}/api/household/vehicles\`, …))` etc.; `BASE_URL` comes from `import.meta.env.VITE_API_BASE_URL` and must prefix every handler URL.
- **`vi.mock` for the rest:** `../../../services/plateReadsApi`, `../../../services/logger`, and `../../../hooks/useCamerasQuery` are mocked outright in the button/search-bar tests.

## Related Files

| File                                | Purpose                                    |
| ----------------------------------- | ------------------------------------------ |
| `frontend/src/components/plate-reads/AGENTS.md` | Component directory overview    |
| `frontend/src/services/plateReadsApi.ts` | API client exercised by these tests |
| `frontend/src/types/plateRead.ts`   | `PlateRead`, `PlateReadFilters` fixtures   |
