import { describe, expect, it } from 'vitest';

import { applySuggestion, generateDiff, isSuggestionApplied } from './promptDiff';

import type { EnrichedSuggestion } from '../services/api';

/**
 * Factory function to create test EnrichedSuggestion objects.
 */
function createSuggestion(overrides: Partial<EnrichedSuggestion> = {}): EnrichedSuggestion {
  return {
    category: 'missing_context',
    suggestion: 'Time since last detected motion or event',
    priority: 'high',
    frequency: 3,
    targetSection: 'Camera & Time Context',
    insertionPoint: 'append',
    proposedVariable: '{time_since_last_event}',
    proposedLabel: 'Time Since Last Event:',
    impactExplanation: 'Adding time-since-last-event helps the AI distinguish...',
    sourceEventIds: [142, 156, 189],
    ...overrides,
  };
}

describe('promptDiff utilities', () => {
  describe('applySuggestion', () => {
    const multiSectionPrompt = `## System Instructions
You are a security AI assistant.

## Camera & Time Context
Camera: {camera_name}
Time: {timestamp}
Day: {day_of_week}
Lighting: {time_of_day}

## Detection Context
Objects detected: {detected_objects}
Confidence: {confidence_score}

## Analysis Instructions
Analyze the scene and provide a risk assessment.`;

    it('inserts at section end when target section exists', () => {
      const suggestion = createSuggestion();
      const result = applySuggestion(multiSectionPrompt, suggestion);

      // Should insert after existing Camera & Time Context variables
      expect(result.modifiedPrompt).toContain('Time Since Last Event: {time_since_last_event}');
      expect(result.insertionType).toBe('section_end');

      // Verify insertion is in the right section (before Detection Context)
      const insertionPos = result.modifiedPrompt.indexOf('Time Since Last Event:');
      const detectionPos = result.modifiedPrompt.indexOf('## Detection Context');
      expect(insertionPos).toBeLessThan(detectionPos);
    });

    it('handles missing section with fallback', () => {
      const suggestion = createSuggestion({
        targetSection: 'Nonexistent Section',
      });
      const result = applySuggestion(multiSectionPrompt, suggestion);

      // Should append as comment at the end
      expect(result.modifiedPrompt).toContain('/* Suggestion:');
      expect(result.modifiedPrompt).toContain('Time since last detected motion or event');
      expect(result.insertionType).toBe('fallback');
    });

    it('preserves existing content', () => {
      const suggestion = createSuggestion();
      const result = applySuggestion(multiSectionPrompt, suggestion);

      // Original content should still be present
      expect(result.modifiedPrompt).toContain('## System Instructions');
      expect(result.modifiedPrompt).toContain('Camera: {camera_name}');
      expect(result.modifiedPrompt).toContain('Time: {timestamp}');
      expect(result.modifiedPrompt).toContain('## Detection Context');
      expect(result.modifiedPrompt).toContain('Objects detected: {detected_objects}');
      expect(result.modifiedPrompt).toContain('## Analysis Instructions');
    });

    it('handles prompt with no sections', () => {
      const simplePrompt = 'You are a helpful assistant. Analyze the image.';
      const suggestion = createSuggestion();
      const result = applySuggestion(simplePrompt, suggestion);

      // Should use fallback since no sections exist
      expect(result.insertionType).toBe('fallback');
      expect(result.modifiedPrompt).toContain('/* Suggestion:');
    });

    it('handles empty prompt', () => {
      const suggestion = createSuggestion();
      const result = applySuggestion('', suggestion);

      expect(result.insertionType).toBe('fallback');
      expect(result.modifiedPrompt).toContain('/* Suggestion:');
    });

    it('handles prepend insertion point', () => {
      const suggestion = createSuggestion({
        insertionPoint: 'prepend',
        targetSection: 'Camera & Time Context',
      });
      const result = applySuggestion(multiSectionPrompt, suggestion);

      // When prepending, the new variable should come before existing variables
      const insertionPos = result.modifiedPrompt.indexOf('Time Since Last Event:');
      const cameraPos = result.modifiedPrompt.indexOf('Camera: {camera_name}');

      // insertionPos should be before Camera line
      expect(insertionPos).toBeLessThan(cameraPos);
      expect(result.insertionType).toBe('section_end'); // Still marks as successful
    });

    it('handles section at end of prompt', () => {
      const promptEndingWithSection = `## Camera & Time Context
Camera: {camera_name}
Time: {timestamp}`;

      const suggestion = createSuggestion();
      const result = applySuggestion(promptEndingWithSection, suggestion);

      expect(result.modifiedPrompt).toContain('Time Since Last Event: {time_since_last_event}');
      expect(result.insertionType).toBe('section_end');
    });
  });

  describe('generateDiff', () => {
    it('shows additions with type added', () => {
      const original = 'Line 1\nLine 2\nLine 3';
      const modified = 'Line 1\nLine 2\nLine 2.5\nLine 3';

      const diff = generateDiff(original, modified);

      const addedLines = diff.filter((line) => line.type === 'added');
      expect(addedLines.length).toBeGreaterThan(0);
      expect(addedLines.some((line) => line.content.includes('Line 2.5'))).toBe(true);
    });

    it('includes context lines', () => {
      const original = 'Line 1\nLine 2\nLine 3\nLine 4\nLine 5';
      const modified = 'Line 1\nLine 2\nLine 3 modified\nLine 4\nLine 5';

      const diff = generateDiff(original, modified, 2);

      // Should have context lines around the change
      const contextLines = diff.filter(
        (line) => line.type === 'context' || line.type === 'unchanged'
      );
      expect(contextLines.length).toBeGreaterThan(0);
    });

    it('handles identical prompts', () => {
      const prompt = 'This is an identical prompt\nWith multiple lines';

      const diff = generateDiff(prompt, prompt);

      // No changes should be detected - all lines should be unchanged or context
      const addedLines = diff.filter((line) => line.type === 'added');
      const removedLines = diff.filter((line) => line.type === 'removed');
      expect(addedLines.length).toBe(0);
      expect(removedLines.length).toBe(0);
    });

    it('shows removals with type removed', () => {
      const original = 'Line 1\nLine 2\nLine 3';
      const modified = 'Line 1\nLine 3';

      const diff = generateDiff(original, modified);

      const removedLines = diff.filter((line) => line.type === 'removed');
      expect(removedLines.length).toBeGreaterThan(0);
      expect(removedLines.some((line) => line.content.includes('Line 2'))).toBe(true);
    });

    it('handles empty strings', () => {
      expect(() => generateDiff('', '')).not.toThrow();
      expect(() => generateDiff('', 'new content')).not.toThrow();
      expect(() => generateDiff('old content', '')).not.toThrow();
    });

    it('includes line numbers', () => {
      const original = 'Line 1\nLine 2\nLine 3';
      const modified = 'Line 1\nLine 2 modified\nLine 3';

      const diff = generateDiff(original, modified);

      // At least some lines should have line numbers
      const linesWithNumbers = diff.filter((line) => line.lineNumber !== undefined);
      expect(linesWithNumbers.length).toBeGreaterThan(0);
    });

    it('processes typical prompts in under 10ms', () => {
      // Create a realistic prompt with multiple sections
      const originalPrompt = Array.from(
        { length: 100 },
        (_, i) => `Line ${i}: Some content here`
      ).join('\n');
      const modifiedPrompt =
        originalPrompt.slice(0, originalPrompt.length / 2) +
        '\nNew line inserted here\n' +
        originalPrompt.slice(originalPrompt.length / 2);

      const start = performance.now();
      generateDiff(originalPrompt, modifiedPrompt);
      const elapsed = performance.now() - start;

      expect(elapsed).toBeLessThan(10);
    });
  });

  describe('isSuggestionApplied', () => {
    it('returns true when variable exists in prompt', () => {
      const prompt = `## Camera & Time Context
Camera: {camera_name}
Time: {timestamp}
Time Since Last Event: {time_since_last_event}`;

      const suggestion = createSuggestion();

      expect(isSuggestionApplied(prompt, suggestion)).toBe(true);
    });

    it('returns false for new suggestion', () => {
      const prompt = `## Camera & Time Context
Camera: {camera_name}
Time: {timestamp}`;

      const suggestion = createSuggestion();

      expect(isSuggestionApplied(prompt, suggestion)).toBe(false);
    });

    it('detects partial matches (variable without label)', () => {
      const prompt = `## Camera & Time Context
Camera: {camera_name}
{time_since_last_event}`;

      const suggestion = createSuggestion();

      // Should detect the variable even without the label
      expect(isSuggestionApplied(prompt, suggestion)).toBe(true);
    });

    it('handles empty prompt', () => {
      const suggestion = createSuggestion();

      expect(isSuggestionApplied('', suggestion)).toBe(false);
    });

    it('is case insensitive for label matching', () => {
      const prompt = `## Camera & Time Context
time since last event: {time_since_last_event}`;

      const suggestion = createSuggestion();

      expect(isSuggestionApplied(prompt, suggestion)).toBe(true);
    });
  });
});
