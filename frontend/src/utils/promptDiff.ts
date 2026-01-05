/**
 * Prompt Diff Utilities
 *
 * Functions for generating diffs and applying suggestions to prompts.
 * Used by the PromptPlayground to show preview changes before applying.
 *
 * @see docs/plans/2026-01-05-prompt-playground-apply-suggestion-design.md
 */

import type { EnrichedSuggestion } from '../services/api';

// ============================================================================
// Types
// ============================================================================

/**
 * Represents a single line in a diff view.
 */
export interface DiffLine {
  /** The type of change for this line */
  type: 'unchanged' | 'added' | 'removed' | 'context';
  /** The text content of the line */
  content: string;
  /** Line number (1-indexed) from the original or modified file */
  lineNumber?: number;
}

/**
 * Result of applying a suggestion to a prompt.
 */
export interface InsertionResult {
  /** The modified prompt text */
  modifiedPrompt: string;
  /** The character index where the insertion was made */
  insertionIndex: number;
  /** How the insertion was performed */
  insertionType: 'section_end' | 'after_variable' | 'fallback';
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Escape special regex characters in a string.
 */
function escapeRegExp(string: string): string {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * Find section boundaries in a prompt.
 * @param prompt - The prompt text
 * @param targetSection - The section header to find (without ##)
 * @returns Start/end indices and whether section was found
 */
function findSectionBoundaries(
  prompt: string,
  targetSection: string
): { start: number; end: number; found: boolean } {
  // Match section header (## Section Name)
  const sectionPattern = new RegExp(`^##\\s*${escapeRegExp(targetSection)}\\s*$`, 'im');
  const match = prompt.match(sectionPattern);

  if (!match || match.index === undefined) {
    return { start: -1, end: -1, found: false };
  }

  const sectionStart = match.index;

  // Find the end of this section (next ## header or end of content)
  const afterHeader = sectionStart + match[0].length;
  const nextSectionPattern = /^##\s/m;
  const restOfPrompt = prompt.slice(afterHeader);
  const nextSectionMatch = restOfPrompt.match(nextSectionPattern);

  let sectionEnd: number;
  if (nextSectionMatch && nextSectionMatch.index !== undefined) {
    sectionEnd = afterHeader + nextSectionMatch.index;
  } else {
    sectionEnd = prompt.length;
  }

  return { start: sectionStart, end: sectionEnd, found: true };
}

/**
 * Generate the line to insert for a suggestion.
 */
function generateInsertionLine(suggestion: EnrichedSuggestion): string {
  return `${suggestion.proposedLabel} ${suggestion.proposedVariable}`;
}

/**
 * Compute a simple line-by-line diff using longest common subsequence.
 * Optimized for speed with typical prompt sizes.
 */
function computeLineDiff(
  originalLines: string[],
  modifiedLines: string[]
): Array<{ type: 'unchanged' | 'added' | 'removed'; line: string; origIdx?: number; modIdx?: number }> {
  const result: Array<{
    type: 'unchanged' | 'added' | 'removed';
    line: string;
    origIdx?: number;
    modIdx?: number;
  }> = [];

  // Use a simple diff algorithm (Myers' algorithm simplified)
  let i = 0;
  let j = 0;

  while (i < originalLines.length || j < modifiedLines.length) {
    if (i >= originalLines.length) {
      // All remaining lines are additions
      result.push({ type: 'added', line: modifiedLines[j], modIdx: j });
      j++;
    } else if (j >= modifiedLines.length) {
      // All remaining lines are removals
      result.push({ type: 'removed', line: originalLines[i], origIdx: i });
      i++;
    } else if (originalLines[i] === modifiedLines[j]) {
      // Lines match
      result.push({ type: 'unchanged', line: originalLines[i], origIdx: i, modIdx: j });
      i++;
      j++;
    } else {
      // Lines differ - look ahead to find best alignment
      // Check if current original line appears later in modified
      const lookAheadMod = modifiedLines.slice(j, j + 5).indexOf(originalLines[i]);
      // Check if current modified line appears later in original
      const lookAheadOrig = originalLines.slice(i, i + 5).indexOf(modifiedLines[j]);

      if (lookAheadMod !== -1 && (lookAheadOrig === -1 || lookAheadMod <= lookAheadOrig)) {
        // Original line found in modified - these are additions before it
        for (let k = 0; k < lookAheadMod; k++) {
          result.push({ type: 'added', line: modifiedLines[j + k], modIdx: j + k });
        }
        j += lookAheadMod;
      } else if (lookAheadOrig !== -1) {
        // Modified line found in original - these are removals before it
        for (let k = 0; k < lookAheadOrig; k++) {
          result.push({ type: 'removed', line: originalLines[i + k], origIdx: i + k });
        }
        i += lookAheadOrig;
      } else {
        // No match found nearby - treat as removal then addition
        result.push({ type: 'removed', line: originalLines[i], origIdx: i });
        result.push({ type: 'added', line: modifiedLines[j], modIdx: j });
        i++;
        j++;
      }
    }
  }

  return result;
}

// ============================================================================
// Main Functions
// ============================================================================

/**
 * Apply a suggestion to a prompt and return the modified version.
 *
 * Algorithm:
 * 1. Parse suggestion's targetSection (e.g., "Camera & Time Context")
 * 2. Find section header in prompt using regex: ## {targetSection}
 * 3. If found: Insert at appropriate position based on insertionPoint
 * 4. If not found: Append comment at end with fallback
 *
 * @param originalPrompt - The original prompt text
 * @param suggestion - The enriched suggestion to apply
 * @returns InsertionResult containing the modified prompt and insertion details
 */
export function applySuggestion(
  originalPrompt: string,
  suggestion: EnrichedSuggestion
): InsertionResult {
  const insertionLine = generateInsertionLine(suggestion);
  const { start, end, found } = findSectionBoundaries(originalPrompt, suggestion.targetSection);

  if (!found) {
    // Fallback: append as comment at end
    const fallbackComment = `\n/* Suggestion: ${suggestion.suggestion} */\n${insertionLine}`;
    return {
      modifiedPrompt: originalPrompt + fallbackComment,
      insertionIndex: originalPrompt.length,
      insertionType: 'fallback',
    };
  }

  // Section found - determine where to insert
  if (suggestion.insertionPoint === 'prepend') {
    // Find the line after the header
    const headerEndIdx = originalPrompt.indexOf('\n', start);
    if (headerEndIdx === -1) {
      // Section header is at the very end
      return {
        modifiedPrompt: originalPrompt + '\n' + insertionLine,
        insertionIndex: originalPrompt.length,
        insertionType: 'section_end',
      };
    }

    // Insert right after the header
    const insertionIndex = headerEndIdx + 1;
    const modifiedPrompt =
      originalPrompt.slice(0, insertionIndex) + insertionLine + '\n' + originalPrompt.slice(insertionIndex);

    return {
      modifiedPrompt,
      insertionIndex,
      insertionType: 'section_end',
    };
  }

  // Default: append at end of section
  let insertionIndex: number;
  if (end === originalPrompt.length) {
    // Section ends at prompt end
    insertionIndex = end;
    const needsNewline = originalPrompt.length > 0 && !originalPrompt.endsWith('\n');
    const modifiedPrompt = originalPrompt + (needsNewline ? '\n' : '') + insertionLine;
    return {
      modifiedPrompt,
      insertionIndex,
      insertionType: 'section_end',
    };
  } else {
    // Section ends before next section
    // Find position just before the next section header
    insertionIndex = end;
    // Ensure we have a newline before the new content
    const charBefore = originalPrompt[insertionIndex - 1];
    const prefix = charBefore === '\n' ? '' : '\n';
    const suffix = '\n';

    const modifiedPrompt =
      originalPrompt.slice(0, insertionIndex) + prefix + insertionLine + suffix + originalPrompt.slice(insertionIndex);

    return {
      modifiedPrompt,
      insertionIndex,
      insertionType: 'section_end',
    };
  }
}

/**
 * Generate a visual diff between original and modified prompts.
 * Shows the affected section with context lines around changes.
 *
 * @param originalPrompt - The original prompt text
 * @param modifiedPrompt - The modified prompt text
 * @param contextLines - Number of context lines to show around changes (default: 3)
 * @returns Array of DiffLine objects for rendering
 */
export function generateDiff(originalPrompt: string, modifiedPrompt: string, contextLines: number = 3): DiffLine[] {
  const originalLines = originalPrompt.split('\n');
  const modifiedLines = modifiedPrompt.split('\n');

  // Handle empty strings
  if (originalPrompt === '' && modifiedPrompt === '') {
    return [];
  }

  // Compute line-by-line diff
  const rawDiff = computeLineDiff(originalLines, modifiedLines);

  // Find indices of changed lines
  const changedIndices: number[] = [];
  rawDiff.forEach((item, idx) => {
    if (item.type !== 'unchanged') {
      changedIndices.push(idx);
    }
  });

  // If no changes, return empty array
  if (changedIndices.length === 0) {
    return [];
  }

  // Determine which lines to include based on context
  const includedIndices = new Set<number>();
  changedIndices.forEach((idx) => {
    for (let i = Math.max(0, idx - contextLines); i <= Math.min(rawDiff.length - 1, idx + contextLines); i++) {
      includedIndices.add(i);
    }
  });

  // Build the final diff output
  const result: DiffLine[] = [];
  let origLineNum = 1;
  let modLineNum = 1;

  rawDiff.forEach((item, idx) => {
    if (!includedIndices.has(idx)) {
      // Track line numbers even for excluded lines
      if (item.type === 'unchanged') {
        origLineNum++;
        modLineNum++;
      } else if (item.type === 'removed') {
        origLineNum++;
      } else if (item.type === 'added') {
        modLineNum++;
      }
      return;
    }

    if (item.type === 'unchanged') {
      result.push({
        type: 'unchanged',
        content: item.line,
        lineNumber: origLineNum,
      });
      origLineNum++;
      modLineNum++;
    } else if (item.type === 'removed') {
      result.push({
        type: 'removed',
        content: item.line,
        lineNumber: origLineNum,
      });
      origLineNum++;
    } else if (item.type === 'added') {
      result.push({
        type: 'added',
        content: item.line,
        lineNumber: modLineNum,
      });
      modLineNum++;
    }
  });

  return result;
}

/**
 * Check if a suggestion has already been applied to a prompt.
 *
 * Checks for:
 * 1. The proposed variable (e.g., {time_since_last_event})
 * 2. The proposed label (case-insensitive)
 *
 * @param prompt - The prompt to check
 * @param suggestion - The suggestion to check for
 * @returns True if the suggestion appears to already be applied
 */
export function isSuggestionApplied(prompt: string, suggestion: EnrichedSuggestion): boolean {
  // Check if the proposed variable is already in the prompt
  if (prompt.includes(suggestion.proposedVariable)) {
    return true;
  }

  // Check for the label (case-insensitive)
  const labelPattern = new RegExp(escapeRegExp(suggestion.proposedLabel), 'i');
  if (labelPattern.test(prompt)) {
    return true;
  }

  return false;
}
