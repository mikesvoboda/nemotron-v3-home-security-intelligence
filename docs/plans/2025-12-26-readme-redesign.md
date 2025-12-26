# README Redesign Plan

**Date:** 2025-12-26
**Status:** Approved

## Goals

Redesign README.md to serve four audiences:

1. Future self - reference after months away
2. Contributors - understand and contribute
3. Users deploying - run on their own hardware
4. Showcase - demonstrate work to others

## Design Principles

- **Problem-first hook** - Lead with value, not technology
- **Layered approach** - Quick overview up top, `<details>` for depth
- **Scannable** - Tables over prose, clear headings
- **Visual placeholders** - Design for screenshots/diagrams to be added

## Structure

### Section 1: Hero (~30 lines)

- Title + tagline ("Turn dumb security cameras into intelligent threat detection")
- Screenshot placeholder (dashboard with risk gauge, events)
- "What it does" - 2-3 sentence explanation
- Quick stats table (detection speed, LLM, storage, interface, GPU)
- Badges (moved below the hook)

### Section 2: Get Running

- Prerequisites (honest about GPU requirement upfront)
- 4-step numbered quick start (copy-pasteable)
- "That's it." confirmation
- Linux networking note in collapsed `<details>`

### Section 3: How It Works

- ASCII flow diagram (works everywhere)
- Placeholder for visual diagram
- Collapsed: "Why batch detections?" explanation
- Collapsed: Service ports table

### Section 4: Features + API

- Feature table (scannable)
- Collapsed: REST API endpoints (points to Swagger)
- Collapsed: WebSocket streams
- Collapsed: Database schema summary

### Section 5: Configuration

- One visible line: "Copy .env.example to .env"
- Collapsed: Full environment variables tables
- Collapsed: Tuning tips (practical Q&A format)

### Section 6: Development

- Test command front and center
- Stats table (335 backend/98%, 233 frontend/99%)
- Collapsed: Specific test commands
- Pre-commit hooks note (never --no-verify)
- Collapsed: What hooks check
- Minimal project structure
- AGENTS.md tip

### Section 7: Troubleshooting & Closing

- All troubleshooting in collapsed sections
- Security warning (visible, not collapsed)
- Contributing (bd commands)
- License (brief)
- Acknowledgments (inline links)

## Visual Assets Needed

1. **Hero screenshot** - Dashboard showing:

   - Risk gauge with score
   - Camera grid
   - Recent event card ("Person detected at back door", risk 72)

2. **Architecture diagram** - Horizontal flow:
   - Camera → FileWatcher → RT-DETRv2 → BatchAggregator → Nemotron → Dashboard

## Implementation

Replace existing README.md with new structure. Estimated length: ~250 lines collapsed, ~150 lines visible on first load.
