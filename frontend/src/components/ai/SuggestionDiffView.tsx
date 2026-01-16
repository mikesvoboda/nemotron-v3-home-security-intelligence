/**
 * SuggestionDiffView - GitHub-style diff view for prompt suggestions
 *
 * Displays a diff showing what will change when a suggestion is applied.
 * Features:
 * - Green background for additions
 * - Red background for removals
 * - Gray background for context lines
 * - Line numbers in left gutter
 * - Monospace font for code-like appearance
 * - Section indicator showing affected area
 */

import { Card } from '@tremor/react';
import { clsx } from 'clsx';
import { GitBranch, Info } from 'lucide-react';

import type { EnrichedSuggestion } from '../../services/api';

/**
 * Represents a single line in the diff view.
 * Exported for use by other modules that need to build diff data.
 */
export interface DiffLine {
  /** The type of diff line */
  type: 'unchanged' | 'added' | 'removed' | 'context';
  /** The content of the line */
  content: string;
  /** Optional line number */
  lineNumber?: number;
}

export interface SuggestionDiffViewProps {
  /** The original prompt text before changes */
  originalPrompt: string;
  /** The enriched suggestion being applied */
  suggestion: EnrichedSuggestion;
  /** The diff lines to display */
  diff: DiffLine[];
  /** Additional CSS classes */
  className?: string;
}

/**
 * Get line styling based on diff type
 */
function getLineStyles(type: DiffLine['type']): {
  bgClass: string;
  textClass: string;
  prefix: string;
} {
  switch (type) {
    case 'added':
      return {
        bgClass: 'bg-green-900/30',
        textClass: 'text-green-300',
        prefix: '+',
      };
    case 'removed':
      return {
        bgClass: 'bg-red-900/30',
        textClass: 'text-red-300',
        prefix: '-',
      };
    case 'context':
      return {
        bgClass: 'bg-gray-800/30',
        textClass: 'text-gray-400',
        prefix: ' ',
      };
    case 'unchanged':
    default:
      return {
        bgClass: '',
        textClass: 'text-gray-300',
        prefix: ' ',
      };
  }
}

/**
 * Get ARIA label for a diff line
 */
function getLineAriaLabel(type: DiffLine['type'], content: string): string {
  switch (type) {
    case 'added':
      return `Line added: ${content}`;
    case 'removed':
      return `Line removed: ${content}`;
    case 'context':
      return `Context: ${content}`;
    default:
      return content;
  }
}

/**
 * SuggestionDiffView - GitHub-style diff display component
 */
export default function SuggestionDiffView({
  suggestion,
  diff,
  className,
}: SuggestionDiffViewProps) {
  const hasDiff = diff.length > 0;

  return (
    <Card
      className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
      data-testid="suggestion-diff-view"
    >
      {/* Header with suggestion text */}
      <div className="mb-4 rounded-lg border border-[#76B900]/30 bg-[#76B900]/10 p-3">
        <div className="flex items-start gap-2">
          <GitBranch className="mt-0.5 h-4 w-4 flex-shrink-0 text-[#76B900]" />
          <div>
            <span className="text-sm font-medium text-white">{suggestion.suggestion}</span>
            <div className="mt-1 flex items-center gap-2 text-xs text-gray-400">
              <span>Target: {suggestion.targetSection}</span>
              <span className="text-gray-600">|</span>
              <span className="capitalize">{suggestion.insertionPoint}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Diff display */}
      {hasDiff ? (
        <div
          role="region"
          aria-label="Code diff showing proposed changes"
          className="overflow-hidden rounded-lg border border-gray-700"
        >
          <div className="overflow-x-auto font-mono text-sm" data-testid="diff-code-block">
            {diff.map((line, index) => {
              const styles = getLineStyles(line.type);
              const testIdType = line.type === 'unchanged' ? 'unchanged' : line.type;
              const testId = `diff-line-${testIdType}-${index}`;

              return (
                <div
                  key={index}
                  className={clsx(
                    'flex items-stretch border-b border-gray-800 last:border-b-0',
                    styles.bgClass
                  )}
                  data-testid={testId}
                  aria-label={getLineAriaLabel(line.type, line.content)}
                >
                  {/* Line number gutter */}
                  <div className="flex w-12 flex-shrink-0 select-none items-center justify-center border-r border-gray-700 bg-black/20 text-xs text-gray-500">
                    {line.lineNumber !== undefined ? line.lineNumber : ''}
                  </div>

                  {/* Line prefix (+/-/space) */}
                  <div
                    className={clsx(
                      'flex w-6 flex-shrink-0 select-none items-center justify-center',
                      styles.textClass
                    )}
                  >
                    {styles.prefix}
                  </div>

                  {/* Line content */}
                  <div className={clsx('flex-1 whitespace-pre px-2 py-1', styles.textClass)}>
                    {line.content}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ) : (
        <div className="flex h-32 items-center justify-center rounded-lg border border-gray-700 bg-black/20">
          <div className="text-center">
            <Info className="mx-auto mb-2 h-6 w-6 text-gray-600" />
            <p className="text-sm text-gray-500">No changes to display</p>
          </div>
        </div>
      )}

      {/* Impact explanation (collapsed by default in full implementation) */}
      {suggestion.impactExplanation && (
        <div className="mt-4 rounded-lg border border-gray-700 bg-black/20 p-3">
          <p className="text-xs text-gray-400">
            <span className="font-medium text-gray-300">Why this matters: </span>
            {suggestion.impactExplanation}
          </p>
        </div>
      )}
    </Card>
  );
}
