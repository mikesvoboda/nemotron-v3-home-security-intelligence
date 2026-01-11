/**
 * EnrichmentPanel - Displays AI enrichment data for detections
 *
 * Shows enrichment data in collapsible accordion sections, including:
 * - Vehicle classification (type, color, damage, commercial status)
 * - Pet identification (type, breed)
 * - Person attributes (clothing, action, carrying, suspicious/service indicators)
 * - Pose analysis (posture, security alerts from ViTPose)
 * - License plate OCR results
 * - Weather conditions
 * - Image quality assessment
 * - Pose visualization (posture, security alerts, keypoint confidence)
 */

import { Accordion, AccordionHeader, AccordionBody, AccordionList } from '@tremor/react';
import { clsx } from 'clsx';
import {
  Activity,
  AlertTriangle,
  Briefcase,
  Car,
  Cloud,
  CreditCard,
  Dog,
  ImageIcon,
  Package,
  ShieldAlert,
  Heart,
  Swords,
  HandMetal,
  User,
} from 'lucide-react';


import { getPostureRiskLevel } from '../../types/enrichment';
import {
  formatConfidencePercent,
  getConfidenceBgColorClass,
  getConfidenceBorderColorClass,
  getConfidenceLevel,
  getConfidenceTextColorClass,
} from '../../utils/confidence';

import type { EnrichmentData, SecurityAlertType, PostureType } from '../../types/enrichment';
import type { ReactElement } from 'react';

export interface EnrichmentPanelProps {
  /** Enrichment data to display */
  enrichment_data?: EnrichmentData | null;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Confidence badge component for consistent confidence display
 */
function ConfidenceBadge({ confidence }: { confidence: number }) {
  const level = getConfidenceLevel(confidence);
  const percent = formatConfidencePercent(confidence);

  return (
    <span
      className={clsx(
        'inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium',
        getConfidenceBgColorClass(level),
        getConfidenceBorderColorClass(level),
        getConfidenceTextColorClass(level)
      )}
    >
      {percent}
    </span>
  );
}

/**
 * Detail row component for consistent key-value display
 */
function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-2 py-1">
      <span className="text-sm text-gray-400">{label}</span>
      <span className="text-sm text-gray-200 text-right">{value}</span>
    </div>
  );
}

/**
 * Badge indicator for boolean flags
 */
function FlagBadge({ label, variant = 'default' }: { label: string; variant?: 'alert' | 'warning' | 'info' | 'default' }) {
  const variantClasses = {
    alert: 'bg-red-500/20 border-red-500/40 text-red-400',
    warning: 'bg-yellow-500/20 border-yellow-500/40 text-yellow-400',
    info: 'bg-blue-500/20 border-blue-500/40 text-blue-400',
    default: 'bg-gray-500/20 border-gray-500/40 text-gray-400',
  };

  return (
    <span className={clsx('inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium', variantClasses[variant])}>
      {(variant === 'alert' || variant === 'warning') && <AlertTriangle className="h-3 w-3" />}
      {variant === 'info' && <Briefcase className="h-3 w-3" />}
      {label}
    </span>
  );
}

/**
 * Get badge color class for posture type
 */
function getPostureBadgeClass(posture: PostureType): string {
  switch (posture) {
    case 'standing':
    case 'sitting':
      return 'bg-gray-500/20 border-gray-500/40 text-gray-400';
    case 'walking':
      return 'bg-blue-500/20 border-blue-500/40 text-blue-400';
    case 'running':
      return 'bg-yellow-500/20 border-yellow-500/40 text-yellow-400';
    case 'crouching':
    case 'lying_down':
      return 'bg-red-500/20 border-red-500/40 text-red-400';
    default:
      return 'bg-gray-500/20 border-gray-500/40 text-gray-400';
  }
}

/**
 * Security alert labels with emoji indicators
 */
const SECURITY_ALERT_LABELS: Record<SecurityAlertType, { emoji: string; label: string; description: string }> = {
  crouching: {
    emoji: '\u26A0\uFE0F',
    label: 'Crouching Detected',
    description: 'Person in crouching position may indicate suspicious behavior or hiding.',
  },
  lying_down: {
    emoji: '\uD83D\uDEA8',
    label: 'Person Down',
    description: 'Person lying on ground may indicate medical emergency or security incident.',
  },
  hands_raised: {
    emoji: '\uD83D\uDE4C',
    label: 'Hands Raised',
    description: 'Raised hands detected, may indicate surrender or distress signal.',
  },
  fighting_stance: {
    emoji: '\u2694\uFE0F',
    label: 'Aggressive Posture',
    description: 'Aggressive stance detected, may indicate potential confrontation.',
  },
};

/**
 * Posture badge component for pose display
 */
function PostureBadge({ posture }: { posture: PostureType }) {
  const badgeClass = getPostureBadgeClass(posture);
  const formattedPosture = posture.replace('_', ' ');

  return (
    <span
      className={clsx(
        'inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium capitalize',
        badgeClass
      )}
      data-testid="posture-badge"
    >
      {formattedPosture}
    </span>
  );
}

/**
 * Security alert component for pose display
 */
function SecurityAlertBadge({ alert }: { alert: SecurityAlertType }) {
  const alertInfo = SECURITY_ALERT_LABELS[alert];

  return (
    <div
      className="rounded-md border border-red-500/40 bg-red-500/20 px-3 py-2"
      data-testid={`security-alert-${alert}`}
    >
      <div className="flex items-center gap-2 text-sm font-medium text-red-400">
        <span>{alertInfo.emoji}</span>
        <span>{alertInfo.label}</span>
      </div>
      <p className="mt-1 text-xs text-red-300/80">{alertInfo.description}</p>
    </div>
  );
}

/**
 * Check if enrichment data has any actual content
 */
function hasEnrichmentContent(data?: EnrichmentData | null): boolean {
  if (!data) return false;
  return !!(
    data.vehicle ||
    data.pet ||
    data.person ||
    data.posture ||
    data.license_plate ||
    data.weather ||
    data.image_quality ||
    data.pose
  );
}

/**
 * Get human-readable posture display name
 */
function getPostureDisplayName(posture: string): string {
  const displayNames: Record<string, string> = {
    standing: 'Standing',
    walking: 'Walking',
    running: 'Running',
    sitting: 'Sitting',
    crouching: 'Crouching',
    lying_down: 'Lying Down',
    unknown: 'Unknown',
  };
  return displayNames[posture] || posture;
}

/**
 * Get posture badge styling based on security relevance
 */
function getPostureBadgeStyle(posture: string): { bg: string; border: string; text: string } {
  // High-alert postures
  if (posture === 'crouching' || posture === 'lying_down') {
    return {
      bg: 'bg-red-500/20',
      border: 'border-red-500/40',
      text: 'text-red-400',
    };
  }
  // Active movement postures
  if (posture === 'running') {
    return {
      bg: 'bg-orange-500/20',
      border: 'border-orange-500/40',
      text: 'text-orange-400',
    };
  }
  // Normal postures
  return {
    bg: 'bg-green-500/20',
    border: 'border-green-500/40',
    text: 'text-green-400',
  };
}

/**
 * Get alert icon and styling for security alerts
 */
function getAlertDisplay(alert: string): { icon: React.ReactNode; label: string; description: string } {
  switch (alert) {
    case 'crouching':
      return {
        icon: <ShieldAlert className="h-4 w-4" />,
        label: 'Crouching Detected',
        description: 'Potential hiding or break-in attempt',
      };
    case 'lying_down':
      return {
        icon: <Heart className="h-4 w-4" />,
        label: 'Person Down',
        description: 'Possible medical emergency',
      };
    case 'hands_raised':
      return {
        icon: <HandMetal className="h-4 w-4" />,
        label: 'Hands Raised',
        description: 'Surrender or robbery situation',
      };
    case 'fighting_stance':
      return {
        icon: <Swords className="h-4 w-4" />,
        label: 'Fighting Stance',
        description: 'Aggressive posture detected',
      };
    default:
      return {
        icon: <AlertTriangle className="h-4 w-4" />,
        label: alert,
        description: 'Security alert',
      };
  }
}

/**
 * EnrichmentPanel - Main component
 */
export default function EnrichmentPanel({
  enrichment_data,
  className,
}: EnrichmentPanelProps) {
  // Don't render anything if there's no enrichment data
  if (!hasEnrichmentContent(enrichment_data)) {
    return null;
  }

  // Build array of accordion sections that have data
  const accordionSections: ReactElement[] = [];

  // Vehicle Section
  if (enrichment_data?.vehicle) {
    accordionSections.push(
      <Accordion key="vehicle" data-testid="enrichment-vehicle">
        <AccordionHeader className="px-4 py-3 text-white hover:bg-gray-800/50">
          <div className="flex w-full items-center justify-between pr-2">
            <div className="flex items-center gap-2">
              <Car className="h-4 w-4 text-[#76B900]" />
              <span className="font-medium">Vehicle</span>
            </div>
            <ConfidenceBadge confidence={enrichment_data.vehicle.confidence} />
          </div>
        </AccordionHeader>
        <AccordionBody className="bg-black/20 px-4 py-3">
          <div className="space-y-1">
            <DetailRow label="Type" value={enrichment_data.vehicle.type} />
            <DetailRow label="Color" value={enrichment_data.vehicle.color} />
            {(enrichment_data.vehicle.damage?.length ?? 0) > 0 && (
              <DetailRow
                label="Damage"
                value={
                  <div className="flex flex-wrap gap-1 justify-end">
                    {enrichment_data.vehicle.damage?.map((d, i) => (
                      <span
                        key={i}
                        className="rounded bg-red-500/20 px-1.5 py-0.5 text-xs text-red-400"
                      >
                        {d}
                      </span>
                    ))}
                  </div>
                }
              />
            )}
            {enrichment_data.vehicle.commercial && (
              <div className="pt-2">
                <FlagBadge label="Commercial Vehicle" variant="info" />
              </div>
            )}
          </div>
        </AccordionBody>
      </Accordion>
    );
  }

  // Pet Section
  if (enrichment_data?.pet) {
    accordionSections.push(
      <Accordion key="pet" data-testid="enrichment-pet">
        <AccordionHeader className="px-4 py-3 text-white hover:bg-gray-800/50">
          <div className="flex w-full items-center justify-between pr-2">
            <div className="flex items-center gap-2">
              <Dog className="h-4 w-4 text-[#76B900]" />
              <span className="font-medium">Pet</span>
            </div>
            <ConfidenceBadge confidence={enrichment_data.pet.confidence} />
          </div>
        </AccordionHeader>
        <AccordionBody className="bg-black/20 px-4 py-3">
          <div className="space-y-1">
            <DetailRow label="Type" value={enrichment_data.pet.type} />
            {enrichment_data.pet.breed && (
              <DetailRow label="Breed" value={enrichment_data.pet.breed} />
            )}
          </div>
        </AccordionBody>
      </Accordion>
    );
  }

  // Person Section
  if (enrichment_data?.person) {
    accordionSections.push(
      <Accordion key="person" data-testid="enrichment-person">
        <AccordionHeader className="px-4 py-3 text-white hover:bg-gray-800/50">
          <div className="flex w-full items-center justify-between pr-2">
            <div className="flex items-center gap-2">
              <User className="h-4 w-4 text-[#76B900]" />
              <span className="font-medium">Person</span>
            </div>
            <ConfidenceBadge confidence={enrichment_data.person.confidence} />
          </div>
        </AccordionHeader>
        <AccordionBody className="bg-black/20 px-4 py-3">
          <div className="space-y-1">
            {enrichment_data.person.clothing && (
              <DetailRow label="Clothing" value={enrichment_data.person.clothing} />
            )}
            {enrichment_data.person.action && (
              <DetailRow label="Action" value={enrichment_data.person.action} />
            )}
            {enrichment_data.person.carrying && (
              <DetailRow
                label="Carrying"
                value={
                  <span className="flex items-center gap-1">
                    <Package className="h-3 w-3" />
                    {enrichment_data.person.carrying}
                  </span>
                }
              />
            )}
            <div className="flex flex-wrap gap-2 pt-2">
              {enrichment_data.person.suspicious_attire && (
                <FlagBadge label="Suspicious Attire" variant="warning" />
              )}
              {enrichment_data.person.service_uniform && (
                <FlagBadge label="Service Uniform" variant="info" />
              )}
            </div>
          </div>
        </AccordionBody>
      </Accordion>
    );
  }

  // Pose Section (ViTPose Analysis)
  if (enrichment_data?.pose) {
    const hasAlerts = enrichment_data.pose.alerts.length > 0;
    const postureStyle = getPostureBadgeStyle(enrichment_data.pose.posture);

    accordionSections.push(
      <Accordion key="pose" data-testid="enrichment-pose" defaultOpen={hasAlerts}>
        <AccordionHeader className="px-4 py-3 text-white hover:bg-gray-800/50">
          <div className="flex w-full items-center justify-between pr-2">
            <div className="flex items-center gap-2">
              <Activity className={clsx('h-4 w-4', hasAlerts ? 'text-red-500' : 'text-[#76B900]')} />
              <span className="font-medium">Pose Analysis</span>
              {hasAlerts && (
                <span className="ml-1 flex h-5 w-5 items-center justify-center rounded-full bg-red-500 text-xs font-bold text-white">
                  {enrichment_data.pose.alerts.length}
                </span>
              )}
            </div>
            <span
              className={clsx(
                'inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium',
                postureStyle.bg,
                postureStyle.border,
                postureStyle.text
              )}
            >
              {getPostureDisplayName(enrichment_data.pose.posture)}
            </span>
          </div>
        </AccordionHeader>
        <AccordionBody className="bg-black/20 px-4 py-3">
          <div className="space-y-3">
            {/* Posture Information */}
            <DetailRow label="Posture" value={getPostureDisplayName(enrichment_data.pose.posture)} />
            <DetailRow label="Keypoints Detected" value={`${enrichment_data.pose.keypoint_count}/17`} />

            {/* Security Alerts Section */}
            {hasAlerts && (
              <div className="mt-3 space-y-2">
                <span className="text-sm font-medium text-red-400 uppercase tracking-wide">Security Alerts</span>
                <div className="space-y-2">
                  {enrichment_data.pose.alerts.map((alert, i) => {
                    const alertInfo = getAlertDisplay(alert);
                    return (
                      <div
                        key={i}
                        className="flex items-start gap-3 rounded-lg border border-red-500/30 bg-red-500/10 p-3"
                        data-testid={`pose-alert-${alert}`}
                      >
                        <div className="flex-shrink-0 text-red-400">{alertInfo.icon}</div>
                        <div>
                          <span className="font-medium text-red-400">{alertInfo.label}</span>
                          <p className="text-sm text-gray-400">{alertInfo.description}</p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* No alerts indicator */}
            {!hasAlerts && (
              <div className="mt-2 rounded-lg border border-green-500/30 bg-green-500/10 p-3">
                <div className="flex items-center gap-2 text-green-400">
                  <Activity className="h-4 w-4" />
                  <span className="text-sm">Normal posture - no security concerns</span>
                </div>
              </div>
            )}
          </div>
        </AccordionBody>
      </Accordion>
    );
  }

  // License Plate Section
  if (enrichment_data?.license_plate) {
    accordionSections.push(
      <Accordion key="license_plate" data-testid="enrichment-license-plate">
        <AccordionHeader className="px-4 py-3 text-white hover:bg-gray-800/50">
          <div className="flex w-full items-center justify-between pr-2">
            <div className="flex items-center gap-2">
              <CreditCard className="h-4 w-4 text-[#76B900]" />
              <span className="font-medium">License Plate</span>
            </div>
            <ConfidenceBadge confidence={enrichment_data.license_plate.confidence} />
          </div>
        </AccordionHeader>
        <AccordionBody className="bg-black/20 px-4 py-3">
          <div className="flex items-center justify-center py-2">
            <span className="rounded bg-gray-900 px-4 py-2 font-mono text-lg text-white tracking-wider border border-gray-700">
              {enrichment_data.license_plate.text}
            </span>
          </div>
        </AccordionBody>
      </Accordion>
    );
  }

  // Weather Section
  if (enrichment_data?.weather) {
    accordionSections.push(
      <Accordion key="weather" data-testid="enrichment-weather">
        <AccordionHeader className="px-4 py-3 text-white hover:bg-gray-800/50">
          <div className="flex w-full items-center justify-between pr-2">
            <div className="flex items-center gap-2">
              <Cloud className="h-4 w-4 text-[#76B900]" />
              <span className="font-medium">Weather</span>
            </div>
            <ConfidenceBadge confidence={enrichment_data.weather.confidence} />
          </div>
        </AccordionHeader>
        <AccordionBody className="bg-black/20 px-4 py-3">
          <div className="space-y-1">
            <DetailRow label="Condition" value={enrichment_data.weather.condition} />
          </div>
        </AccordionBody>
      </Accordion>
    );
  }

  // Image Quality Section
  if (enrichment_data?.image_quality) {
    accordionSections.push(
      <Accordion key="image_quality" data-testid="enrichment-image-quality">
        <AccordionHeader className="px-4 py-3 text-white hover:bg-gray-800/50">
          <div className="flex w-full items-center justify-between pr-2">
            <div className="flex items-center gap-2">
              <ImageIcon className="h-4 w-4 text-[#76B900]" />
              <span className="font-medium">Image Quality</span>
            </div>
            <ConfidenceBadge confidence={enrichment_data.image_quality.score} />
          </div>
        </AccordionHeader>
        <AccordionBody className="bg-black/20 px-4 py-3">
          <div className="space-y-2">
            <DetailRow
              label="Quality Score"
              value={formatConfidencePercent(enrichment_data.image_quality.score)}
            />
            {enrichment_data.image_quality.issues.length > 0 && (
              <DetailRow
                label="Issues"
                value={
                  <div className="flex flex-wrap gap-1 justify-end">
                    {enrichment_data.image_quality.issues.map((issue, i) => (
                      <span
                        key={i}
                        className="rounded bg-yellow-500/20 px-1.5 py-0.5 text-xs text-yellow-400"
                      >
                        {issue}
                      </span>
                    ))}
                  </div>
                }
              />
            )}
          </div>
        </AccordionBody>
      </Accordion>
    );
  }

  // Pose Section
  if (enrichment_data?.pose) {
    const pose = enrichment_data.pose;
    // Use alerts (HEAD) or security_alerts (fallback) for compatibility
    const securityAlerts: string[] = pose.alerts ?? pose.security_alerts ?? [];
    const hasSecurityAlerts = securityAlerts.length > 0;

    // Calculate keypoint confidence summary
    const keypoints = pose.keypoints;
    const validKeypoints = keypoints.filter((kp) => kp[2] > 0);
    const avgConfidence = validKeypoints.length > 0
      ? validKeypoints.reduce((sum, kp) => sum + kp[2], 0) / validKeypoints.length
      : 0;
    const highConfidenceCount = keypoints.filter((kp) => kp[2] > 0.5).length;

    accordionSections.push(
      <Accordion key="pose" data-testid="enrichment-pose">
        <AccordionHeader
          className={clsx(
            'px-4 py-3 text-white hover:bg-gray-800/50',
            hasSecurityAlerts && 'bg-red-900/20'
          )}
        >
          <div className="flex w-full items-center justify-between pr-2">
            <div className="flex items-center gap-2">
              <Activity className={clsx('h-4 w-4', hasSecurityAlerts ? 'text-red-500' : 'text-[#76B900]')} />
              <span className="font-medium">Pose Analysis</span>
              {hasSecurityAlerts && (
                <span className="ml-1 inline-flex items-center rounded-full bg-red-500 px-2 py-0.5 text-xs font-semibold text-white">
                  {securityAlerts.length} Alert{securityAlerts.length > 1 ? 's' : ''}
                </span>
              )}
            </div>
            <ConfidenceBadge confidence={pose.confidence ?? 0} />
          </div>
        </AccordionHeader>
        <AccordionBody
          className={clsx(
            'px-4 py-3',
            hasSecurityAlerts ? 'bg-red-50/5 border-l-2 border-red-500' : 'bg-black/20'
          )}
        >
          <div className="space-y-3">
            {/* Security Alerts Section - High Visibility */}
            {hasSecurityAlerts && (
              <div
                className="space-y-2 rounded-lg border border-red-200 bg-red-50 p-3 dark:border-red-800 dark:bg-red-900/20"
                data-testid="pose-security-alerts"
              >
                <div className="text-xs font-semibold uppercase tracking-wide text-red-600 dark:text-red-400">
                  Security Alerts
                </div>
                <div className="space-y-2">
                  {securityAlerts.map((alert) => (
                    <SecurityAlertBadge key={alert} alert={alert as SecurityAlertType} />
                  ))}
                </div>
              </div>
            )}

            {/* Posture */}
            <DetailRow
              label="Posture"
              value={<PostureBadge posture={pose.posture as PostureType} />}
            />

            {/* Keypoint Confidence Summary */}
            <DetailRow
              label="Keypoint Confidence"
              value={
                <div className="text-right">
                  <span className="text-sm text-gray-200">
                    {formatConfidencePercent(avgConfidence)} avg
                  </span>
                </div>
              }
            />
            <DetailRow
              label="High-Confidence Points"
              value={
                <span className="text-sm text-gray-200">
                  {highConfidenceCount} / 17
                </span>
              }
            />
          </div>
        </AccordionBody>
      </Accordion>
    );
  }

  return (
    <div
      data-testid="enrichment-panel"
      className={clsx('rounded-lg border border-gray-800 bg-black/20', className)}
    >
      <h3 className="px-4 py-3 text-sm font-semibold uppercase tracking-wide text-gray-400 border-b border-gray-800">
        AI Enrichment Analysis
      </h3>

      <AccordionList className="divide-y divide-gray-800">
        {accordionSections}
      </AccordionList>
    </div>
  );
}
