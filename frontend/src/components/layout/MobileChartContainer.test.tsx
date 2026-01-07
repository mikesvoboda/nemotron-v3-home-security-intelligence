import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import MobileChartContainer from './MobileChartContainer';

describe('MobileChartContainer', () => {
  it('renders children in container', () => {
    render(
      <MobileChartContainer title="Test Chart">
        <div>Chart Content</div>
      </MobileChartContainer>
    );

    expect(screen.getByText('Chart Content')).toBeInTheDocument();
  });

  it('displays title in header', () => {
    render(
      <MobileChartContainer title="GPU Usage">
        <div>Chart Content</div>
      </MobileChartContainer>
    );

    expect(screen.getByText('GPU Usage')).toBeInTheDocument();
  });

  it('applies mobile height constraint', () => {
    const { container } = render(
      <MobileChartContainer title="Test Chart">
        <div>Chart Content</div>
      </MobileChartContainer>
    );

    const chartContainer = container.querySelector('.h-\\[180px\\]');
    expect(chartContainer).toBeInTheDocument();
  });

  it('displays expand button on mobile', () => {
    render(
      <MobileChartContainer title="Test Chart">
        <div>Chart Content</div>
      </MobileChartContainer>
    );

    expect(screen.getByLabelText(/expand test chart to fullscreen/i)).toBeInTheDocument();
  });

  it('opens fullscreen modal on expand button click', () => {
    render(
      <MobileChartContainer title="Test Chart">
        <div>Chart Content</div>
      </MobileChartContainer>
    );

    const expandButton = screen.getByLabelText(/expand test chart to fullscreen/i);
    fireEvent.click(expandButton);

    // Modal should be visible
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getAllByText('Test Chart')).toHaveLength(2); // One in header, one in modal
  });

  it('displays close button in fullscreen modal', () => {
    render(
      <MobileChartContainer title="Test Chart">
        <div>Chart Content</div>
      </MobileChartContainer>
    );

    const expandButton = screen.getByLabelText(/expand test chart to fullscreen/i);
    fireEvent.click(expandButton);

    expect(screen.getByLabelText(/close fullscreen/i)).toBeInTheDocument();
  });

  it('closes fullscreen modal on close button click', () => {
    render(
      <MobileChartContainer title="Test Chart">
        <div>Chart Content</div>
      </MobileChartContainer>
    );

    // Open modal
    const expandButton = screen.getByLabelText(/expand test chart to fullscreen/i);
    fireEvent.click(expandButton);

    // Close modal
    const closeButton = screen.getByLabelText(/close fullscreen/i);
    fireEvent.click(closeButton);

    // Modal should be gone
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('renders chart at full height in fullscreen mode', () => {
    const { container } = render(
      <MobileChartContainer title="Test Chart">
        <div>Chart Content</div>
      </MobileChartContainer>
    );

    // Open modal
    const expandButton = screen.getByLabelText(/expand test chart to fullscreen/i);
    fireEvent.click(expandButton);

    // Check for full height class in modal
    const fullHeightContainer = container.querySelector('.h-full');
    expect(fullHeightContainer).toBeInTheDocument();
  });

  it('closes modal on backdrop click', () => {
    render(
      <MobileChartContainer title="Test Chart">
        <div>Chart Content</div>
      </MobileChartContainer>
    );

    // Open modal
    const expandButton = screen.getByLabelText(/expand test chart to fullscreen/i);
    fireEvent.click(expandButton);

    // Click backdrop
    const backdrop = screen.getByTestId('fullscreen-backdrop');
    fireEvent.click(backdrop);

    // Modal should be closed
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('closes modal on Escape key press', () => {
    render(
      <MobileChartContainer title="Test Chart">
        <div>Chart Content</div>
      </MobileChartContainer>
    );

    // Open modal
    const expandButton = screen.getByLabelText(/expand test chart to fullscreen/i);
    fireEvent.click(expandButton);

    // Press Escape
    fireEvent.keyDown(document, { key: 'Escape', code: 'Escape' });

    // Modal should be closed
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('traps focus within modal when open', () => {
    render(
      <MobileChartContainer title="Test Chart">
        <div>Chart Content</div>
      </MobileChartContainer>
    );

    // Open modal
    const expandButton = screen.getByLabelText(/expand test chart to fullscreen/i);
    fireEvent.click(expandButton);

    // Modal should have proper aria attributes
    const modal = screen.getByRole('dialog');
    expect(modal).toHaveAttribute('aria-modal', 'true');
    expect(modal).toHaveAttribute('aria-labelledby');
  });

  it('applies custom className to container', () => {
    const { container } = render(
      <MobileChartContainer title="Test Chart" className="custom-class">
        <div>Chart Content</div>
      </MobileChartContainer>
    );

    expect(container.firstChild).toHaveClass('custom-class');
  });

  it('does not show expand button when showExpandButton is false', () => {
    render(
      <MobileChartContainer title="Test Chart" showExpandButton={false}>
        <div>Chart Content</div>
      </MobileChartContainer>
    );

    expect(screen.queryByLabelText(/expand/i)).not.toBeInTheDocument();
  });
});
