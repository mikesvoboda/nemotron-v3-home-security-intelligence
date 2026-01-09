/**
 * EnrichmentPanel - Displays AI enrichment data for detections
 *
 * Shows enrichment data in collapsible accordion sections, including:
 * - Vehicle classification (type, color, damage, commercial status)
 * - Pet identification (type, breed)
 * - Person attributes (clothing, action, carrying, suspicious/service indicators)
 * - License plate OCR results
 * - Weather conditions
 * - Image quality assessment
 */

import { Accordion, AccordionHeader, AccordionBody, AccordionList } from '@tremor/react';
import { clsx } from 'clsx';
import {
  Car,
  Dog,
  User,
  CreditCard,
  Cloud,
  ImageIcon,
  AlertTriangle,
  Briefcase,
  Package,
} from 'lucide-react';

import {
  formatConfidencePercent,
  getConfidenceBgColorClass,
  getConfidenceBorderColorClass,
  getConfidenceLevel,
  getConfidenceTextColorClass,
} from '../../utils/confidence';

import type { EnrichmentData } from '../../types/enrichment';
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
function FlagBadge({ label, variant = 'default' }: { label: string; variant?: 'warning' | 'info' | 'default' }) {
  const variantClasses = {
    warning: 'bg-yellow-500/20 border-yellow-500/40 text-yellow-400',
    info: 'bg-blue-500/20 border-blue-500/40 text-blue-400',
    default: 'bg-gray-500/20 border-gray-500/40 text-gray-400',
  };

  return (
    <span className={clsx('inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium', variantClasses[variant])}>
      {variant === 'warning' && <AlertTriangle className="h-3 w-3" />}
      {variant === 'info' && <Briefcase className="h-3 w-3" />}
      {label}
    </span>
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
    data.license_plate ||
    data.weather ||
    data.image_quality
  );
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
