# Discovery: Event Clip Generation UI Not Accessible from Timeline

**Issue:** NEM-3590
**Epic:** NEM-3530 (Platform Integration Gaps & Production Readiness)
**Date:** 2026-01-26

## Summary

Event clip generation functionality exists but is only accessible from within the event detail modal, not directly from the timeline view.

## Current State

### Backend Implementation (Fully Functional)

**API Endpoints:**

- `GET /api/events/{event_id}/clip` - Fetch clip info (`backend/api/routes/events.py`)
- `POST /api/events/{event_id}/clip/generate` - Generate clip (`backend/api/routes/events.py`)
- `GET /api/media/clips/{filename}` - Serve generated clips (`backend/api/routes/media.py`)

**Service Layer:**

- `ClipGenerator` service in `backend/services/clip_generator.py`
- Handles MP4 generation from image sequences or video extraction
- Stores clips in configured clips directory

**Database:**

- Event model includes `clip_path` field to store generated clip location

### Frontend Implementation (Partial)

**API Client Functions** (`frontend/src/services/api.ts`):

- `fetchEventClipInfo(eventId)` - Get clip availability info
- `generateEventClip(eventId)` - Trigger clip generation
- `getEventClipUrl(clipFilename)` - Get clip URL

**Components:**

- `EventVideoPlayer` component (`frontend/src/components/events/EventVideoPlayer.tsx`)
  - Automatic clip availability check on mount
  - Generate clip button when clip doesn't exist
  - Loading states during generation
  - HTML5 video player with controls
  - Download button for clips
- Integrated into `EventDetailModal` as the "Video Clip" tab

## The Gap

**Where clip generation IS accessible:**

1. User opens EventTimeline view
2. User clicks on an event card to open EventDetailModal
3. User clicks the "Video Clip" tab
4. User sees EventVideoPlayer with option to generate clip

**Where it's NOT accessible (the gap):**

1. **From EventCard in timeline** - No direct clip generation button
2. **From TimelineScrubber** - Visual timeline can't trigger clip generation
3. **Bulk operations** - No way to generate clips for multiple events
4. **From event list view** - List view has no clip generation actions

## Root Cause

The clip generation UI is designed as:

- **Discovery feature** - Available only when user explicitly opens event detail modal
- **On-demand generation** - Created only when explicitly requested
- **Resource optimization** - Avoids generating clips for events users may not care about

This is reasonable for single-event workflow but creates a discoverability problem.

## Recommendations

1. **EventCard Enhancement** - Add clip generation button/icon in event card footer
2. **Quick Action Menu** - Add clip generation to card's context menu
3. **Bulk Clip Generation** - Extend bulk actions to include "Generate Clips for Selected Events"
4. **Discovery Improvements** - Add tooltip explaining clip feature on first discovery

## Files to Modify

- `frontend/src/components/events/EventCard.tsx` - Add clip action button
- `frontend/src/components/events/EventTimeline.tsx` - Add bulk clip generation
- `backend/api/routes/events.py` - May need batch generation endpoint

## Status

**Assessment:** Feature gap requiring UI work. Backend infrastructure is complete.
