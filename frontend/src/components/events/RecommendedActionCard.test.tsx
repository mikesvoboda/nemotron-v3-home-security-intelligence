import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import RecommendedActionCard from './RecommendedActionCard';

describe('RecommendedActionCard', () => {
  describe('rendering', () => {
    it('renders nothing when recommendedAction is null', () => {
      const { container } = render(<RecommendedActionCard recommendedAction={null} />);
      expect(container.firstChild).toBeNull();
    });

    it('renders nothing when recommendedAction is undefined', () => {
      const { container } = render(<RecommendedActionCard recommendedAction={undefined} />);
      expect(container.firstChild).toBeNull();
    });

    it('renders nothing when recommendedAction is empty string', () => {
      const { container } = render(<RecommendedActionCard recommendedAction="" />);
      expect(container.firstChild).toBeNull();
    });

    it('renders the action text when provided', () => {
      render(<RecommendedActionCard recommendedAction="Contact authorities immediately" />);
      expect(screen.getByText('Contact authorities immediately')).toBeInTheDocument();
    });

    it('renders the header', () => {
      render(<RecommendedActionCard recommendedAction="Review camera footage" />);
      expect(screen.getByText('Recommended Action')).toBeInTheDocument();
    });

    it('has correct test id', () => {
      render(<RecommendedActionCard recommendedAction="Test action" />);
      expect(screen.getByTestId('recommended-action-card')).toBeInTheDocument();
    });
  });

  describe('styling', () => {
    it('applies custom className', () => {
      render(
        <RecommendedActionCard
          recommendedAction="Test action"
          className="custom-class"
        />
      );
      expect(screen.getByTestId('recommended-action-card')).toHaveClass('custom-class');
    });

    it('uses amber styling when not reviewed', () => {
      render(<RecommendedActionCard recommendedAction="Test action" />);
      const card = screen.getByTestId('recommended-action-card');
      expect(card).toHaveClass('border-amber-500/40');
      expect(card).toHaveClass('bg-amber-500/10');
    });

    it('uses gray styling when reviewed', () => {
      render(
        <RecommendedActionCard
          recommendedAction="Test action"
          isReviewed={true}
        />
      );
      const card = screen.getByTestId('recommended-action-card');
      expect(card).toHaveClass('border-gray-600');
      expect(card).toHaveClass('bg-gray-800/50');
    });
  });

  describe('content variations', () => {
    it('renders long action text', () => {
      const longAction =
        'Review all camera footage from the past 30 minutes, contact local authorities if suspicious activity continues, and document all observations in the incident report.';
      render(<RecommendedActionCard recommendedAction={longAction} />);
      expect(screen.getByText(longAction)).toBeInTheDocument();
    });

    it('handles action text with special characters', () => {
      const action = 'Contact: 911 - Emergency response & follow-up required';
      render(<RecommendedActionCard recommendedAction={action} />);
      expect(screen.getByText(action)).toBeInTheDocument();
    });
  });
});
