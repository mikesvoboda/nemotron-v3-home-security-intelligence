import { describe, expect, it } from 'vitest';

import {
  calculateAverageConfidence,
  calculateMaxConfidence,
  filterDetectionsByConfidence,
  formatConfidencePercent,
  getConfidenceBgColorClass,
  getConfidenceBorderColorClass,
  getConfidenceColor,
  getConfidenceLabel,
  getConfidenceLevel,
  getConfidenceTextColorClass,
  sortDetectionsByConfidence,
} from './confidence';

describe('confidence utilities', () => {
  describe('getConfidenceLevel', () => {
    it('returns "low" for confidence < 0.7', () => {
      expect(getConfidenceLevel(0)).toBe('low');
      expect(getConfidenceLevel(0.5)).toBe('low');
      expect(getConfidenceLevel(0.69)).toBe('low');
    });

    it('returns "medium" for confidence 0.7-0.85', () => {
      expect(getConfidenceLevel(0.7)).toBe('medium');
      expect(getConfidenceLevel(0.75)).toBe('medium');
      expect(getConfidenceLevel(0.84)).toBe('medium');
    });

    it('returns "high" for confidence >= 0.85', () => {
      expect(getConfidenceLevel(0.85)).toBe('high');
      expect(getConfidenceLevel(0.9)).toBe('high');
      expect(getConfidenceLevel(1.0)).toBe('high');
    });

    it('throws error for confidence < 0', () => {
      expect(() => getConfidenceLevel(-0.1)).toThrow(
        'Confidence score must be between 0.0 and 1.0'
      );
    });

    it('throws error for confidence > 1', () => {
      expect(() => getConfidenceLevel(1.1)).toThrow('Confidence score must be between 0.0 and 1.0');
    });

    it('handles boundary values correctly', () => {
      expect(getConfidenceLevel(0.699)).toBe('low');
      expect(getConfidenceLevel(0.7)).toBe('medium');
      expect(getConfidenceLevel(0.849)).toBe('medium');
      expect(getConfidenceLevel(0.85)).toBe('high');
    });
  });

  describe('getConfidenceColor', () => {
    it('returns red color for low confidence', () => {
      expect(getConfidenceColor('low')).toBe('#E74856');
    });

    it('returns yellow color for medium confidence', () => {
      expect(getConfidenceColor('medium')).toBe('#FFB800');
    });

    it('returns green color for high confidence', () => {
      expect(getConfidenceColor('high')).toBe('#76B900');
    });
  });

  describe('getConfidenceTextColorClass', () => {
    it('returns red text class for low confidence', () => {
      expect(getConfidenceTextColorClass('low')).toBe('text-red-400');
    });

    it('returns yellow text class for medium confidence', () => {
      expect(getConfidenceTextColorClass('medium')).toBe('text-yellow-400');
    });

    it('returns green text class for high confidence', () => {
      expect(getConfidenceTextColorClass('high')).toBe('text-green-400');
    });
  });

  describe('getConfidenceBgColorClass', () => {
    it('returns red background class for low confidence', () => {
      expect(getConfidenceBgColorClass('low')).toBe('bg-red-500/20');
    });

    it('returns yellow background class for medium confidence', () => {
      expect(getConfidenceBgColorClass('medium')).toBe('bg-yellow-500/20');
    });

    it('returns green background class for high confidence', () => {
      expect(getConfidenceBgColorClass('high')).toBe('bg-green-500/20');
    });
  });

  describe('getConfidenceBorderColorClass', () => {
    it('returns red border class for low confidence', () => {
      expect(getConfidenceBorderColorClass('low')).toBe('border-red-500/40');
    });

    it('returns yellow border class for medium confidence', () => {
      expect(getConfidenceBorderColorClass('medium')).toBe('border-yellow-500/40');
    });

    it('returns green border class for high confidence', () => {
      expect(getConfidenceBorderColorClass('high')).toBe('border-green-500/40');
    });
  });

  describe('getConfidenceLabel', () => {
    it('returns "Low Confidence" for low level', () => {
      expect(getConfidenceLabel('low')).toBe('Low Confidence');
    });

    it('returns "Medium Confidence" for medium level', () => {
      expect(getConfidenceLabel('medium')).toBe('Medium Confidence');
    });

    it('returns "High Confidence" for high level', () => {
      expect(getConfidenceLabel('high')).toBe('High Confidence');
    });
  });

  describe('formatConfidencePercent', () => {
    it('formats 0.95 as "95%"', () => {
      expect(formatConfidencePercent(0.95)).toBe('95%');
    });

    it('formats 0.5 as "50%"', () => {
      expect(formatConfidencePercent(0.5)).toBe('50%');
    });

    it('formats 1.0 as "100%"', () => {
      expect(formatConfidencePercent(1.0)).toBe('100%');
    });

    it('formats 0 as "0%"', () => {
      expect(formatConfidencePercent(0)).toBe('0%');
    });

    it('rounds to nearest integer', () => {
      expect(formatConfidencePercent(0.956)).toBe('96%');
      expect(formatConfidencePercent(0.874)).toBe('87%');
      expect(formatConfidencePercent(0.255)).toBe('26%');
    });
  });

  describe('calculateAverageConfidence', () => {
    it('returns null for empty array', () => {
      expect(calculateAverageConfidence([])).toBeNull();
    });

    it('returns the confidence for single detection', () => {
      expect(calculateAverageConfidence([{ confidence: 0.9 }])).toBe(0.9);
    });

    it('calculates average correctly for multiple detections', () => {
      const detections = [{ confidence: 0.8 }, { confidence: 0.9 }, { confidence: 1.0 }];
      expect(calculateAverageConfidence(detections)).toBe(0.9);
    });

    it('handles decimal values correctly', () => {
      const detections = [{ confidence: 0.75 }, { confidence: 0.85 }];
      expect(calculateAverageConfidence(detections)).toBe(0.8);
    });
  });

  describe('calculateMaxConfidence', () => {
    it('returns null for empty array', () => {
      expect(calculateMaxConfidence([])).toBeNull();
    });

    it('returns the confidence for single detection', () => {
      expect(calculateMaxConfidence([{ confidence: 0.9 }])).toBe(0.9);
    });

    it('returns the maximum confidence', () => {
      const detections = [{ confidence: 0.7 }, { confidence: 0.95 }, { confidence: 0.85 }];
      expect(calculateMaxConfidence(detections)).toBe(0.95);
    });

    it('handles equal confidences', () => {
      const detections = [{ confidence: 0.8 }, { confidence: 0.8 }];
      expect(calculateMaxConfidence(detections)).toBe(0.8);
    });
  });

  describe('sortDetectionsByConfidence', () => {
    it('returns empty array for empty input', () => {
      expect(sortDetectionsByConfidence([])).toEqual([]);
    });

    it('returns same array for single detection', () => {
      const detections = [{ label: 'person', confidence: 0.9 }];
      expect(sortDetectionsByConfidence(detections)).toEqual(detections);
    });

    it('sorts detections by confidence descending', () => {
      const detections = [
        { label: 'car', confidence: 0.7 },
        { label: 'person', confidence: 0.95 },
        { label: 'dog', confidence: 0.85 },
      ];
      const sorted = sortDetectionsByConfidence(detections);
      expect(sorted[0].confidence).toBe(0.95);
      expect(sorted[1].confidence).toBe(0.85);
      expect(sorted[2].confidence).toBe(0.7);
    });

    it('preserves original array', () => {
      const detections = [
        { label: 'car', confidence: 0.7 },
        { label: 'person', confidence: 0.95 },
      ];
      sortDetectionsByConfidence(detections);
      expect(detections[0].confidence).toBe(0.7);
    });

    it('handles equal confidences stably', () => {
      const detections = [
        { label: 'a', confidence: 0.9 },
        { label: 'b', confidence: 0.9 },
      ];
      const sorted = sortDetectionsByConfidence(detections);
      expect(sorted.length).toBe(2);
      expect(sorted[0].confidence).toBe(0.9);
      expect(sorted[1].confidence).toBe(0.9);
    });
  });

  describe('filterDetectionsByConfidence', () => {
    it('returns empty array for empty input', () => {
      expect(filterDetectionsByConfidence([], 0.5)).toEqual([]);
    });

    it('filters out detections below threshold', () => {
      const detections = [
        { label: 'car', confidence: 0.7 },
        { label: 'person', confidence: 0.95 },
        { label: 'dog', confidence: 0.6 },
      ];
      const filtered = filterDetectionsByConfidence(detections, 0.85);
      expect(filtered.length).toBe(1);
      expect(filtered[0].label).toBe('person');
    });

    it('includes detections at threshold', () => {
      const detections = [
        { label: 'car', confidence: 0.85 },
        { label: 'person', confidence: 0.84 },
      ];
      const filtered = filterDetectionsByConfidence(detections, 0.85);
      expect(filtered.length).toBe(1);
      expect(filtered[0].label).toBe('car');
    });

    it('returns all detections when threshold is 0', () => {
      const detections = [
        { label: 'car', confidence: 0.1 },
        { label: 'person', confidence: 0.5 },
      ];
      const filtered = filterDetectionsByConfidence(detections, 0);
      expect(filtered.length).toBe(2);
    });

    it('returns empty array when threshold is 1 and no perfect detections', () => {
      const detections = [
        { label: 'car', confidence: 0.99 },
        { label: 'person', confidence: 0.95 },
      ];
      const filtered = filterDetectionsByConfidence(detections, 1);
      expect(filtered.length).toBe(0);
    });

    it('preserves original array', () => {
      const detections = [
        { label: 'car', confidence: 0.7 },
        { label: 'person', confidence: 0.95 },
      ];
      filterDetectionsByConfidence(detections, 0.85);
      expect(detections.length).toBe(2);
    });
  });
});
