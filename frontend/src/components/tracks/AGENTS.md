# Track Visualization Components

## Purpose

Object-tracking UI: active-track counts on camera cards, trajectory rendering on snapshots, and movement history inside entity modals. Tracks are the trajectories of detected objects (people, vehicles) across frames (NEM-4766).

## Key Files

| File                         | Purpose                                                              |
| ---------------------------- | -------------------------------------------------------------------- |
| `index.ts`                   | Barrel: components + `ActiveTracksBadgeProps`, `TrackHistorySectionProps`, `TrackPathVisualizationProps`, `TrajectoryPoint` |
| `ActiveTracksBadge.tsx`      | Pulsing badge with the count of active tracks on a camera            |
| `TrackPathVisualization.tsx` | Pure SVG overlay — polyline trajectory, age-faded dots, green start / red end markers |
| `TrackHistorySection.tsx`    | Section for entity detail modals; fetches via `useTrackHistory` and embeds the visualization |

## Related Files

| File                        | Purpose                                        |
| --------------------------- | ---------------------------------------------- |
| `frontend/src/hooks/useTracks.ts` | Track queries incl. `useTrackHistory` (used by `TrackHistorySection`) |
| `frontend/src/pages/TracksPage.tsx` | Track browser page (consumes the hook, not these components) |

## Gotchas

- **No co-located tests** in this directory — behavior is covered via the hooks and page tests.
- **Not yet imported by any page/modal.** All three components are currently only referenced from `index.ts`; check for a consumer before assuming a change is user-visible.
- `TrackPathVisualization` takes raw `trajectory` points (`{x, y, timestamp}`), not a track id — fetching is the caller's job (`TrackHistorySection` does it).
