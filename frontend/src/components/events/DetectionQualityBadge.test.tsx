import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import DetectionQualityBadge, { getQualityTier } from './DetectionQualityBadge';

describe('DetectionQualityBadge', () => {
  describe('getQualityTier', () => {
    it('returns EXCELLENT for confidence >= 0.9', () => {
      expect(getQualityTier(0.9)).toBe('EXCELLENT');
      expect(getQualityTier(0.95)).toBe('EXCELLENT');
      expect(getQualityTier(1.0)).toBe('EXCELLENT');
    });

    it('returns GOOD for confidence >= 0.75 and < 0.9', () => {
      expect(getQualityTier(0.75)).toBe('GOOD');
      expect(getQualityTier(0.85)).toBe('GOOD');
      expect(getQualityTier(0.89)).toBe('GOOD');
    });

    it('returns MODERATE for confidence >= 0.5 and < 0.75', () => {
      expect(getQualityTier(0.5)).toBe('MODERATE');
      expect(getQualityTier(0.6)).toBe('MODERATE');
      expect(getQualityTier(0.74)).toBe('MODERATE');
    });

    it('returns MARGINAL for confidence < 0.5', () => {
      expect(getQualityTier(0.49)).toBe('MARGINAL');
      expect(getQualityTier(0.3)).toBe('MARGINAL');
      expect(getQualityTier(0.0)).toBe('MARGINAL');
    });
  });

  describe('rendering', () => {
    it('renders EXCELLENT badge for high confidence', () => {
      render(<DetectionQualityBadge confidence={0.95} />);
      const badge = screen.getByTestId('detection-quality-badge');
      expect(badge).toBeInTheDocument();
      expect(badge).toHaveAttribute('data-tier', 'EXCELLENT');
      expect(badge).toHaveTextContent('EXCELLENT');
    });

    it('renders GOOD badge for good confidence', () => {
      render(<DetectionQualityBadge confidence={0.82} />);
      const badge = screen.getByTestId('detection-quality-badge');
      expect(badge).toHaveAttribute('data-tier', 'GOOD');
      expect(badge).toHaveTextContent('GOOD');
    });

    it('renders MODERATE badge for moderate confidence', () => {
      render(<DetectionQualityBadge confidence={0.6} />);
      const badge = screen.getByTestId('detection-quality-badge');
      expect(badge).toHaveAttribute('data-tier', 'MODERATE');
      expect(badge).toHaveTextContent('MODERATE');
    });

    it('renders MARGINAL badge for low confidence', () => {
      render(<DetectionQualityBadge confidence={0.3} />);
      const badge = screen.getByTestId('detection-quality-badge');
      expect(badge).toHaveAttribute('data-tier', 'MARGINAL');
      expect(badge).toHaveTextContent('MARGINAL');
    });

    it('shows confidence percentage in title', () => {
      render(<DetectionQualityBadge confidence={0.82} />);
      const badge = screen.getByTestId('detection-quality-badge');
      expect(badge).toHaveAttribute('title', 'Quality: GOOD (82%)');
    });

    it('applies custom className', () => {
      render(<DetectionQualityBadge confidence={0.9} className="my-custom-class" />);
      const badge = screen.getByTestId('detection-quality-badge');
      expect(badge).toHaveClass('my-custom-class');
    });

    it('renders with md size', () => {
      render(<DetectionQualityBadge confidence={0.9} size="md" />);
      const badge = screen.getByTestId('detection-quality-badge');
      expect(badge).toBeInTheDocument();
    });

    it('renders green styles for EXCELLENT tier', () => {
      render(<DetectionQualityBadge confidence={0.95} />);
      const badge = screen.getByTestId('detection-quality-badge');
      expect(badge.className).toContain('green');
    });

    it('renders blue styles for GOOD tier', () => {
      render(<DetectionQualityBadge confidence={0.8} />);
      const badge = screen.getByTestId('detection-quality-badge');
      expect(badge.className).toContain('blue');
    });

    it('renders yellow styles for MODERATE tier', () => {
      render(<DetectionQualityBadge confidence={0.55} />);
      const badge = screen.getByTestId('detection-quality-badge');
      expect(badge.className).toContain('yellow');
    });

    it('renders red styles for MARGINAL tier', () => {
      render(<DetectionQualityBadge confidence={0.25} />);
      const badge = screen.getByTestId('detection-quality-badge');
      expect(badge.className).toContain('red');
    });
  });
});
