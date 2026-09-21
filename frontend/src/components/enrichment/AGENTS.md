# Enrichment Components

## Purpose

Displays AI enrichment data (vehicle, person, pet, scene, telemetry) attached to detections and events. One component with three visual variants.

## Key Files

| File                              | Purpose                                                        |
| --------------------------------- | -------------------------------------------------------------- |
| `index.ts`                        | Barrel: exports `EnrichmentViewer`, `EnrichmentViewerProps`    |
| `EnrichmentViewer.tsx`            | Multi-variant viewer: `full` (accordion), `compact` (badges), `modal` (all expanded) |
| `__tests__/EnrichmentViewer.test.tsx` | Variant rendering, empty-section hiding, security-alert auto-expand |

## Related Files

| File                                       | Purpose                                             |
| ------------------------------------------ | --------------------------------------------------- |
| `frontend/src/types/enrichment.ts`         | `EnrichmentData` model + `hasAnyEnrichment()` helper |
| `frontend/src/utils/confidence.ts`         | `formatConfidencePercent()` for score labels         |
| `frontend/src/components/events/EventDetailModal.tsx` | Main consumer (event detail enrichment tab) |

## Patterns

- **Empty-data hiding:** sections with no data are dropped, so callers can pass partial `EnrichmentData` without blank panels.
- **Security alert highlighting:** an enrichment section flagged as a security alert auto-expands.
- **Controlled and uncontrolled expansion:** pass expansion state or let the component own it.
