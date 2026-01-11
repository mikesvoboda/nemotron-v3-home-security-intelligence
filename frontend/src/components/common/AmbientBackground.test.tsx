import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import AmbientBackground, { getThreatCategory, threatLevelToRiskLevel } from './AmbientBackground';

// Mock matchMedia globally
const mockMatchMedia = vi.fn().mockImplementation((query: string) => ({
  matches: false,
  media: query,
  onchange: null,
  addListener: vi.fn(),
  removeListener: vi.fn(),
  addEventListener: vi.fn(),
  removeEventListener: vi.fn(),
  dispatchEvent: vi.fn(),
}));

describe('AmbientBackground', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: mockMatchMedia,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('getThreatCategory', () => {
    it('returns normal for scores 0-30', () => {
      expect(getThreatCategory(0)).toBe('normal');
      expect(getThreatCategory(15)).toBe('normal');
      expect(getThreatCategory(30)).toBe('normal');
    });

    it('returns elevated for scores 31-60', () => {
      expect(getThreatCategory(31)).toBe('elevated');
      expect(getThreatCategory(45)).toBe('elevated');
      expect(getThreatCategory(60)).toBe('elevated');
    });

    it('returns high for scores 61-80', () => {
      expect(getThreatCategory(61)).toBe('high');
      expect(getThreatCategory(70)).toBe('high');
      expect(getThreatCategory(80)).toBe('high');
    });

    it('returns critical for scores 81-100', () => {
      expect(getThreatCategory(81)).toBe('critical');
      expect(getThreatCategory(90)).toBe('critical');
      expect(getThreatCategory(100)).toBe('critical');
    });
  });

  describe('threatLevelToRiskLevel', () => {
    it('returns low for scores 0-30', () => {
      expect(threatLevelToRiskLevel(0)).toBe('low');
      expect(threatLevelToRiskLevel(30)).toBe('low');
    });

    it('returns medium for scores 31-60', () => {
      expect(threatLevelToRiskLevel(31)).toBe('medium');
      expect(threatLevelToRiskLevel(60)).toBe('medium');
    });

    it('returns high for scores 61-80', () => {
      expect(threatLevelToRiskLevel(61)).toBe('high');
      expect(threatLevelToRiskLevel(80)).toBe('high');
    });

    it('returns critical for scores 81-100', () => {
      expect(threatLevelToRiskLevel(81)).toBe('critical');
      expect(threatLevelToRiskLevel(100)).toBe('critical');
    });
  });

  describe('component rendering', () => {
    it('renders children when enabled', () => {
      render(
        <AmbientBackground threatLevel={0} enabled={true}>
          <div data-testid="child">Child Content</div>
        </AmbientBackground>
      );

      expect(screen.getByTestId('child')).toBeInTheDocument();
      expect(screen.getByTestId('ambient-background')).toBeInTheDocument();
    });

    it('renders children without ambient wrapper when disabled', () => {
      render(
        <AmbientBackground threatLevel={50} enabled={false}>
          <div data-testid="child">Child Content</div>
        </AmbientBackground>
      );

      expect(screen.getByTestId('child')).toBeInTheDocument();
      expect(screen.queryByTestId('ambient-background')).not.toBeInTheDocument();
    });

    it('renders ambient overlay with correct threat category attribute', () => {
      render(
        <AmbientBackground threatLevel={50} enabled={true}>
          <div>Content</div>
        </AmbientBackground>
      );

      const overlay = screen.getByTestId('ambient-overlay');
      expect(overlay).toHaveAttribute('data-threat-category', 'elevated');
    });

    it('clamps threat level to valid range', () => {
      render(
        <AmbientBackground threatLevel={150} enabled={true}>
          <div>Content</div>
        </AmbientBackground>
      );

      const overlay = screen.getByTestId('ambient-overlay');
      expect(overlay).toHaveAttribute('data-threat-level', '100');
    });

    it('handles negative threat level by clamping to 0', () => {
      render(
        <AmbientBackground threatLevel={-10} enabled={true}>
          <div>Content</div>
        </AmbientBackground>
      );

      const overlay = screen.getByTestId('ambient-overlay');
      expect(overlay).toHaveAttribute('data-threat-level', '0');
    });

    it('sets aria-hidden on overlay for accessibility', () => {
      render(
        <AmbientBackground threatLevel={50} enabled={true}>
          <div>Content</div>
        </AmbientBackground>
      );

      const overlay = screen.getByTestId('ambient-overlay');
      expect(overlay).toHaveAttribute('aria-hidden', 'true');
    });

    it('applies custom className', () => {
      render(
        <AmbientBackground threatLevel={0} enabled={true} className="custom-class">
          <div>Content</div>
        </AmbientBackground>
      );

      expect(screen.getByTestId('ambient-background')).toHaveClass('custom-class');
    });
  });

  describe('threat level categories', () => {
    it('renders normal category with no visible overlay', () => {
      render(
        <AmbientBackground threatLevel={20} enabled={true}>
          <div>Content</div>
        </AmbientBackground>
      );

      const overlay = screen.getByTestId('ambient-overlay');
      expect(overlay).toHaveAttribute('data-threat-category', 'normal');
      expect(overlay).toHaveClass('opacity-0');
    });

    it('renders elevated category with visible overlay', () => {
      render(
        <AmbientBackground threatLevel={45} enabled={true}>
          <div>Content</div>
        </AmbientBackground>
      );

      const overlay = screen.getByTestId('ambient-overlay');
      expect(overlay).toHaveAttribute('data-threat-category', 'elevated');
      expect(overlay).toHaveClass('opacity-100');
    });

    it('renders high category with visible overlay', () => {
      render(
        <AmbientBackground threatLevel={75} enabled={true}>
          <div>Content</div>
        </AmbientBackground>
      );

      const overlay = screen.getByTestId('ambient-overlay');
      expect(overlay).toHaveAttribute('data-threat-category', 'high');
      expect(overlay).toHaveClass('opacity-100');
    });

    it('renders critical category with visible overlay', () => {
      render(
        <AmbientBackground threatLevel={90} enabled={true}>
          <div>Content</div>
        </AmbientBackground>
      );

      const overlay = screen.getByTestId('ambient-overlay');
      expect(overlay).toHaveAttribute('data-threat-category', 'critical');
      expect(overlay).toHaveClass('opacity-100');
    });
  });

  describe('reduced motion', () => {
    it('does not apply animation when reduced motion is preferred', () => {
      mockMatchMedia.mockImplementation((query: string) => ({
        matches: query === '(prefers-reduced-motion: reduce)',
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }));

      render(
        <AmbientBackground threatLevel={90} enabled={true}>
          <div>Content</div>
        </AmbientBackground>
      );

      const overlay = screen.getByTestId('ambient-overlay');
      expect(overlay).not.toHaveClass('animate-ambient-pulse');
    });

    it('applies animation for critical when reduced motion is not preferred', () => {
      mockMatchMedia.mockImplementation((query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }));

      render(
        <AmbientBackground threatLevel={90} enabled={true}>
          <div>Content</div>
        </AmbientBackground>
      );

      const overlay = screen.getByTestId('ambient-overlay');
      expect(overlay).toHaveClass('animate-ambient-pulse');
    });
  });
});
