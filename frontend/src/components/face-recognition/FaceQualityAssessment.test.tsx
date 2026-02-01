/**
 * FaceQualityAssessment Test Suite
 *
 * Tests for the FaceQualityAssessment component that displays
 * face quality visualization during enrollment.
 *
 * @module components/face-recognition/FaceQualityAssessment.test
 * @see NEM-4953 - Face Quality Assessment Visualization During Enrollment
 */

import { render, screen, within } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';

import FaceQualityAssessment from './FaceQualityAssessment';

import type { QualityFactors } from '../../types/faceRecognition';

// Mock the computeQualityFactorsFromScore to return deterministic values
vi.mock('../../types/faceRecognition', async () => {
  const actual = await vi.importActual<typeof import('../../types/faceRecognition')>(
    '../../types/faceRecognition'
  );
  return {
    ...actual,
    computeQualityFactorsFromScore: (score: number) => ({
      blur: {
        score: score,
        label: 'Sharpness',
        status: score >= 0.8 ? 'good' : score >= 0.6 ? 'fair' : 'poor',
        recommendation:
          score < 0.8
            ? 'Hold the camera steady or improve lighting for a sharper image'
            : undefined,
      },
      lighting: {
        score: score,
        label: 'Lighting',
        status: score >= 0.8 ? 'good' : score >= 0.6 ? 'fair' : 'poor',
        recommendation:
          score < 0.8
            ? 'Face towards a light source or move to a better-lit area'
            : undefined,
      },
      angle: {
        score: score,
        label: 'Face Angle',
        status: score >= 0.8 ? 'good' : score >= 0.6 ? 'fair' : 'poor',
        recommendation:
          score < 0.8
            ? 'Look directly at the camera with face fully visible'
            : undefined,
      },
      occlusion: {
        score: score,
        label: 'Visibility',
        status: score >= 0.8 ? 'good' : score >= 0.6 ? 'fair' : 'poor',
        recommendation:
          score < 0.8
            ? 'Remove glasses, hats, or other items covering your face'
            : undefined,
      },
    }),
  };
});

const mockGoodFactors: QualityFactors = {
  blur: { score: 0.9, label: 'Sharpness', status: 'good' },
  lighting: { score: 0.85, label: 'Lighting', status: 'good' },
  angle: { score: 0.92, label: 'Face Angle', status: 'good' },
  occlusion: { score: 0.88, label: 'Visibility', status: 'good' },
};

const mockFairFactors: QualityFactors = {
  blur: { score: 0.75, label: 'Sharpness', status: 'fair', recommendation: 'Hold camera steady' },
  lighting: { score: 0.72, label: 'Lighting', status: 'fair', recommendation: 'Improve lighting' },
  angle: { score: 0.78, label: 'Face Angle', status: 'fair', recommendation: 'Face the camera' },
  occlusion: { score: 0.7, label: 'Visibility', status: 'fair', recommendation: 'Remove obstructions' },
};

const mockPoorFactors: QualityFactors = {
  blur: { score: 0.4, label: 'Sharpness', status: 'poor', recommendation: 'Image is blurry' },
  lighting: { score: 0.5, label: 'Lighting', status: 'poor', recommendation: 'Too dark' },
  angle: { score: 0.55, label: 'Face Angle', status: 'poor', recommendation: 'Face not visible' },
  occlusion: { score: 0.45, label: 'Visibility', status: 'poor', recommendation: 'Face is occluded' },
};

describe('FaceQualityAssessment', () => {
  // ========== Basic Rendering ==========

  describe('basic rendering', () => {
    it('renders the component with quality score', () => {
      render(<FaceQualityAssessment qualityScore={0.85} />);
      expect(screen.getByTestId('face-quality-assessment')).toBeInTheDocument();
    });

    it('displays the overall quality score', () => {
      render(<FaceQualityAssessment qualityScore={0.85} />);
      expect(screen.getByText('Quality Score')).toBeInTheDocument();
      // Check for percentage in the overall score section
      const overallSection = screen.getByTestId('quality-overall-score');
      expect(within(overallSection).getByText('85%')).toBeInTheDocument();
    });

    it('displays the quality progress bar', () => {
      render(<FaceQualityAssessment qualityScore={0.85} />);
      const progressBar = screen.getByTestId('quality-progress-bar');
      expect(progressBar).toBeInTheDocument();
      expect(progressBar).toHaveStyle({ width: '85%' });
    });

    it('displays the quality indicator dot', () => {
      render(<FaceQualityAssessment qualityScore={0.85} />);
      const indicator = screen.getByTestId('quality-indicator');
      expect(indicator).toBeInTheDocument();
    });

    it('sets enrollable data attribute correctly for good quality', () => {
      render(<FaceQualityAssessment qualityScore={0.85} />);
      const container = screen.getByTestId('face-quality-assessment');
      expect(container).toHaveAttribute('data-enrollable', 'true');
    });

    it('sets enrollable data attribute correctly for poor quality', () => {
      render(<FaceQualityAssessment qualityScore={0.5} />);
      const container = screen.getByTestId('face-quality-assessment');
      expect(container).toHaveAttribute('data-enrollable', 'false');
    });
  });

  // ========== Quality Status Indicators ==========

  describe('quality status indicators', () => {
    it('shows green indicator and "Good" label for quality >= 0.8', () => {
      render(<FaceQualityAssessment qualityScore={0.85} />);
      const indicator = screen.getByTestId('quality-indicator');
      expect(indicator).toHaveClass('bg-green-500');
      expect(screen.getByText('Good')).toBeInTheDocument();
    });

    it('shows yellow indicator and "Fair" label for quality 0.7-0.8', () => {
      render(<FaceQualityAssessment qualityScore={0.75} />);
      const indicator = screen.getByTestId('quality-indicator');
      expect(indicator).toHaveClass('bg-yellow-500');
      expect(screen.getByText('Fair')).toBeInTheDocument();
    });

    it('shows red indicator and "Poor" label for quality < 0.7', () => {
      render(<FaceQualityAssessment qualityScore={0.5} />);
      const indicator = screen.getByTestId('quality-indicator');
      expect(indicator).toHaveClass('bg-red-500');
      expect(screen.getByText('Poor')).toBeInTheDocument();
    });

    it('shows correct indicator at boundary 0.8', () => {
      render(<FaceQualityAssessment qualityScore={0.8} />);
      const indicator = screen.getByTestId('quality-indicator');
      expect(indicator).toHaveClass('bg-green-500');
    });

    it('shows correct indicator at boundary 0.7', () => {
      render(<FaceQualityAssessment qualityScore={0.7} />);
      const indicator = screen.getByTestId('quality-indicator');
      expect(indicator).toHaveClass('bg-yellow-500');
    });
  });

  // ========== Quality Factors Breakdown ==========

  describe('quality factors breakdown', () => {
    it('displays all four quality factors', () => {
      render(<FaceQualityAssessment qualityScore={0.85} />);
      expect(screen.getByText('Sharpness')).toBeInTheDocument();
      expect(screen.getByText('Lighting')).toBeInTheDocument();
      expect(screen.getByText('Face Angle')).toBeInTheDocument();
      expect(screen.getByText('Visibility')).toBeInTheDocument();
    });

    it('displays factors section label', () => {
      render(<FaceQualityAssessment qualityScore={0.85} />);
      expect(screen.getByText('Quality Factors')).toBeInTheDocument();
    });

    it('hides factors when showFactors is false', () => {
      render(<FaceQualityAssessment qualityScore={0.85} showFactors={false} />);
      expect(screen.queryByText('Quality Factors')).not.toBeInTheDocument();
      expect(screen.queryByText('Sharpness')).not.toBeInTheDocument();
    });

    it('uses provided quality factors instead of computing', () => {
      render(
        <FaceQualityAssessment qualityScore={0.85} qualityFactors={mockGoodFactors} />
      );
      // Check that factor scores are displayed (90% for blur)
      const blurSection = screen.getByTestId('quality-factor-sharpness');
      expect(within(blurSection).getByText('90%')).toBeInTheDocument();
    });

    it('shows progress bars for each factor', () => {
      render(<FaceQualityAssessment qualityScore={0.85} />);
      const factorsSection = screen.getByTestId('quality-factors');
      const progressBars = within(factorsSection).getAllByRole('generic').filter(
        el => el.classList.contains('bg-gray-700')
      );
      expect(progressBars.length).toBe(4);
    });
  });

  // ========== Warnings and Messages ==========

  describe('warnings and messages', () => {
    it('shows good quality message for score >= 0.8', () => {
      render(<FaceQualityAssessment qualityScore={0.85} />);
      expect(screen.getByTestId('quality-good-message')).toBeInTheDocument();
      expect(screen.getByText(/excellent quality/i)).toBeInTheDocument();
    });

    it('shows fair warning for score 0.7-0.8', () => {
      render(<FaceQualityAssessment qualityScore={0.75} />);
      expect(screen.getByTestId('quality-fair-warning')).toBeInTheDocument();
      expect(screen.getByText(/moderate quality/i)).toBeInTheDocument();
    });

    it('shows blocked warning for score < 0.7', () => {
      render(<FaceQualityAssessment qualityScore={0.5} />);
      expect(screen.getByTestId('quality-blocked-warning')).toBeInTheDocument();
      expect(screen.getByText(/quality too low/i)).toBeInTheDocument();
    });

    it('does not show warning for good quality', () => {
      render(<FaceQualityAssessment qualityScore={0.9} />);
      expect(screen.queryByTestId('quality-fair-warning')).not.toBeInTheDocument();
      expect(screen.queryByTestId('quality-blocked-warning')).not.toBeInTheDocument();
    });

    it('hides warnings when showRecommendations is false', () => {
      render(<FaceQualityAssessment qualityScore={0.5} showRecommendations={false} />);
      expect(screen.queryByTestId('quality-blocked-warning')).not.toBeInTheDocument();
    });
  });

  // ========== Recommendations ==========

  describe('recommendations', () => {
    it('shows recommendations list for fair quality', () => {
      render(
        <FaceQualityAssessment qualityScore={0.75} qualityFactors={mockFairFactors} />
      );
      expect(screen.getByTestId('quality-recommendations')).toBeInTheDocument();
      expect(screen.getByText(/tips for better quality/i)).toBeInTheDocument();
    });

    it('shows recommendations list for poor quality', () => {
      render(
        <FaceQualityAssessment qualityScore={0.5} qualityFactors={mockPoorFactors} />
      );
      expect(screen.getByTestId('quality-recommendations')).toBeInTheDocument();
    });

    it('does not show recommendations for good quality', () => {
      render(
        <FaceQualityAssessment qualityScore={0.9} qualityFactors={mockGoodFactors} />
      );
      expect(screen.queryByTestId('quality-recommendations')).not.toBeInTheDocument();
    });

    it('displays factor-specific recommendations', () => {
      render(
        <FaceQualityAssessment qualityScore={0.75} qualityFactors={mockFairFactors} />
      );
      expect(screen.getByText(/hold camera steady/i)).toBeInTheDocument();
      expect(screen.getByText(/improve lighting/i)).toBeInTheDocument();
    });
  });

  // ========== Compact Mode ==========

  describe('compact mode', () => {
    it('renders in compact mode', () => {
      render(<FaceQualityAssessment qualityScore={0.85} compact />);
      expect(screen.getByTestId('face-quality-assessment')).toBeInTheDocument();
    });

    it('uses smaller progress bar in compact mode', () => {
      render(<FaceQualityAssessment qualityScore={0.85} compact />);
      const indicator = screen.getByTestId('quality-indicator');
      expect(indicator).toHaveClass('w-2');
      expect(indicator).toHaveClass('h-2');
    });

    it('uses larger indicator in normal mode', () => {
      render(<FaceQualityAssessment qualityScore={0.85} compact={false} />);
      const indicator = screen.getByTestId('quality-indicator');
      expect(indicator).toHaveClass('w-3');
      expect(indicator).toHaveClass('h-3');
    });
  });

  // ========== Edge Cases ==========

  describe('edge cases', () => {
    it('handles quality score of 0', () => {
      render(<FaceQualityAssessment qualityScore={0} />);
      // Check for percentage in the overall score section
      const overallSection = screen.getByTestId('quality-overall-score');
      expect(within(overallSection).getByText('0%')).toBeInTheDocument();
      expect(screen.getByTestId('quality-blocked-warning')).toBeInTheDocument();
    });

    it('handles quality score of 1', () => {
      render(<FaceQualityAssessment qualityScore={1} />);
      // Check for percentage in the overall score section
      const overallSection = screen.getByTestId('quality-overall-score');
      expect(within(overallSection).getByText('100%')).toBeInTheDocument();
      expect(screen.getByTestId('quality-good-message')).toBeInTheDocument();
    });

    it('handles quality score above 1 (capped)', () => {
      render(<FaceQualityAssessment qualityScore={1.2} />);
      const progressBar = screen.getByTestId('quality-progress-bar');
      expect(progressBar).toHaveStyle({ width: '100%' });
    });

    it('handles quality score below 0 (capped)', () => {
      render(<FaceQualityAssessment qualityScore={-0.1} />);
      const progressBar = screen.getByTestId('quality-progress-bar');
      expect(progressBar).toHaveStyle({ width: '0%' });
    });

    it('applies custom className', () => {
      render(<FaceQualityAssessment qualityScore={0.85} className="custom-class" />);
      const container = screen.getByTestId('face-quality-assessment');
      expect(container).toHaveClass('custom-class');
    });
  });

  // ========== Accessibility ==========

  describe('accessibility', () => {
    it('quality indicator has aria-label', () => {
      render(<FaceQualityAssessment qualityScore={0.85} />);
      const indicator = screen.getByTestId('quality-indicator');
      expect(indicator).toHaveAttribute('aria-label', 'Quality: Good');
    });

    it('quality indicator has correct aria-label for fair quality', () => {
      render(<FaceQualityAssessment qualityScore={0.75} />);
      const indicator = screen.getByTestId('quality-indicator');
      expect(indicator).toHaveAttribute('aria-label', 'Quality: Fair');
    });

    it('quality indicator has correct aria-label for poor quality', () => {
      render(<FaceQualityAssessment qualityScore={0.5} />);
      const indicator = screen.getByTestId('quality-indicator');
      expect(indicator).toHaveAttribute('aria-label', 'Quality: Poor');
    });
  });
});
