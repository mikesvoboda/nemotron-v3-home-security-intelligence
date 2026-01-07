import { Disclosure, Transition } from '@headlessui/react';
import { clsx } from 'clsx';
import { ChevronDown } from 'lucide-react';
import { Fragment, ReactNode } from 'react';

export interface CollapsibleSectionProps {
  /** Section title */
  title: ReactNode;
  /** Section icon (optional) */
  icon?: ReactNode;
  /** Section content */
  children: ReactNode;
  /** Whether the section should be expanded by default */
  defaultOpen?: boolean;
  /** Whether the section is currently expanded (controlled mode) */
  isOpen?: boolean;
  /** Callback when the section is toggled (controlled mode) */
  onToggle?: (isOpen: boolean) => void;
  /** Optional summary badge (e.g., "6/7 Healthy") */
  summary?: ReactNode;
  /** Optional alert badge (shown when there are issues) */
  alertBadge?: ReactNode;
  /** Additional CSS classes */
  className?: string;
  /** Test ID */
  'data-testid'?: string;
}

/**
 * CollapsibleSection - Reusable collapsible section component using Headless UI Disclosure
 *
 * Features:
 * - Smooth expand/collapse animations
 * - Optional controlled or uncontrolled mode
 * - Summary badge support
 * - Alert badge support
 * - Consistent styling across all sections
 */
export default function CollapsibleSection({
  title,
  icon,
  children,
  defaultOpen = false,
  isOpen: controlledIsOpen,
  onToggle,
  summary,
  alertBadge,
  className,
  'data-testid': testId,
}: CollapsibleSectionProps) {
  // Use controlled mode if isOpen is provided, otherwise uncontrolled
  const isControlled = controlledIsOpen !== undefined;

  return (
    <Disclosure defaultOpen={!isControlled ? defaultOpen : undefined} as="div" className={className}>
      {({ open }) => {
        // In controlled mode, use the controlled isOpen value
        const isExpanded = isControlled ? controlledIsOpen : open;

        return (
          <>
            <Disclosure.Button
              className="flex w-full items-center justify-between rounded-t-lg bg-[#1A1A1A] p-4 text-left transition-colors hover:bg-[#232323] focus:outline-none focus:ring-2 focus:ring-[#76B900]/50"
              onClick={
                isControlled
                  ? (e) => {
                      e.preventDefault();
                      onToggle?.(!controlledIsOpen);
                    }
                  : undefined
              }
              data-testid={testId ? `${testId}-toggle` : undefined}
              aria-expanded={isExpanded}
            >
              <div className="flex items-center gap-3">
                {icon && <span className="flex-shrink-0">{icon}</span>}
                <span className="text-lg font-semibold text-white">{title}</span>
                {alertBadge && <span className="flex-shrink-0">{alertBadge}</span>}
              </div>

              <div className="flex items-center gap-2">
                {summary && <span className="mr-2 text-sm text-gray-400">{summary}</span>}
                <ChevronDown
                  className={clsx(
                    'h-5 w-5 text-gray-400 transition-transform duration-200',
                    isExpanded ? 'rotate-180' : ''
                  )}
                  aria-hidden="true"
                />
              </div>
            </Disclosure.Button>

            <Transition
              as={Fragment}
              show={isExpanded}
              enter="transition duration-200 ease-out"
              enterFrom="transform opacity-0 -translate-y-2"
              enterTo="transform opacity-100 translate-y-0"
              leave="transition duration-150 ease-in"
              leaveFrom="transform opacity-100 translate-y-0"
              leaveTo="transform opacity-0 -translate-y-2"
            >
              <Disclosure.Panel static className="bg-[#1A1A1A] p-4 rounded-b-lg border-t border-gray-800">
                {children}
              </Disclosure.Panel>
            </Transition>
          </>
        );
      }}
    </Disclosure>
  );
}
