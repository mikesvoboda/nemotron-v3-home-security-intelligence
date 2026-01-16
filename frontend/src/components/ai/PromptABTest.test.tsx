/**
 * Tests for PromptABTest component
 *
 * This component provides a split-view A/B testing interface for comparing
 * prompt performance on real events.
 *
 * Test coverage:
 * 1. renders side-by-side panels
 * 2. shows original prompt label on left
 * 3. shows modified prompt label on right
 * 4. displays test results when provided
 * 5. calculates and shows score delta
 * 6. colors delta green when B is lower
 * 7. colors delta red when B is higher
 * 8. Run Random button calls onRunRandomTests
 * 9. Promote B button calls onPromoteB
 * 10. shows loading state when isRunning
 * 11. disables buttons when isRunning
 */

import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import PromptABTest from './PromptABTest';

import type { ABTestResult } from '../../services/api';

describe('PromptABTest', () => {
  const mockOriginalPrompt = 'You are a security analyst. Analyze the scene.';
  const mockModifiedPrompt = 'You are a security analyst. Analyze the scene with extra context.';

  const mockResults: ABTestResult[] = [
    {
      eventId: 123,
      originalResult: {
        riskScore: 65,
        riskLevel: 'high',
        reasoning: 'Person detected approaching the door at night.',
        processingTimeMs: 250,
      },
      modifiedResult: {
        riskScore: 42,
        riskLevel: 'medium',
        reasoning: 'Person detected at night, but recognized as regular delivery.',
        processingTimeMs: 280,
      },
      scoreDelta: -23,
    },
  ];

  const defaultProps = {
    originalPrompt: mockOriginalPrompt,
    modifiedPrompt: mockModifiedPrompt,
    results: [],
    isRunning: false,
    onRunTest: vi.fn(),
    onRunRandomTests: vi.fn(),
    onPromoteB: vi.fn(),
  };

  it('renders side-by-side panels', () => {
    render(<PromptABTest {...defaultProps} />);

    // Should have a container with both panels
    const container = screen.getByTestId('prompt-ab-test');
    expect(container).toBeInTheDocument();

    // Should have two result panel areas (left and right)
    const leftPanel = screen.getByTestId('panel-original');
    const rightPanel = screen.getByTestId('panel-modified');
    expect(leftPanel).toBeInTheDocument();
    expect(rightPanel).toBeInTheDocument();
  });

  it('shows original prompt label on left', () => {
    render(<PromptABTest {...defaultProps} />);

    // The left panel should have "Original (A)" label
    expect(screen.getByText('Original (A)')).toBeInTheDocument();

    // Verify it's in the left panel
    const leftPanel = screen.getByTestId('panel-original');
    expect(leftPanel).toHaveTextContent('Original (A)');
  });

  it('shows modified prompt label on right', () => {
    render(<PromptABTest {...defaultProps} />);

    // The right panel should have "Modified (B)" label
    expect(screen.getByText('Modified (B)')).toBeInTheDocument();

    // Verify it's in the right panel
    const rightPanel = screen.getByTestId('panel-modified');
    expect(rightPanel).toHaveTextContent('Modified (B)');
  });

  it('displays test results when provided', () => {
    render(<PromptABTest {...defaultProps} results={mockResults} />);

    // Should display the risk scores
    expect(screen.getByText('65')).toBeInTheDocument();
    expect(screen.getByText('42')).toBeInTheDocument();

    // Should display the risk levels
    expect(screen.getByText('high')).toBeInTheDocument();
    expect(screen.getByText('medium')).toBeInTheDocument();
  });

  it('calculates and shows score delta', () => {
    render(<PromptABTest {...defaultProps} results={mockResults} />);

    // Should show the score delta
    const deltaIndicator = screen.getByTestId('delta-indicator');
    expect(deltaIndicator).toBeInTheDocument();
    expect(deltaIndicator).toHaveTextContent('-23');
  });

  it('colors delta green when B is lower', () => {
    // B is lower (better for security - less false alarms)
    const resultsWithBLower: ABTestResult[] = [
      {
        eventId: 1,
        originalResult: {
          riskScore: 70,
          riskLevel: 'high',
          reasoning: 'Original reasoning',
          processingTimeMs: 100,
        },
        modifiedResult: {
          riskScore: 40,
          riskLevel: 'medium',
          reasoning: 'Modified reasoning',
          processingTimeMs: 100,
        },
        scoreDelta: -30, // Negative = B is lower
      },
    ];

    render(<PromptABTest {...defaultProps} results={resultsWithBLower} />);

    const deltaIndicator = screen.getByTestId('delta-indicator');
    // Should have green styling (text-green-* or bg-green-*)
    expect(deltaIndicator).toHaveClass(/green/);
  });

  it('colors delta red when B is higher', () => {
    // B is higher (worse - more false alarms)
    const resultsWithBHigher: ABTestResult[] = [
      {
        eventId: 1,
        originalResult: {
          riskScore: 40,
          riskLevel: 'medium',
          reasoning: 'Original reasoning',
          processingTimeMs: 100,
        },
        modifiedResult: {
          riskScore: 70,
          riskLevel: 'high',
          reasoning: 'Modified reasoning',
          processingTimeMs: 100,
        },
        scoreDelta: 30, // Positive = B is higher
      },
    ];

    render(<PromptABTest {...defaultProps} results={resultsWithBHigher} />);

    const deltaIndicator = screen.getByTestId('delta-indicator');
    // Should have red styling (text-red-* or bg-red-*)
    expect(deltaIndicator).toHaveClass(/red/);
  });

  it('Run Random button calls onRunRandomTests', () => {
    const onRunRandomTests = vi.fn();
    render(<PromptABTest {...defaultProps} onRunRandomTests={onRunRandomTests} />);

    const runRandomButton = screen.getByRole('button', { name: /run.*random/i });
    fireEvent.click(runRandomButton);

    // Default is 5 random events
    expect(onRunRandomTests).toHaveBeenCalledWith(5);
  });

  it('Promote B button calls onPromoteB', () => {
    const onPromoteB = vi.fn();
    render(<PromptABTest {...defaultProps} onPromoteB={onPromoteB} />);

    const promoteButton = screen.getByRole('button', { name: /promote.*b/i });
    fireEvent.click(promoteButton);

    expect(onPromoteB).toHaveBeenCalledTimes(1);
  });

  it('shows loading state when isRunning', () => {
    render(<PromptABTest {...defaultProps} isRunning={true} />);

    // Should show a loading indicator (spinner)
    const spinner = screen.getByTestId('loading-spinner');
    expect(spinner).toBeInTheDocument();
  });

  it('disables buttons when isRunning', () => {
    render(<PromptABTest {...defaultProps} isRunning={true} />);

    const runRandomButton = screen.getByRole('button', { name: /run.*random/i });
    const promoteButton = screen.getByRole('button', { name: /promote.*b/i });

    expect(runRandomButton).toBeDisabled();
    expect(promoteButton).toBeDisabled();
  });
});

describe('PromptABTest delta indicator', () => {
  const defaultProps = {
    originalPrompt: 'Original',
    modifiedPrompt: 'Modified',
    results: [],
    isRunning: false,
    onRunTest: vi.fn(),
    onRunRandomTests: vi.fn(),
    onPromoteB: vi.fn(),
  };

  it('shows neutral color when delta is within +/-5', () => {
    const neutralResults: ABTestResult[] = [
      {
        eventId: 1,
        originalResult: {
          riskScore: 50,
          riskLevel: 'medium',
          reasoning: 'Original',
          processingTimeMs: 100,
        },
        modifiedResult: {
          riskScore: 52,
          riskLevel: 'medium',
          reasoning: 'Modified',
          processingTimeMs: 100,
        },
        scoreDelta: 2, // Within +/-5 threshold
      },
    ];

    render(<PromptABTest {...defaultProps} results={neutralResults} />);

    const deltaIndicator = screen.getByTestId('delta-indicator');
    // Should have neutral/gray styling
    expect(deltaIndicator).toHaveClass(/gray/);
  });
});

describe('PromptABTest multiple results', () => {
  const defaultProps = {
    originalPrompt: 'Original',
    modifiedPrompt: 'Modified',
    results: [],
    isRunning: false,
    onRunTest: vi.fn(),
    onRunRandomTests: vi.fn(),
    onPromoteB: vi.fn(),
  };

  it('displays multiple test results', () => {
    const multipleResults: ABTestResult[] = [
      {
        eventId: 1,
        originalResult: {
          riskScore: 60,
          riskLevel: 'high',
          reasoning: 'First original',
          processingTimeMs: 100,
        },
        modifiedResult: {
          riskScore: 40,
          riskLevel: 'medium',
          reasoning: 'First modified',
          processingTimeMs: 100,
        },
        scoreDelta: -20,
      },
      {
        eventId: 2,
        originalResult: {
          riskScore: 30,
          riskLevel: 'low',
          reasoning: 'Second original',
          processingTimeMs: 100,
        },
        modifiedResult: {
          riskScore: 25,
          riskLevel: 'low',
          reasoning: 'Second modified',
          processingTimeMs: 100,
        },
        scoreDelta: -5,
      },
    ];

    render(<PromptABTest {...defaultProps} results={multipleResults} />);

    // Should show both event IDs - getAllByText because each event appears in both panels
    expect(screen.getAllByText(/Event #1/)).toHaveLength(2); // Once in each panel
    expect(screen.getAllByText(/Event #2/)).toHaveLength(2); // Once in each panel
  });
});

describe('PromptABTest accessibility', () => {
  const defaultProps = {
    originalPrompt: 'Original',
    modifiedPrompt: 'Modified',
    results: [],
    isRunning: false,
    onRunTest: vi.fn(),
    onRunRandomTests: vi.fn(),
    onPromoteB: vi.fn(),
  };

  it('has appropriate ARIA labels for panels', () => {
    render(<PromptABTest {...defaultProps} />);

    // Panels should be accessible regions
    const leftPanel = screen.getByTestId('panel-original');
    const rightPanel = screen.getByTestId('panel-modified');

    expect(leftPanel).toHaveAttribute('aria-label', expect.stringMatching(/original/i));
    expect(rightPanel).toHaveAttribute('aria-label', expect.stringMatching(/modified/i));
  });
});

describe('PromptABTest className prop', () => {
  it('applies additional className', () => {
    render(
      <PromptABTest
        originalPrompt="Original"
        modifiedPrompt="Modified"
        results={[]}
        isRunning={false}
        onRunTest={vi.fn()}
        onRunRandomTests={vi.fn()}
        onPromoteB={vi.fn()}
        className="custom-class"
      />
    );

    const container = screen.getByTestId('prompt-ab-test');
    expect(container).toHaveClass('custom-class');
  });
});
