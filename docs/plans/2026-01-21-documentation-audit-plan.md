# Documentation Audit Plan

**Date:** 2026-01-21
**Status:** Planning

## Executive Summary

This document outlines the findings from a comprehensive audit of the project documentation, identifies gaps and outdated content, and provides a prioritized plan for improvements.

## Audit Scope

### Documents Reviewed
- Main README.md
- docs/README.md (documentation hub)
- All docs/ui/*.md files (19 files)
- docs/images/SCREENSHOT_GUIDE.md
- Recent git history and closed Linear tasks
- Frontend component inventory (267 components across 26 directories)

### Key Metrics
| Metric | Count |
|--------|-------|
| Total documentation files | 150+ |
| UI page docs | 19 |
| Existing screenshots | 13 |
| Required screenshots | 42 |
| Frontend components | 267 |
| Component-level docs | 0 |

---

## Critical Findings

### 1. New Pages Missing Documentation

The following pages were added recently but lack corresponding docs/ui documentation:

| Page | Feature | Linear Issue | Status |
|------|---------|--------------|--------|
| **Pyroscope** | Continuous profiling viewer | NEM-3157 | No docs/ui/pyroscope.md |
| **Tracing** | Distributed tracing (Jaeger/Grafana) | NEM-3069 | No docs/ui/tracing.md |

### 2. Potentially Outdated Documentation

These pages underwent significant changes that may not be reflected in documentation:

| Page | Change | Linear Issue | Risk |
|------|--------|--------------|------|
| **Logs** | Replaced with Grafana/Loki embed | NEM-3090 | High - docs may describe old implementation |
| **Analytics** | Replaced with Grafana iframe | NEM-2943 | Medium - architecture changed significantly |
| **Operations** | Refactored from System page | NEM-2773 | Medium - page name and features changed |

### 3. Screenshot Coverage Gap

**Current state:**
- SCREENSHOT_GUIDE.md specifies 42 screenshots needed
- Only 13 screenshots exist in docs/images/screenshots/

**Existing screenshots:**
- ai-performance.png
- alerts.png
- analytics.png
- audit-log.png
- dashboard.png
- entities.png
- jobs.png
- logs.png
- operations.png
- settings.png
- system.png
- timeline.png
- trash.png

**Missing high-priority screenshots (from SCREENSHOT_GUIDE.md):**
- Header health indicator
- Quick stats row
- Risk gauge states (composite)
- Camera grid
- Activity feed
- Event detail modal
- Timeline filters expanded
- Detection image with bounding boxes
- Alert cards comparison
- Settings AI models tab
- Search interface
- Log detail modal

### 4. Component-Level Documentation Gap

**Finding:** 267 frontend components exist but no component library documentation.

**Impact:** Developers and contributors lack guidance on:
- Component usage patterns
- Props and configuration
- Visual examples
- Integration patterns

**Recommendation:** Create docs/components/ directory with categorized component documentation.

---

## Prioritized Action Plan

### Tier 1: Critical (Blocking User Understanding)

| Task | Priority | Effort | Description |
|------|----------|--------|-------------|
| Create docs/ui/pyroscope.md | P1 | Medium | New page needs user documentation |
| Create docs/ui/tracing.md | P1 | Medium | New page needs user documentation |
| Audit and update docs/ui/logs.md | P1 | Low | Verify Grafana/Loki integration is documented |
| Audit and update docs/ui/analytics.md | P1 | Low | Verify Grafana embed is documented |

### Tier 2: Important (Improves User Experience)

| Task | Priority | Effort | Description |
|------|----------|--------|-------------|
| Capture missing page screenshots | P2 | Medium | Update all 14 page screenshots to current UI |
| Add screenshots to pyroscope.md | P2 | Low | Include screenshots for new page |
| Add screenshots to tracing.md | P2 | Low | Include screenshots for new page |
| Update docs/ui/README.md navigation | P2 | Low | Add Pyroscope and Tracing entries |

### Tier 3: Enhancement (Comprehensive Documentation)

| Task | Priority | Effort | Description |
|------|----------|--------|-------------|
| Capture component-specific screenshots | P3 | High | 29 additional screenshots per SCREENSHOT_GUIDE |
| Create docs/components/README.md | P3 | Medium | Component documentation hub |
| Document common components | P3 | High | Button, Modal, Toast, Error Boundaries |
| Document layout components | P3 | Medium | Header, Sidebar, Layout |
| Document feature components | P3 | High | Dashboard, Timeline, Entities widgets |

---

## Documentation Quality Checklist

Each UI doc should meet these criteria:

- [ ] Hero image at top
- [ ] Current screenshot of page
- [ ] "What You're Looking At" overview
- [ ] Key Components section with descriptions
- [ ] Settings & Configuration section
- [ ] Troubleshooting section
- [ ] Technical Deep Dive section (for developers)
- [ ] Related Code references
- [ ] Mermaid diagrams where applicable

### Current Status by Page

| Page Doc | Hero | Screenshot | Overview | Components | Settings | Troubleshooting | Deep Dive | Related Code | Mermaid |
|----------|------|------------|----------|------------|----------|-----------------|-----------|--------------|---------|
| dashboard.md | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| timeline.md | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| entities.md | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| alerts.md | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| analytics.md | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| operations.md | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| settings.md | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| jobs.md | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| logs.md | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| audit-log.md | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| ai-audit.md | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| ai-performance.md | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| zones.md | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| trash.md | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| pyroscope.md | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| tracing.md | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

### Audit Summary

**Documents with Full Coverage (all criteria met):**
- dashboard.md
- timeline.md
- alerts.md
- operations.md

**Documents Missing Only Hero Images:**
- entities.md (also missing Mermaid diagrams)
- analytics.md (also missing Mermaid diagrams)
- settings.md (also missing Mermaid diagrams)
- jobs.md (also missing Mermaid diagrams)
- logs.md (also missing Mermaid diagrams)
- audit-log.md (also missing Mermaid diagrams)
- ai-audit.md (also missing Mermaid diagrams)
- ai-performance.md (also missing Mermaid diagrams)
- zones.md (also missing Mermaid diagrams)
- trash.md (also missing Mermaid diagrams)
- pyroscope.md (has Mermaid diagram)
- tracing.md (has Mermaid diagram)

### Priority Recommendations

**Tier 1 - High Priority (Missing Hero Images):**
All 12 docs below are complete except for AI-generated hero images:
1. entities.md - Needs hero image
2. analytics.md - Needs hero image
3. settings.md - Has hero image already!
4. jobs.md - Needs hero image
5. logs.md - Needs hero image
6. audit-log.md - Needs hero image
7. ai-audit.md - Needs hero image
8. ai-performance.md - Needs hero image
9. zones.md - Needs hero image
10. trash.md - Needs hero image
11. pyroscope.md - Needs hero image
12. tracing.md - Needs hero image

**Tier 2 - Medium Priority (Missing Mermaid Diagrams):**
These docs would benefit from Mermaid diagrams to visualize workflows:
1. entities.md - Could use entity re-ID flow diagram
2. analytics.md - Could use data aggregation flow diagram
3. jobs.md - Could use job lifecycle state diagram
4. logs.md - Could use log flow diagram
5. audit-log.md - Could use audit event flow diagram
6. ai-audit.md - Could use self-evaluation flow diagram
7. ai-performance.md - Already has data flow (text-based, could be Mermaid)
8. zones.md - Could use zone detection flow diagram
9. trash.md - Could use soft-delete lifecycle diagram

**Key Findings:**
- pyroscope.md and tracing.md (newly created) are well-documented with screenshots, overviews, components, settings, troubleshooting, technical deep dives, related code, AND Mermaid diagrams
- The main gap across docs is AI-generated hero images (aesthetic, not functional)
- All 16 UI page docs have current screenshots
- All 16 UI page docs have comprehensive content sections

---

## Product Evolution Context

### Recent Major Features (Jan 2026)

Based on closed Linear tasks, these features were added recently:

1. **Distributed Tracing Page** (NEM-3069)
   - Jaeger integration with Grafana
   - New TracingPage component
   - Service correlation visualization

2. **Pyroscope Profiling Page** (NEM-3157)
   - Continuous profiling viewer
   - CPU/memory flame graphs
   - Service-level profiling

3. **Observability Stack** (NEM-3090)
   - Loki for log aggregation
   - Pyroscope for profiling
   - Alloy for collection
   - Full correlation between logs, traces, and profiles

4. **Logs Page Migration** (NEM-3090 related)
   - Replaced custom logs viewer with Grafana/Loki embed
   - New query capabilities
   - Integrated with distributed tracing

5. **System Page Refactor** (NEM-2773)
   - Renamed to Operations
   - Streamlined interface
   - Grafana integration banner

6. **UI Improvements**
   - Dashboard summaries (NEM-2922)
   - Timeline improvements (NEM-2931)
   - Entities improvements (NEM-2945)
   - Alerts improvements (NEM-2950)
   - Mobile experience (NEM-2989, NEM-2990, NEM-2991)

---

## Screenshot Capture Plan

### Priority 1: New Page Screenshots
- [ ] pyroscope.png - Full page capture
- [ ] tracing.png - Full page capture

### Priority 2: Update Existing Screenshots
These may need refreshing if UI changed significantly:
- [ ] logs.png - Verify shows Grafana/Loki embed
- [ ] analytics.png - Verify shows Grafana embed
- [ ] operations.png - Verify shows current layout

### Priority 3: Component Screenshots (from SCREENSHOT_GUIDE.md)
- [ ] placeholder-header-health.png
- [ ] placeholder-quick-stats.png
- [ ] placeholder-risk-gauge.png
- [ ] placeholder-risk-gauge-states.png (composite)
- [ ] placeholder-camera-grid.png
- [ ] placeholder-activity-feed.png
- [ ] placeholder-event-detail-modal.png
- [ ] placeholder-timeline-filters.png
- [ ] placeholder-detection-image.png
- [ ] placeholder-alert-cards-comparison.png (composite)
- [ ] placeholder-settings-ai-models.png
- [ ] placeholder-search-interface.png
- [ ] placeholder-log-detail-modal.png

---

## Implementation Recommendations

### Phase 1: Critical Documentation (Immediate)
1. Create pyroscope.md following dashboard.md template
2. Create tracing.md following dashboard.md template
3. Audit logs.md and analytics.md for accuracy
4. Capture screenshots for new pages

### Phase 2: Screenshot Refresh (Short-term)
1. Verify all existing screenshots match current UI
2. Capture missing page-level screenshots
3. Update SCREENSHOT_GUIDE.md checklist

### Phase 3: Component Documentation (Medium-term)
1. Create docs/components/ structure
2. Document Tier 1 common components
3. Add visual examples and usage patterns

### Phase 4: Quality Audit (Ongoing)
1. Apply documentation checklist to all UI docs
2. Fill gaps in sections (Settings, Troubleshooting, etc.)
3. Add Mermaid diagrams where helpful

---

## Appendix: Frontend Component Inventory

### Summary by Category

| Category | Component Count | Documentation Status |
|----------|-----------------|---------------------|
| Common/Reusable | 42 | None |
| Layout | 6 | None |
| Dashboard | 14 | Page doc only |
| Events | 20 | Page doc only |
| Detection | 4 | None |
| Alerts | 8 | Page doc only |
| Entities | 11 | Page doc only |
| Zones | 4 | Page doc only |
| Settings | 21 | Page doc only |
| Audit | 7 | Page doc only |
| AI Audit | 5 | Page doc only |
| AI Performance | 17 | Page doc only |
| Analytics | 9 | Page doc only |
| Jobs | 16 | Page doc only |
| Video | 1 | None |
| Logs | 1 | Page doc only |
| System | 11 | Page doc only |
| Developer Tools | 14 | None |
| Performance | 3 | None |
| Pyroscope | 1 | None |
| Tracing | 1 | None |
| Status | 1 | None |
| Search | 3 | None |
| Feedback | 1 | None |
| Exports | 2 | None |
| Pages | 3 | Partial |
| Utilities | 3 | None |
| **TOTAL** | **267** | **14 page docs** |

---

## Next Steps

1. **Create Linear Epic** - "Documentation Audit and Expansion (NEM-XXXX)"
2. **Create Subtasks** - Based on prioritized action plan
3. **Assign and Execute** - Work through Tier 1 items first
4. **Review and Iterate** - Verify documentation accuracy after each update
