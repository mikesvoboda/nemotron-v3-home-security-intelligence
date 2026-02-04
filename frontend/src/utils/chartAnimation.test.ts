/**
 * Tests for Chart Animation Utilities (NEM-5045)
 *
 * @module utils/chartAnimation.test
 */

import { describe, expect, it } from 'vitest';

import {
  shouldAnimateChart,
  getChartAnimationConfig,
  CHART_ANIMATION_THRESHOLD,
} from './chartAnimation';

describe('chartAnimation', () => {
  describe('CHART_ANIMATION_THRESHOLD', () => {
    it('should be set to 100', () => {
      expect(CHART_ANIMATION_THRESHOLD).toBe(100);
    });
  });

  describe('shouldAnimateChart', () => {
    it('should return true for empty datasets', () => {
      expect(shouldAnimateChart(0)).toBe(true);
    });

    it('should return true for small datasets', () => {
      expect(shouldAnimateChart(1)).toBe(true);
      expect(shouldAnimateChart(10)).toBe(true);
      expect(shouldAnimateChart(50)).toBe(true);
    });

    it('should return true for datasets at the threshold', () => {
      expect(shouldAnimateChart(CHART_ANIMATION_THRESHOLD)).toBe(true);
      expect(shouldAnimateChart(100)).toBe(true);
    });

    it('should return false for datasets exceeding the threshold', () => {
      expect(shouldAnimateChart(CHART_ANIMATION_THRESHOLD + 1)).toBe(false);
      expect(shouldAnimateChart(101)).toBe(false);
      expect(shouldAnimateChart(200)).toBe(false);
      expect(shouldAnimateChart(1000)).toBe(false);
    });

    it('should return false for very large datasets', () => {
      expect(shouldAnimateChart(10000)).toBe(false);
      expect(shouldAnimateChart(100000)).toBe(false);
    });
  });

  describe('getChartAnimationConfig', () => {
    it('should return showAnimation: true for small datasets', () => {
      expect(getChartAnimationConfig(0)).toEqual({ showAnimation: true });
      expect(getChartAnimationConfig(50)).toEqual({ showAnimation: true });
      expect(getChartAnimationConfig(100)).toEqual({ showAnimation: true });
    });

    it('should return showAnimation: false for large datasets', () => {
      expect(getChartAnimationConfig(101)).toEqual({ showAnimation: false });
      expect(getChartAnimationConfig(500)).toEqual({ showAnimation: false });
      expect(getChartAnimationConfig(1000)).toEqual({ showAnimation: false });
    });

    it('should return an object that can be spread onto chart props', () => {
      const config = getChartAnimationConfig(50);
      expect(config).toHaveProperty('showAnimation');
      expect(typeof config.showAnimation).toBe('boolean');
    });
  });
});
