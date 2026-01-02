import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import EventAuditDetail from './EventAuditDetail';
import { AuditApiError } from '../../services/auditApi';
import * as auditApi from '../../services/auditApi';

import type { EventAudit } from '../../services/auditApi';

// Mock only the functions, not the classes
vi.mock('../../services/auditApi', async (importOriginal) => {
  const original = await importOriginal<typeof import('../../services/auditApi')>();
  return {
    ...original,
    fetchEventAudit: vi.fn(),
    triggerEvaluation: vi.fn(),
  };
});

describe('EventAuditDetail', () => {
  const mockEventAudit: EventAudit = {
    id: 1,
    event_id: 42,
    audited_at: '2024-01-15T10:30:00Z',
    is_fully_evaluated: true,
    contributions: {
      rtdetr: true,
      florence: true,
      clip: false,
      violence: true,
      clothing: false,
      vehicle: true,
      pet: false,
      weather: false,
      image_quality: true,
      zones: false,
      baseline: true,
      cross_camera: false,
    },
    prompt_length: 5000,
    prompt_token_estimate: 1250,
    enrichment_utilization: 0.75,
    scores: {
      context_usage: 4.2,
      reasoning_coherence: 4.5,
      risk_justification: 3.8,
      consistency: 4.0,
      overall: 4.1,
    },
    consistency_risk_score: 65,
    consistency_diff: 5,
    self_eval_critique: 'The analysis correctly identified the vehicle and assessed the risk appropriately.',
    improvements: {
      missing_context: ['Weather conditions at time of event'],
      confusing_sections: [],
      unused_data: ['Historical patterns for this camera'],
      format_suggestions: ['Include timestamps in summary'],
      model_gaps: ['Pet detection was not available'],
    },
  };

  const mockUnevaluatedAudit: EventAudit = {
    ...mockEventAudit,
    is_fully_evaluated: false,
    scores: {
      context_usage: null,
      reasoning_coherence: null,
      risk_justification: null,
      consistency: null,
      overall: null,
    },
    consistency_risk_score: null,
    consistency_diff: null,
    self_eval_critique: null,
    improvements: {
      missing_context: [],
      confusing_sections: [],
      unused_data: [],
      format_suggestions: [],
      model_gaps: [],
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('Loading State', () => {
    it('displays loading spinner initially', () => {
      vi.mocked(auditApi.fetchEventAudit).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      render(<EventAuditDetail eventId={42} />);

      expect(screen.getByText('Loading audit data...')).toBeInTheDocument();
    });

    it('shows loading animation', () => {
      vi.mocked(auditApi.fetchEventAudit).mockImplementation(
        () => new Promise(() => {})
      );

      const { container } = render(<EventAuditDetail eventId={42} />);

      const spinner = container.querySelector('.animate-spin');
      expect(spinner).toBeInTheDocument();
    });
  });

  describe('Error State', () => {
    it('displays error message when fetch fails', async () => {
      vi.mocked(auditApi.fetchEventAudit).mockRejectedValue(
        new AuditApiError(500, 'Internal server error')
      );

      render(<EventAuditDetail eventId={42} />);

      await waitFor(() => {
        expect(screen.getByText('Internal server error')).toBeInTheDocument();
      });
    });

    it('displays 404 message when audit not found', async () => {
      vi.mocked(auditApi.fetchEventAudit).mockRejectedValue(
        new AuditApiError(404, 'Audit not found')
      );

      render(<EventAuditDetail eventId={42} />);

      await waitFor(() => {
        expect(screen.getByText('No audit record found for this event.')).toBeInTheDocument();
      });
    });

    it('displays generic error for non-AuditApiError', async () => {
      vi.mocked(auditApi.fetchEventAudit).mockRejectedValue(new Error('Network error'));

      render(<EventAuditDetail eventId={42} />);

      await waitFor(() => {
        expect(screen.getByText('Failed to load audit data.')).toBeInTheDocument();
      });
    });

    it('shows Retry button on error', async () => {
      vi.mocked(auditApi.fetchEventAudit).mockRejectedValue(
        new AuditApiError(500, 'Server error')
      );

      render(<EventAuditDetail eventId={42} />);

      await waitFor(() => {
        expect(screen.getByText('Retry')).toBeInTheDocument();
      });
    });
  });

  describe('Header Section', () => {
    beforeEach(() => {
      vi.mocked(auditApi.fetchEventAudit).mockResolvedValue(mockEventAudit);
    });

    it('displays event ID', async () => {
      render(<EventAuditDetail eventId={42} />);

      await waitFor(() => {
        expect(screen.getByText('Event #42 Audit')).toBeInTheDocument();
      });
    });

    it('displays audited at timestamp', async () => {
      render(<EventAuditDetail eventId={42} />);

      await waitFor(() => {
        expect(screen.getByText(/Audited:/)).toBeInTheDocument();
      });
    });

    it('displays prompt length', async () => {
      render(<EventAuditDetail eventId={42} />);

      await waitFor(() => {
        expect(screen.getByText('5,000')).toBeInTheDocument();
        expect(screen.getByText(/chars/)).toBeInTheDocument();
      });
    });

    it('displays token estimate', async () => {
      render(<EventAuditDetail eventId={42} />);

      await waitFor(() => {
        expect(screen.getByText('~1,250')).toBeInTheDocument();
      });
    });

    it('displays enrichment utilization percentage', async () => {
      render(<EventAuditDetail eventId={42} />);

      await waitFor(() => {
        expect(screen.getByText('75%')).toBeInTheDocument();
      });
    });
  });

  describe('Evaluate Button', () => {
    it('shows "Run Evaluation" when not evaluated', async () => {
      vi.mocked(auditApi.fetchEventAudit).mockResolvedValue(mockUnevaluatedAudit);

      render(<EventAuditDetail eventId={42} />);

      await waitFor(() => {
        expect(screen.getByText('Run Evaluation')).toBeInTheDocument();
      });
    });

    it('shows "Re-run Evaluation" when already evaluated', async () => {
      vi.mocked(auditApi.fetchEventAudit).mockResolvedValue(mockEventAudit);

      render(<EventAuditDetail eventId={42} />);

      await waitFor(() => {
        expect(screen.getByText('Re-run Evaluation')).toBeInTheDocument();
      });
    });

    it('calls triggerEvaluation when clicked', async () => {
      vi.mocked(auditApi.fetchEventAudit).mockResolvedValue(mockUnevaluatedAudit);
      vi.mocked(auditApi.triggerEvaluation).mockResolvedValue(mockEventAudit);

      const user = userEvent.setup();
      render(<EventAuditDetail eventId={42} />);

      await waitFor(() => {
        expect(screen.getByText('Run Evaluation')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Run Evaluation'));

      await waitFor(() => {
        expect(auditApi.triggerEvaluation).toHaveBeenCalledWith(42, false);
      });
    });

    it('calls triggerEvaluation with force=true when re-evaluating', async () => {
      vi.mocked(auditApi.fetchEventAudit).mockResolvedValue(mockEventAudit);
      vi.mocked(auditApi.triggerEvaluation).mockResolvedValue(mockEventAudit);

      const user = userEvent.setup();
      render(<EventAuditDetail eventId={42} />);

      await waitFor(() => {
        expect(screen.getByText('Re-run Evaluation')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Re-run Evaluation'));

      await waitFor(() => {
        expect(auditApi.triggerEvaluation).toHaveBeenCalledWith(42, true);
      });
    });

    it('shows evaluating state when button is clicked', async () => {
      vi.mocked(auditApi.fetchEventAudit).mockResolvedValue(mockUnevaluatedAudit);
      vi.mocked(auditApi.triggerEvaluation).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      const user = userEvent.setup();
      render(<EventAuditDetail eventId={42} />);

      await waitFor(() => {
        expect(screen.getByText('Run Evaluation')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Run Evaluation'));

      await waitFor(() => {
        expect(screen.getByText('Evaluating...')).toBeInTheDocument();
      });
    });

    it('disables button while evaluating', async () => {
      vi.mocked(auditApi.fetchEventAudit).mockResolvedValue(mockUnevaluatedAudit);
      vi.mocked(auditApi.triggerEvaluation).mockImplementation(
        () => new Promise(() => {})
      );

      const user = userEvent.setup();
      render(<EventAuditDetail eventId={42} />);

      await waitFor(() => {
        expect(screen.getByText('Run Evaluation')).toBeInTheDocument();
      });

      const button = screen.getByText('Run Evaluation').closest('button');
      await user.click(button!);

      await waitFor(() => {
        expect(button).toBeDisabled();
      });
    });
  });

  describe('Quality Scores Section', () => {
    it('displays quality scores when fully evaluated', async () => {
      vi.mocked(auditApi.fetchEventAudit).mockResolvedValue(mockEventAudit);

      render(<EventAuditDetail eventId={42} />);

      await waitFor(() => {
        expect(screen.getByText('Quality Scores')).toBeInTheDocument();
      });

      expect(screen.getByText('Context Usage')).toBeInTheDocument();
      expect(screen.getByText('Reasoning Coherence')).toBeInTheDocument();
      expect(screen.getByText('Risk Justification')).toBeInTheDocument();
      expect(screen.getByText('Consistency')).toBeInTheDocument();
      expect(screen.getByText('Overall')).toBeInTheDocument();
    });

    it('displays score values', async () => {
      vi.mocked(auditApi.fetchEventAudit).mockResolvedValue(mockEventAudit);

      render(<EventAuditDetail eventId={42} />);

      await waitFor(() => {
        expect(screen.getByText('4.2 / 5')).toBeInTheDocument();
        expect(screen.getByText('4.5 / 5')).toBeInTheDocument();
        expect(screen.getByText('3.8 / 5')).toBeInTheDocument();
        expect(screen.getByText('4.0 / 5')).toBeInTheDocument();
        expect(screen.getByText('4.1 / 5')).toBeInTheDocument();
      });
    });

    it('shows placeholder when not evaluated', async () => {
      vi.mocked(auditApi.fetchEventAudit).mockResolvedValue(mockUnevaluatedAudit);

      render(<EventAuditDetail eventId={42} />);

      await waitFor(() => {
        expect(screen.getByText('Run evaluation to see quality scores')).toBeInTheDocument();
      });
    });

    it('displays consistency check diff', async () => {
      vi.mocked(auditApi.fetchEventAudit).mockResolvedValue(mockEventAudit);

      render(<EventAuditDetail eventId={42} />);

      await waitFor(() => {
        expect(screen.getByText('Consistency Check')).toBeInTheDocument();
        expect(screen.getByText('+5 pts')).toBeInTheDocument();
      });
    });
  });

  describe('Model Contributions Section', () => {
    beforeEach(() => {
      vi.mocked(auditApi.fetchEventAudit).mockResolvedValue(mockEventAudit);
    });

    it('displays model contributions section', async () => {
      render(<EventAuditDetail eventId={42} />);

      await waitFor(() => {
        expect(screen.getByText('Model Contributions')).toBeInTheDocument();
      });
    });

    it('displays model count', async () => {
      render(<EventAuditDetail eventId={42} />);

      await waitFor(() => {
        // 6 models contributed out of 12
        expect(screen.getByText('6 / 12')).toBeInTheDocument();
      });
    });

    it('displays all model names', async () => {
      render(<EventAuditDetail eventId={42} />);

      await waitFor(() => {
        expect(screen.getByText('RT-DETR')).toBeInTheDocument();
        expect(screen.getByText('Florence')).toBeInTheDocument();
        expect(screen.getByText('CLIP')).toBeInTheDocument();
        expect(screen.getByText('Violence')).toBeInTheDocument();
        expect(screen.getByText('Clothing')).toBeInTheDocument();
        expect(screen.getByText('Vehicle')).toBeInTheDocument();
        expect(screen.getByText('Pet')).toBeInTheDocument();
        expect(screen.getByText('Weather')).toBeInTheDocument();
        expect(screen.getByText('Quality')).toBeInTheDocument();
        expect(screen.getByText('Zones')).toBeInTheDocument();
        expect(screen.getByText('Baseline')).toBeInTheDocument();
        expect(screen.getByText('Cross-cam')).toBeInTheDocument();
      });
    });

    it('shows checkmark for contributing models', async () => {
      render(<EventAuditDetail eventId={42} />);

      await waitFor(() => {
        expect(screen.getByText('RT-DETR')).toBeInTheDocument();
      });

      // Models that contributed should have green checkmark styling
      const rtDetrElement = screen.getByText('RT-DETR').closest('div');
      expect(rtDetrElement).toHaveClass('bg-[#76B900]/10');
    });

    it('shows X for non-contributing models', async () => {
      render(<EventAuditDetail eventId={42} />);

      await waitFor(() => {
        expect(screen.getByText('CLIP')).toBeInTheDocument();
      });

      // CLIP did not contribute
      const clipElement = screen.getByText('CLIP').closest('div');
      expect(clipElement).toHaveClass('bg-black/20');
    });
  });

  describe('Self-Critique Section', () => {
    it('displays self-critique when evaluated', async () => {
      vi.mocked(auditApi.fetchEventAudit).mockResolvedValue(mockEventAudit);

      render(<EventAuditDetail eventId={42} />);

      await waitFor(() => {
        expect(screen.getByText('Self-Critique')).toBeInTheDocument();
        expect(
          screen.getByText(/The analysis correctly identified the vehicle/)
        ).toBeInTheDocument();
      });
    });

    it('hides self-critique section when not evaluated', async () => {
      vi.mocked(auditApi.fetchEventAudit).mockResolvedValue(mockUnevaluatedAudit);

      render(<EventAuditDetail eventId={42} />);

      await waitFor(() => {
        expect(screen.getByText('Model Contributions')).toBeInTheDocument();
      });

      expect(screen.queryByText('Self-Critique')).not.toBeInTheDocument();
    });
  });

  describe('Improvements Section', () => {
    it('displays improvement suggestions', async () => {
      vi.mocked(auditApi.fetchEventAudit).mockResolvedValue(mockEventAudit);

      render(<EventAuditDetail eventId={42} />);

      await waitFor(() => {
        expect(screen.getByText('Improvement Suggestions')).toBeInTheDocument();
      });
    });

    it('displays missing context items', async () => {
      vi.mocked(auditApi.fetchEventAudit).mockResolvedValue(mockEventAudit);

      render(<EventAuditDetail eventId={42} />);

      await waitFor(() => {
        expect(screen.getByText('Missing Context')).toBeInTheDocument();
        expect(screen.getByText('Weather conditions at time of event')).toBeInTheDocument();
      });
    });

    it('displays unused data items', async () => {
      vi.mocked(auditApi.fetchEventAudit).mockResolvedValue(mockEventAudit);

      render(<EventAuditDetail eventId={42} />);

      await waitFor(() => {
        expect(screen.getByText('Unused Data')).toBeInTheDocument();
        expect(screen.getByText('Historical patterns for this camera')).toBeInTheDocument();
      });
    });

    it('displays format suggestions', async () => {
      vi.mocked(auditApi.fetchEventAudit).mockResolvedValue(mockEventAudit);

      render(<EventAuditDetail eventId={42} />);

      await waitFor(() => {
        expect(screen.getByText('Format Suggestions')).toBeInTheDocument();
        expect(screen.getByText('Include timestamps in summary')).toBeInTheDocument();
      });
    });

    it('displays model gaps', async () => {
      vi.mocked(auditApi.fetchEventAudit).mockResolvedValue(mockEventAudit);

      render(<EventAuditDetail eventId={42} />);

      await waitFor(() => {
        expect(screen.getByText('Model Gaps')).toBeInTheDocument();
        expect(screen.getByText('Pet detection was not available')).toBeInTheDocument();
      });
    });

    it('shows no suggestions message when all empty', async () => {
      const noImprovementsAudit: EventAudit = {
        ...mockEventAudit,
        improvements: {
          missing_context: [],
          confusing_sections: [],
          unused_data: [],
          format_suggestions: [],
          model_gaps: [],
        },
      };

      vi.mocked(auditApi.fetchEventAudit).mockResolvedValue(noImprovementsAudit);

      render(<EventAuditDetail eventId={42} />);

      await waitFor(() => {
        expect(screen.getByText('No improvement suggestions available')).toBeInTheDocument();
      });
    });

    it('hides improvements section when not evaluated', async () => {
      vi.mocked(auditApi.fetchEventAudit).mockResolvedValue(mockUnevaluatedAudit);

      render(<EventAuditDetail eventId={42} />);

      await waitFor(() => {
        expect(screen.getByText('Model Contributions')).toBeInTheDocument();
      });

      expect(screen.queryByText('Improvement Suggestions')).not.toBeInTheDocument();
    });
  });

  describe('Event ID Changes', () => {
    it('refetches data when eventId changes', async () => {
      vi.mocked(auditApi.fetchEventAudit).mockResolvedValue(mockEventAudit);

      const { rerender } = render(<EventAuditDetail eventId={42} />);

      await waitFor(() => {
        expect(auditApi.fetchEventAudit).toHaveBeenCalledWith(42);
      });

      // Change eventId
      rerender(<EventAuditDetail eventId={100} />);

      await waitFor(() => {
        expect(auditApi.fetchEventAudit).toHaveBeenCalledWith(100);
      });
    });
  });

  describe('Score Bar Styling', () => {
    it('shows green for high scores', async () => {
      vi.mocked(auditApi.fetchEventAudit).mockResolvedValue(mockEventAudit);

      const { container } = render(<EventAuditDetail eventId={42} />);

      await waitFor(() => {
        expect(screen.getByText('4.5 / 5')).toBeInTheDocument();
      });

      // High scores (>= 4) should have green bar
      const greenBars = container.querySelectorAll('.bg-green-500');
      expect(greenBars.length).toBeGreaterThan(0);
    });

    it('shows yellow for medium scores', async () => {
      const mediumScoresAudit: EventAudit = {
        ...mockEventAudit,
        scores: {
          context_usage: 3.5,
          reasoning_coherence: 3.2,
          risk_justification: 3.0,
          consistency: 3.8,
          overall: 3.4,
        },
      };

      vi.mocked(auditApi.fetchEventAudit).mockResolvedValue(mediumScoresAudit);

      const { container } = render(<EventAuditDetail eventId={42} />);

      await waitFor(() => {
        expect(screen.getByText('3.5 / 5')).toBeInTheDocument();
      });

      // Medium scores (>= 3 and < 4) should have yellow bar
      const yellowBars = container.querySelectorAll('.bg-yellow-500');
      expect(yellowBars.length).toBeGreaterThan(0);
    });

    it('shows red for low scores', async () => {
      const lowScoresAudit: EventAudit = {
        ...mockEventAudit,
        scores: {
          context_usage: 2.0,
          reasoning_coherence: 2.5,
          risk_justification: 1.8,
          consistency: 2.2,
          overall: 2.1,
        },
      };

      vi.mocked(auditApi.fetchEventAudit).mockResolvedValue(lowScoresAudit);

      const { container } = render(<EventAuditDetail eventId={42} />);

      await waitFor(() => {
        expect(screen.getByText('2.0 / 5')).toBeInTheDocument();
      });

      // Low scores (< 3) should have red bar
      const redBars = container.querySelectorAll('.bg-red-500');
      expect(redBars.length).toBeGreaterThan(0);
    });
  });

  describe('Consistency Diff Styling', () => {
    it('shows green for small diff', async () => {
      vi.mocked(auditApi.fetchEventAudit).mockResolvedValue(mockEventAudit);

      render(<EventAuditDetail eventId={42} />);

      await waitFor(() => {
        expect(screen.getByText('+5 pts')).toBeInTheDocument();
      });

      const diffElement = screen.getByText('+5 pts');
      expect(diffElement).toHaveClass('text-green-400');
    });

    it('shows yellow for medium diff', async () => {
      const mediumDiffAudit: EventAudit = {
        ...mockEventAudit,
        consistency_diff: 15,
      };

      vi.mocked(auditApi.fetchEventAudit).mockResolvedValue(mediumDiffAudit);

      render(<EventAuditDetail eventId={42} />);

      await waitFor(() => {
        expect(screen.getByText('+15 pts')).toBeInTheDocument();
      });

      const diffElement = screen.getByText('+15 pts');
      expect(diffElement).toHaveClass('text-yellow-400');
    });

    it('shows red for large diff', async () => {
      const largeDiffAudit: EventAudit = {
        ...mockEventAudit,
        consistency_diff: 25,
      };

      vi.mocked(auditApi.fetchEventAudit).mockResolvedValue(largeDiffAudit);

      render(<EventAuditDetail eventId={42} />);

      await waitFor(() => {
        expect(screen.getByText('+25 pts')).toBeInTheDocument();
      });

      const diffElement = screen.getByText('+25 pts');
      expect(diffElement).toHaveClass('text-red-400');
    });

    it('shows negative diff correctly', async () => {
      const negativeDiffAudit: EventAudit = {
        ...mockEventAudit,
        consistency_diff: -10,
      };

      vi.mocked(auditApi.fetchEventAudit).mockResolvedValue(negativeDiffAudit);

      render(<EventAuditDetail eventId={42} />);

      await waitFor(() => {
        expect(screen.getByText('-10 pts')).toBeInTheDocument();
      });
    });
  });

  describe('Styling', () => {
    it('uses NVIDIA dark theme colors', async () => {
      vi.mocked(auditApi.fetchEventAudit).mockResolvedValue(mockEventAudit);

      const { container } = render(<EventAuditDetail eventId={42} />);

      await waitFor(() => {
        expect(screen.getByText('Event #42 Audit')).toBeInTheDocument();
      });

      const darkPanel = container.querySelector('.bg-\\[\\#1F1F1F\\]');
      expect(darkPanel).toBeInTheDocument();
    });

    it('uses green accent for utilization', async () => {
      vi.mocked(auditApi.fetchEventAudit).mockResolvedValue(mockEventAudit);

      render(<EventAuditDetail eventId={42} />);

      await waitFor(() => {
        expect(screen.getByText('75%')).toBeInTheDocument();
      });

      const utilizationElement = screen.getByText('75%');
      expect(utilizationElement).toHaveClass('text-[#76B900]');
    });
  });
});
