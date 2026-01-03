import { Disclosure, Transition } from '@headlessui/react';
import { clsx } from 'clsx';
import {
  Car,
  ChevronDown,
  CloudSun,
  FileImage,
  PawPrint,
  Shirt,
  RectangleHorizontal,
} from 'lucide-react';
import { useMemo } from 'react';

import type { EnrichmentData } from '../../types/generated';

export interface EnrichmentPanelProps {
  enrichment?: EnrichmentData | null;
  className?: string;
}

/**
 * Format confidence score as percentage string
 */
function formatConfidence(confidence: number): string {
  return `${Math.round(confidence * 100)}%`;
}

/**
 * Get color class based on confidence level
 */
function getConfidenceColorClass(confidence: number): string {
  if (confidence >= 0.85) return 'text-green-400';
  if (confidence >= 0.7) return 'text-yellow-400';
  return 'text-red-400';
}

/**
 * Get background color class based on confidence level
 */
function getConfidenceBgClass(confidence: number): string {
  if (confidence >= 0.85) return 'bg-green-500';
  if (confidence >= 0.7) return 'bg-yellow-500';
  return 'bg-red-500';
}

/**
 * Confidence bar component
 */
function ConfidenceBar({
  confidence,
  label,
}: {
  confidence: number;
  label?: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-gray-700">
        <div
          className={clsx(
            'h-full rounded-full transition-all duration-300',
            getConfidenceBgClass(confidence)
          )}
          style={{ width: `${Math.round(confidence * 100)}%` }}
        />
      </div>
      <span className={clsx('min-w-[3rem] text-xs font-medium', getConfidenceColorClass(confidence))}>
        {label || formatConfidence(confidence)}
      </span>
    </div>
  );
}

/**
 * Enrichment section wrapper with disclosure/accordion behavior
 */
function EnrichmentSection({
  title,
  icon: Icon,
  children,
  defaultOpen = false,
}: {
  title: string;
  icon: React.ElementType;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  return (
    <Disclosure defaultOpen={defaultOpen}>
      {({ open }) => (
        <div className="overflow-hidden rounded-lg border border-gray-700 bg-black/20">
          <Disclosure.Button className="flex w-full items-center justify-between px-4 py-3 text-left transition-colors hover:bg-gray-800/50">
            <div className="flex items-center gap-2">
              <Icon className="h-4 w-4 text-[#76B900]" aria-hidden="true" />
              <span className="text-sm font-medium text-gray-200">{title}</span>
            </div>
            <ChevronDown
              className={clsx(
                'h-4 w-4 text-gray-400 transition-transform duration-200',
                open && 'rotate-180 transform'
              )}
              aria-hidden="true"
            />
          </Disclosure.Button>
          <Transition
            enter="transition duration-100 ease-out"
            enterFrom="transform scale-95 opacity-0"
            enterTo="transform scale-100 opacity-100"
            leave="transition duration-75 ease-out"
            leaveFrom="transform scale-100 opacity-100"
            leaveTo="transform scale-95 opacity-0"
          >
            <Disclosure.Panel className="border-t border-gray-700 bg-black/10 px-4 py-3">
              {children}
            </Disclosure.Panel>
          </Transition>
        </div>
      )}
    </Disclosure>
  );
}

/**
 * Label-value pair display
 */
function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between py-1">
      <span className="text-xs text-gray-400">{label}</span>
      <span className="text-sm text-gray-200">{value}</span>
    </div>
  );
}

/**
 * EnrichmentPanel component displays AI enrichment data for an event
 *
 * Displays accordion sections for:
 * - Vehicle classification
 * - Pet detection
 * - Person attributes
 * - License plate
 * - Weather condition
 * - Image quality
 */
export default function EnrichmentPanel({ enrichment, className }: EnrichmentPanelProps) {
  // Count available enrichment sections
  const sectionCount = useMemo(() => {
    if (!enrichment) return 0;
    let count = 0;
    if (enrichment.vehicle) count++;
    if (enrichment.pet) count++;
    if (enrichment.person) count++;
    if (enrichment.license_plate) count++;
    if (enrichment.weather) count++;
    if (enrichment.image_quality) count++;
    return count;
  }, [enrichment]);

  // No enrichment data available
  if (!enrichment || sectionCount === 0) {
    return (
      <div
        className={clsx(
          'rounded-lg border border-gray-800 bg-black/20 p-4 text-center',
          className
        )}
      >
        <p className="text-sm text-gray-500">No enrichment data available for this event.</p>
      </div>
    );
  }

  return (
    <div className={clsx('space-y-3', className)} data-testid="enrichment-panel">
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-400">
        AI Enrichment ({sectionCount} {sectionCount === 1 ? 'type' : 'types'})
      </h3>

      {/* Vehicle Classification */}
      {enrichment.vehicle && (
        <EnrichmentSection title="Vehicle" icon={Car} defaultOpen>
          <div className="space-y-2">
            <DetailRow label="Type" value={enrichment.vehicle.type} />
            <DetailRow label="Color" value={enrichment.vehicle.color} />
            {enrichment.vehicle.damage && enrichment.vehicle.damage.length > 0 && (
              <DetailRow
                label="Damage"
                value={
                  <div className="flex flex-wrap gap-1">
                    {enrichment.vehicle.damage.map((d, i) => (
                      <span
                        key={i}
                        className="rounded-md bg-red-500/20 px-2 py-0.5 text-xs text-red-400"
                      >
                        {d}
                      </span>
                    ))}
                  </div>
                }
              />
            )}
            <div className="pt-2">
              <span className="text-xs text-gray-400">Confidence</span>
              <ConfidenceBar confidence={enrichment.vehicle.confidence} />
            </div>
          </div>
        </EnrichmentSection>
      )}

      {/* Pet Detection */}
      {enrichment.pet && (
        <EnrichmentSection title="Pet" icon={PawPrint}>
          <div className="space-y-2">
            <DetailRow label="Type" value={enrichment.pet.type} />
            {enrichment.pet.breed && <DetailRow label="Breed" value={enrichment.pet.breed} />}
            <div className="pt-2">
              <span className="text-xs text-gray-400">Confidence</span>
              <ConfidenceBar confidence={enrichment.pet.confidence} />
            </div>
          </div>
        </EnrichmentSection>
      )}

      {/* Person Attributes */}
      {enrichment.person && (
        <EnrichmentSection title="Person Attributes" icon={Shirt}>
          <div className="space-y-2">
            <DetailRow label="Clothing" value={enrichment.person.clothing} />
            {enrichment.person.action && (
              <DetailRow label="Action" value={enrichment.person.action} />
            )}
            {enrichment.person.carrying && (
              <DetailRow label="Carrying" value={enrichment.person.carrying} />
            )}
            <div className="pt-2">
              <span className="text-xs text-gray-400">Confidence</span>
              <ConfidenceBar confidence={enrichment.person.confidence} />
            </div>
          </div>
        </EnrichmentSection>
      )}

      {/* License Plate */}
      {enrichment.license_plate && (
        <EnrichmentSection title="License Plate" icon={RectangleHorizontal}>
          <div className="space-y-2">
            <DetailRow
              label="Plate"
              value={
                <span className="rounded bg-gray-700 px-2 py-0.5 font-mono text-sm tracking-wider">
                  {enrichment.license_plate.text}
                </span>
              }
            />
            <div className="pt-2">
              <span className="text-xs text-gray-400">Confidence</span>
              <ConfidenceBar confidence={enrichment.license_plate.confidence} />
            </div>
          </div>
        </EnrichmentSection>
      )}

      {/* Weather Condition */}
      {enrichment.weather && (
        <EnrichmentSection title="Weather" icon={CloudSun}>
          <div className="space-y-2">
            <DetailRow label="Condition" value={enrichment.weather.condition} />
            <div className="pt-2">
              <span className="text-xs text-gray-400">Confidence</span>
              <ConfidenceBar confidence={enrichment.weather.confidence} />
            </div>
          </div>
        </EnrichmentSection>
      )}

      {/* Image Quality */}
      {enrichment.image_quality && (
        <EnrichmentSection title="Image Quality" icon={FileImage}>
          <div className="space-y-2">
            <DetailRow
              label="Quality Score"
              value={
                <span
                  className={clsx(
                    'font-semibold',
                    enrichment.image_quality.score >= 0.8
                      ? 'text-green-400'
                      : enrichment.image_quality.score >= 0.5
                        ? 'text-yellow-400'
                        : 'text-red-400'
                  )}
                >
                  {Math.round(enrichment.image_quality.score * 100)}%
                </span>
              }
            />
            {enrichment.image_quality.issues.length > 0 && (
              <div className="pt-2">
                <span className="text-xs text-gray-400">Issues</span>
                <ul className="mt-1 space-y-1">
                  {enrichment.image_quality.issues.map((issue, i) => (
                    <li key={i} className="text-xs text-yellow-400">
                      - {issue}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </EnrichmentSection>
      )}
    </div>
  );
}
