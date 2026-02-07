/**
 * EventEnrichmentSummary - Aggregated enrichment data display for an event
 *
 * Fetches enrichment data for all detections in an event and displays
 * an aggregated summary including:
 * - Violence/threat detection results
 * - Clothing analysis highlights
 * - Face detection count
 * - Vehicle classification
 * - Pet classification
 * - Pose analysis alerts
 * - Image quality issues
 *
 * Uses the /api/events/{id}/enrichments endpoint to fetch all detection
 * enrichments in a single paginated request.
 */

import { useQuery } from '@tanstack/react-query';
import { clsx } from 'clsx';
import {
  Activity,
  AlertTriangle,
  Car,
  CreditCard,
  Dog,
  ImageIcon,
  Loader2,
  Shield,
  Shirt,
  User,
  Zap,
} from 'lucide-react';
import { useMemo } from 'react';

import { fetchApi } from '../../services/api';
import { formatConfidencePercent } from '../../utils/confidence';

import type { EnrichmentResponse } from '../../services/api';

// ============================================================================
// Types
// ============================================================================

interface EventEnrichmentsApiResponse {
  event_id: number;
  enrichments: EnrichmentResponse[];
  count: number;
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

export interface EventEnrichmentSummaryProps {
  /** Event ID to fetch enrichments for */
  eventId: number;
  /** Additional CSS classes */
  className?: string;
}

interface AggregatedEnrichment {
  totalDetections: number;
  enrichedDetections: number;
  faceCount: number;
  hasVehicle: boolean;
  vehicleDetails: Array<{ type?: string; color?: string; confidence?: number }>;
  hasLicensePlate: boolean;
  licensePlateTexts: string[];
  hasPet: boolean;
  petTypes: string[];
  hasViolence: boolean;
  violenceMaxScore: number;
  hasClothing: boolean;
  clothingItems: Array<{
    upper?: string;
    lower?: string;
    isSuspicious?: boolean;
    isServiceUniform?: boolean;
    hasFaceCovered?: boolean;
  }>;
  hasPose: boolean;
  poseAlerts: string[];
  hasImageQuality: boolean;
  imageQualityIssues: string[];
  averageQualityScore: number;
  processingErrors: string[];
}

// ============================================================================
// Helper Functions
// ============================================================================

function aggregateEnrichments(enrichments: EnrichmentResponse[]): AggregatedEnrichment {
  const result: AggregatedEnrichment = {
    totalDetections: enrichments.length,
    enrichedDetections: 0,
    faceCount: 0,
    hasVehicle: false,
    vehicleDetails: [],
    hasLicensePlate: false,
    licensePlateTexts: [],
    hasPet: false,
    petTypes: [],
    hasViolence: false,
    violenceMaxScore: 0,
    hasClothing: false,
    clothingItems: [],
    hasPose: false,
    poseAlerts: [],
    hasImageQuality: false,
    imageQualityIssues: [],
    averageQualityScore: 0,
    processingErrors: [],
  };

  let qualityScoreSum = 0;
  let qualityScoreCount = 0;

  for (const enrichment of enrichments) {
    // Check if enrichment has any meaningful (positive) data
    const faceCheck = enrichment.face as { detected?: boolean } | null | undefined;
    const plateCheck = enrichment.license_plate as { detected?: boolean } | null | undefined;
    const violenceCheck = enrichment.violence as { detected?: boolean } | null | undefined;
    const hasMeaningfulData = !!(
      (faceCheck?.detected) ||
      enrichment.vehicle ||
      (plateCheck?.detected) ||
      enrichment.pet ||
      (violenceCheck?.detected) ||
      enrichment.clothing ||
      enrichment.pose ||
      enrichment.image_quality
    );
    if (hasMeaningfulData) result.enrichedDetections++;

    // Face detection
    const face = enrichment.face as { detected?: boolean; count?: number } | null | undefined;
    if (face?.detected && face.count) {
      result.faceCount += face.count;
    }

    // Vehicle classification
    const vehicle = enrichment.vehicle as {
      type?: string;
      color?: string;
      confidence?: number;
    } | null | undefined;
    if (vehicle) {
      result.hasVehicle = true;
      result.vehicleDetails.push(vehicle);
    }

    // License plate
    const plate = enrichment.license_plate as {
      detected?: boolean;
      text?: string;
    } | null | undefined;
    if (plate?.detected && plate.text) {
      result.hasLicensePlate = true;
      if (!result.licensePlateTexts.includes(plate.text)) {
        result.licensePlateTexts.push(plate.text);
      }
    }

    // Pet detection
    const pet = enrichment.pet as {
      detected?: boolean;
      type?: string;
    } | null | undefined;
    if (pet?.detected && pet.type) {
      result.hasPet = true;
      if (!result.petTypes.includes(pet.type)) {
        result.petTypes.push(pet.type);
      }
    }

    // Violence detection
    const violence = enrichment.violence as {
      detected?: boolean;
      score?: number;
    } | null | undefined;
    if (violence?.detected) {
      result.hasViolence = true;
      if (violence.score && violence.score > result.violenceMaxScore) {
        result.violenceMaxScore = violence.score;
      }
    }

    // Clothing analysis
    const clothing = enrichment.clothing as {
      upper?: string;
      lower?: string;
      is_suspicious?: boolean;
      is_service_uniform?: boolean;
      has_face_covered?: boolean;
    } | null | undefined;
    if (clothing) {
      result.hasClothing = true;
      result.clothingItems.push({
        upper: clothing.upper,
        lower: clothing.lower,
        isSuspicious: clothing.is_suspicious,
        isServiceUniform: clothing.is_service_uniform,
        hasFaceCovered: clothing.has_face_covered,
      });
    }

    // Pose analysis
    const pose = enrichment.pose as {
      posture?: string;
      alerts?: string[];
      security_alerts?: string[];
    } | null | undefined;
    if (pose) {
      result.hasPose = true;
      const alerts = pose.alerts ?? pose.security_alerts ?? [];
      for (const alert of alerts) {
        if (!result.poseAlerts.includes(alert)) {
          result.poseAlerts.push(alert);
        }
      }
    }

    // Image quality
    const iq = enrichment.image_quality as {
      score?: number;
      quality_issues?: string[];
    } | null | undefined;
    if (iq) {
      result.hasImageQuality = true;
      if (iq.score !== undefined) {
        qualityScoreSum += iq.score;
        qualityScoreCount++;
      }
      if (iq.quality_issues) {
        for (const issue of iq.quality_issues) {
          if (!result.imageQualityIssues.includes(issue)) {
            result.imageQualityIssues.push(issue);
          }
        }
      }
    }

    // Errors
    if (enrichment.errors && enrichment.errors.length > 0) {
      result.processingErrors.push(...enrichment.errors);
    }
  }

  if (qualityScoreCount > 0) {
    result.averageQualityScore = qualityScoreSum / qualityScoreCount;
  }

  return result;
}

// ============================================================================
// Sub-components
// ============================================================================

function SummaryBadge({
  icon,
  label,
  value,
  variant = 'info',
}: {
  icon: React.ReactNode;
  label: string;
  value?: string | number;
  variant?: 'info' | 'warning' | 'alert' | 'success';
}) {
  const variantClasses = {
    info: 'border-blue-500/30 bg-blue-500/10 text-blue-400',
    warning: 'border-yellow-500/30 bg-yellow-500/10 text-yellow-400',
    alert: 'border-red-500/30 bg-red-500/10 text-red-400',
    success: 'border-green-500/30 bg-green-500/10 text-green-400',
  };

  return (
    <div
      className={clsx(
        'flex items-center gap-2 rounded-lg border px-3 py-2',
        variantClasses[variant]
      )}
    >
      {icon}
      <div className="flex flex-col">
        <span className="text-xs font-medium">{label}</span>
        {value !== undefined && (
          <span className="text-sm font-semibold text-white">{value}</span>
        )}
      </div>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export default function EventEnrichmentSummary({
  eventId,
  className,
}: EventEnrichmentSummaryProps) {
  const {
    data: response,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['eventEnrichments', eventId],
    queryFn: () =>
      fetchApi<EventEnrichmentsApiResponse>(`/api/events/${eventId}/enrichments?limit=200`),
    enabled: eventId > 0,
    staleTime: 60_000, // 1 minute
    retry: 1,
  });

  const aggregated = useMemo(() => {
    if (!response?.enrichments || response.enrichments.length === 0) return null;
    return aggregateEnrichments(response.enrichments);
  }, [response]);

  if (isLoading) {
    return (
      <div className={clsx('flex items-center gap-2 py-4 text-gray-400', className)}>
        <Loader2 className="h-4 w-4 animate-spin" />
        <span className="text-sm">Loading enrichment data...</span>
      </div>
    );
  }

  if (error || !aggregated || aggregated.enrichedDetections === 0) {
    return null;
  }

  const hasSuspiciousClothing = aggregated.clothingItems.some((c) => c.isSuspicious);
  const hasFaceCovered = aggregated.clothingItems.some((c) => c.hasFaceCovered);
  const hasServiceUniform = aggregated.clothingItems.some((c) => c.isServiceUniform);

  return (
    <div
      className={clsx('rounded-lg border border-gray-800 bg-black/20', className)}
      data-testid="event-enrichment-summary"
    >
      <div className="flex items-center justify-between border-b border-gray-800 px-4 py-3">
        <h3 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-gray-400">
          <Zap className="h-4 w-4 text-[#76B900]" />
          AI Enrichment Summary
        </h3>
        <span className="text-xs text-gray-500">
          {aggregated.enrichedDetections}/{aggregated.totalDetections} detections enriched
        </span>
      </div>

      <div className="p-4">
        {/* Threat Indicators - High Priority */}
        {(aggregated.hasViolence || aggregated.poseAlerts.length > 0 || hasSuspiciousClothing || hasFaceCovered) && (
          <div className="mb-4" data-testid="threat-indicators">
            <h4 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-red-400">
              <Shield className="h-3.5 w-3.5" />
              Threat Indicators
            </h4>
            <div className="flex flex-wrap gap-2">
              {aggregated.hasViolence && (
                <SummaryBadge
                  icon={<AlertTriangle className="h-4 w-4" />}
                  label="Violence Detected"
                  value={`${Math.round(aggregated.violenceMaxScore * 100)}% score`}
                  variant="alert"
                />
              )}
              {aggregated.poseAlerts.map((alert) => (
                <SummaryBadge
                  key={alert}
                  icon={<Activity className="h-4 w-4" />}
                  label={alert.replace('_', ' ')}
                  variant="alert"
                />
              ))}
              {hasSuspiciousClothing && (
                <SummaryBadge
                  icon={<Shirt className="h-4 w-4" />}
                  label="Suspicious Attire"
                  variant="warning"
                />
              )}
              {hasFaceCovered && (
                <SummaryBadge
                  icon={<User className="h-4 w-4" />}
                  label="Face Covered"
                  variant="warning"
                />
              )}
            </div>
          </div>
        )}

        {/* Detection Results Grid */}
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {aggregated.faceCount > 0 && (
            <SummaryBadge
              icon={<User className="h-4 w-4" />}
              label="Faces Detected"
              value={aggregated.faceCount}
              variant="info"
            />
          )}

          {aggregated.hasVehicle && aggregated.vehicleDetails.length > 0 && (
            <SummaryBadge
              icon={<Car className="h-4 w-4" />}
              label="Vehicle"
              value={aggregated.vehicleDetails
                .map((v) => [v.color, v.type].filter(Boolean).join(' '))
                .filter(Boolean)
                .join(', ') || 'Detected'}
              variant="info"
            />
          )}

          {aggregated.hasLicensePlate && (
            <SummaryBadge
              icon={<CreditCard className="h-4 w-4" />}
              label="License Plate"
              value={aggregated.licensePlateTexts.join(', ')}
              variant="info"
            />
          )}

          {aggregated.hasPet && (
            <SummaryBadge
              icon={<Dog className="h-4 w-4" />}
              label="Pet"
              value={aggregated.petTypes.join(', ')}
              variant="success"
            />
          )}

          {hasServiceUniform && (
            <SummaryBadge
              icon={<Shirt className="h-4 w-4" />}
              label="Service Uniform"
              variant="info"
            />
          )}

          {aggregated.hasImageQuality && aggregated.averageQualityScore > 0 && (
            <SummaryBadge
              icon={<ImageIcon className="h-4 w-4" />}
              label="Avg Image Quality"
              value={formatConfidencePercent(aggregated.averageQualityScore)}
              variant={aggregated.averageQualityScore >= 0.7 ? 'success' : 'warning'}
            />
          )}
        </div>

        {/* Clothing Details */}
        {aggregated.hasClothing && aggregated.clothingItems.length > 0 && (
          <div className="mt-3" data-testid="clothing-details">
            <h4 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-gray-400">
              <Shirt className="h-3.5 w-3.5 text-[#76B900]" />
              Clothing Analysis
            </h4>
            <div className="space-y-1">
              {aggregated.clothingItems.map((item, idx) => (
                <div key={idx} className="flex items-center gap-2 text-sm text-gray-300">
                  {item.upper && <span>Upper: {item.upper}</span>}
                  {item.upper && item.lower && <span className="text-gray-600">|</span>}
                  {item.lower && <span>Lower: {item.lower}</span>}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Image Quality Issues */}
        {aggregated.imageQualityIssues.length > 0 && (
          <div className="mt-3" data-testid="image-quality-issues">
            <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-400">
              Image Quality Issues
            </h4>
            <div className="flex flex-wrap gap-1">
              {aggregated.imageQualityIssues.map((issue) => (
                <span
                  key={issue}
                  className="rounded bg-yellow-500/20 px-1.5 py-0.5 text-xs text-yellow-400"
                >
                  {issue}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Processing Errors */}
        {aggregated.processingErrors.length > 0 && (
          <div className="mt-3" data-testid="processing-errors">
            <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-red-400">
              Processing Errors
            </h4>
            <div className="space-y-1">
              {aggregated.processingErrors.slice(0, 5).map((err, idx) => (
                <p key={idx} className="text-xs text-red-300/80">
                  {err}
                </p>
              ))}
              {aggregated.processingErrors.length > 5 && (
                <p className="text-xs text-gray-500">
                  + {aggregated.processingErrors.length - 5} more errors
                </p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
