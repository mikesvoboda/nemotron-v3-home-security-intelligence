import { CheckCircle2, XCircle } from 'lucide-react';

import { getDetectionThumbnailUrl } from '../../services/api';
import VerdictBadge from '../common/VerdictBadge';

import type { EventVerificationPayload } from '../../types/generated/websocket';

export interface EventVerificationSectionProps {
  /**
   * The event's verification payload (REST `verification` / WS payload,
   * spec §4). Null/undefined = no verification row (legacy events, pre-1.3
   * history): the section renders nothing - the header VerdictBadge already
   * states "Unverified", and an empty section would only add a dead box.
   */
  verification: EventVerificationPayload | null | undefined;
  className?: string;
}

/**
 * EventVerificationSection - what the VLM actually said (spec §4 "Event
 * detail": verdict badge, scene description, criteria checklist, "frames
 * the VLM reviewed"). Every block is data-gated (R8 doctrine: a retired
 * producer leaves an empty state, never a phantom): a verification_failed
 * verdict carries only the verdict, and the section says exactly that -
 * nothing is padded in to fill the layout.
 */
export default function EventVerificationSection({
  verification,
  className = '',
}: EventVerificationSectionProps) {
  if (!verification) return null;

  const { verdict, scene_description, criteria, key_frame_detection_ids, engine, model_id } =
    verification;
  const latencyMs = verification.latency_ms;
  const frames = key_frame_detection_ids ?? [];
  const criteriaList = criteria ?? [];

  return (
    <section
      data-testid="verification-section"
      className={`rounded-lg border border-gray-800 bg-gray-900/50 p-4 ${className}`}
      aria-label="VLM verification"
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-400">
          VLM verification
        </h3>
        <VerdictBadge verdict={verdict} size="md" />
      </div>

      {scene_description && (
        <p data-testid="verification-scene" className="mb-3 text-sm text-gray-200">
          {scene_description}
        </p>
      )}

      {criteriaList.length > 0 && (
        <ul data-testid="verification-criteria" className="mb-3 space-y-1.5">
          {criteriaList.map((criterion) => (
            <li
              key={criterion.name}
              data-testid={`criterion-${criterion.name}`}
              data-passed={String(criterion.passed)}
              className="flex items-start gap-2 text-sm"
            >
              {criterion.passed ? (
                <CheckCircle2 className="mt-0.5 h-4 w-4 flex-shrink-0 text-[#76B900]" />
              ) : (
                <XCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-red-400" />
              )}
              <span className="text-gray-200">{criterion.name}</span>
              {/* Failed criteria state no evidence rather than an empty
                  quote - the absence is itself the answer. */}
              {criterion.evidence && (
                <span className="min-w-0 flex-1 text-xs text-text-secondary">
                  {criterion.evidence}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}

      {frames.length > 0 && (
        <div className="mb-3">
          <h4 className="mb-2 text-xs font-medium uppercase tracking-wide text-gray-500">
            Frames the VLM reviewed
          </h4>
          {/* Existing detection thumbnails by id (spec §4) - the frames are
              REFERENCED, never re-stored (privacy rule: paths/ids only). */}
          <div className="flex flex-wrap gap-2">
            {frames.map((detectionId, index) => (
              <img
                key={detectionId}
                src={getDetectionThumbnailUrl(detectionId)}
                alt={`Reviewed frame ${index + 1} (detection ${detectionId})`}
                className="h-16 w-16 rounded-md border border-gray-700 object-cover"
                loading="lazy"
              />
            ))}
          </div>
        </div>
      )}

      <p className="text-xs text-gray-500">
        {engine} · {model_id}
        {latencyMs !== null && latencyMs !== undefined && <> · {latencyMs} ms</>}
      </p>
    </section>
  );
}
