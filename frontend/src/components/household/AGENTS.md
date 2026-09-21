# Household Components

## Purpose

Household-member access-control UI: weekly schedule editing, schedule-violation indicators, and the detections linked to a specific member.

## Key Files

| File                                          | Purpose                                             |
| --------------------------------------------- | --------------------------------------------------- |
| `ScheduleGrid.tsx`                            | 7x24 click/drag grid editor for a member's weekly schedule |
| `AccessViolationBadge.tsx`                    | Badge shown when a detection falls outside allowed hours |
| `MemberDetectionHistory.tsx`                  | Paginated detection list for a member, with filter/sort/unlink |
| `ScheduleGrid.test.tsx`                       | Cell toggle, drag-select, schedule serialization     |
| `AccessViolationBadge.test.tsx`               | Violation vs compliant rendering                     |
| `MemberDetectionHistory.test.tsx`             | Unit tests (mocked hooks)                            |
| `MemberDetectionHistory.integration.test.tsx` | MSW-driven link/unlink flow                          |

## Related Files

| File                              | Purpose                                                                  |
| --------------------------------- | ------------------------------------------------------------------------ |
| `frontend/src/hooks/useHouseholdApi.ts` | `WeeklySchedule`, `DayOfWeek`, `useMemberDetectionsQuery`, `useUnlinkDetection` — all types and hooks live here, not in this directory |
| `frontend/src/components/settings/HouseholdSettings.tsx` | Household configuration page |

## Gotchas

- **No `index.ts` barrel** — import components by full path (`../household/ScheduleGrid`), unlike most sibling directories.
- **Not wired into a page yet.** Nothing outside this directory imports these three components; they are exercised only by their own tests. Check for a consumer before assuming a change here is user-visible.
- Types come from the hook module, not from `frontend/src/types/`.
