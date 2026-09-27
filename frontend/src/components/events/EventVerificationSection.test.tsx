/**
 * Tests for EventVerificationSection (1.6, spec §4 "Event detail"):
 * verdict badge, scene description, criteria checklist, and "frames the
 * VLM reviewed" resolved from key_frame_detection_ids to existing
 * thumbnails - plus the retired-enrichment empty state (R8: empty states,
 * not deletions).
 */

import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import EventVerificationSection from './EventVerificationSection';
import { getDetectionThumbnailUrl } from '../../services/api';

import type { EventVerificationPayload } from '../../types/generated/websocket';

function fullPayload(overrides: Partial<EventVerificationPayload> = {}): EventVerificationPayload {
  return {
    verdict: 'confirmed',
    scene_description: 'A person in a dark jacket walks along the driveway.',
    criteria: [
      { name: 'person_present', passed: true, evidence: 'full-body person, left third' },
      { name: 'loitering', passed: false, evidence: null },
    ],
    key_frame_detection_ids: [101, 102],
    engine: 'llama.cpp',
    model_id: 'qwen3-vl-4b',
    latency_ms: 312,
    created_at: '2026-09-26T10:00:00Z',
    ...overrides,
  };
}

describe('EventVerificationSection', () => {
  it('renders nothing when there is no verification (legacy/pre-1.3 event)', () => {
    const { container } = render(<EventVerificationSection verification={null} />);
    expect(container).toBeEmptyDOMElement();
    const { container: c2 } = render(<EventVerificationSection verification={undefined} />);
    expect(c2).toBeEmptyDOMElement();
  });

  it('names the verdict - never a bare score', () => {
    render(<EventVerificationSection verification={fullPayload()} />);
    expect(screen.getByTestId('verification-section')).toBeInTheDocument();
    expect(screen.getByRole('status', { name: /verification verdict/i })).toHaveTextContent(
      /confirmed/i
    );
  });

  it('shows the scene description', () => {
    render(<EventVerificationSection verification={fullPayload()} />);
    expect(screen.getByText(/person in a dark jacket/i)).toBeInTheDocument();
  });

  it('renders the criteria checklist with pass/fail and evidence', () => {
    render(<EventVerificationSection verification={fullPayload()} />);

    const passed = screen.getByTestId('criterion-person_present');
    expect(passed).toHaveAttribute('data-passed', 'true');
    expect(passed).toHaveTextContent(/full-body person/i);

    const failed = screen.getByTestId('criterion-loitering');
    expect(failed).toHaveAttribute('data-passed', 'false');
    // A failed criterion states no evidence rather than an empty quote.
    expect(failed).not.toHaveTextContent(/null/i);
  });

  it('hides the checklist when criteria is absent or empty (R8 empty state)', () => {
    const { rerender } = render(<EventVerificationSection verification={fullPayload()} />);
    expect(screen.getByTestId('verification-criteria')).toBeInTheDocument();

    rerender(<EventVerificationSection verification={fullPayload({ criteria: [] })} />);
    expect(screen.queryByTestId('verification-criteria')).not.toBeInTheDocument();

    rerender(<EventVerificationSection verification={fullPayload({ criteria: null })} />);
    expect(screen.queryByTestId('verification-criteria')).not.toBeInTheDocument();
  });

  it('resolves reviewed frames to existing thumbnails by detection id', () => {
    render(<EventVerificationSection verification={fullPayload()} />);

    const frames = screen.getAllByRole('img', { name: /reviewed frame/i });
    expect(frames).toHaveLength(2);
    expect(frames[0]).toHaveAttribute('src', getDetectionThumbnailUrl(101));
    expect(frames[1]).toHaveAttribute('src', getDetectionThumbnailUrl(102));
  });

  it('hides the frames block when no key frames were recorded', () => {
    const { rerender } = render(
      <EventVerificationSection verification={fullPayload({ key_frame_detection_ids: [] })} />
    );
    expect(screen.queryAllByRole('img', { name: /reviewed frame/i })).toHaveLength(0);

    rerender(
      <EventVerificationSection verification={fullPayload({ key_frame_detection_ids: null })} />
    );
    expect(screen.queryAllByRole('img', { name: /reviewed frame/i })).toHaveLength(0);
  });

  it('verification_failed: names the failure, shows none of the absent parts', () => {
    render(
      <EventVerificationSection
        verification={fullPayload({
          verdict: 'verification_failed',
          scene_description: null,
          criteria: null,
          key_frame_detection_ids: null,
          latency_ms: null,
        })}
      />
    );
    expect(screen.getByRole('status', { name: /verification verdict/i })).toHaveTextContent(
      /verification failed/i
    );
    expect(screen.queryByTestId('verification-criteria')).not.toBeInTheDocument();
    expect(screen.queryAllByRole('img', { name: /reviewed frame/i })).toHaveLength(0);
  });

  it('credits the engine and model that produced the verdict', () => {
    render(<EventVerificationSection verification={fullPayload()} />);
    expect(screen.getByText(/llama\.cpp/i)).toBeInTheDocument();
    expect(screen.getByText(/qwen3-vl-4b/i)).toBeInTheDocument();
    expect(screen.getByText(/312\s?ms/i)).toBeInTheDocument();
  });
});
