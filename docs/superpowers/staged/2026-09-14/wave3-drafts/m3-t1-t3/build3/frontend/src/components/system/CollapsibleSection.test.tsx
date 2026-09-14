import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AlertTriangle } from 'lucide-react';
import { describe, it, expect, vi } from 'vitest';

import CollapsibleSection from './CollapsibleSection';

describe('CollapsibleSection', () => {
  it('renders title and content', () => {
    render(
      <CollapsibleSection title="Test Section" defaultOpen={true}>
        <div>Test Content</div>
      </CollapsibleSection>
    );

    expect(screen.getByText('Test Section')).toBeInTheDocument();
    expect(screen.getByText('Test Content')).toBeInTheDocument();
  });

  it('renders icon when provided', () => {
    render(
      <CollapsibleSection
        title="Test Section"
        icon={<AlertTriangle data-testid="test-icon" />}
        defaultOpen={true}
      >
        <div>Test Content</div>
      </CollapsibleSection>
    );

    expect(screen.getByTestId('test-icon')).toBeInTheDocument();
  });

  it('starts collapsed by default', () => {
    render(
      <CollapsibleSection title="Test Section">
        <div>Test Content</div>
      </CollapsibleSection>
    );

    // Content should not be visible initially
    expect(screen.queryByText('Test Content')).not.toBeInTheDocument();
  });

  it('starts expanded when defaultOpen is true', () => {
    render(
      <CollapsibleSection title="Test Section" defaultOpen={true}>
        <div>Test Content</div>
      </CollapsibleSection>
    );

    expect(screen.getByText('Test Content')).toBeInTheDocument();
  });

  it('toggles visibility when clicked', async () => {
    const user = userEvent.setup();

    render(
      <CollapsibleSection title="Test Section">
        <div data-testid="test-content">Test Content</div>
      </CollapsibleSection>
    );

    const button = screen.getByRole('button', { name: /test section/i });

    // Should start collapsed (aria-expanded should be false)
    expect(button).toHaveAttribute('aria-expanded', 'false');

    // Click to expand
    await user.click(button);
    expect(button).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByTestId('test-content')).toBeInTheDocument();

    // Click to collapse
    await user.click(button);
    expect(button).toHaveAttribute('aria-expanded', 'false');
    // Note: The content may still be in DOM during transition, so we check aria-expanded instead
  });

  it('supports controlled mode with isOpen prop', async () => {
    const user = userEvent.setup();
    const onToggle = vi.fn();

    const { rerender } = render(
      <CollapsibleSection title="Test Section" isOpen={false} onToggle={onToggle}>
        <div>Test Content</div>
      </CollapsibleSection>
    );

    // Should start collapsed
    expect(screen.queryByText('Test Content')).not.toBeInTheDocument();

    // Click should call onToggle
    const button = screen.getByRole('button', { name: /test section/i });
    await user.click(button);
    expect(onToggle).toHaveBeenCalledWith(true);

    // Rerender with isOpen=true to simulate parent updating state
    rerender(
      <CollapsibleSection title="Test Section" isOpen={true} onToggle={onToggle}>
        <div>Test Content</div>
      </CollapsibleSection>
    );

    expect(screen.getByText('Test Content')).toBeInTheDocument();
  });

  it('renders summary badge when provided', () => {
    render(
      <CollapsibleSection
        title="Test Section"
        summary={<span>6/7 Healthy</span>}
        defaultOpen={true}
      >
        <div>Test Content</div>
      </CollapsibleSection>
    );

    expect(screen.getByText('6/7 Healthy')).toBeInTheDocument();
  });

  it('renders alert badge when provided', () => {
    render(
      <CollapsibleSection
        title="Test Section"
        alertBadge={<span data-testid="alert-badge">Alert!</span>}
        defaultOpen={true}
      >
        <div>Test Content</div>
      </CollapsibleSection>
    );

    expect(screen.getByTestId('alert-badge')).toBeInTheDocument();
  });

  it('applies custom className', () => {
    const { container } = render(
      <CollapsibleSection title="Test Section" className="custom-class">
        <div>Test Content</div>
      </CollapsibleSection>
    );

    expect(container.querySelector('.custom-class')).toBeInTheDocument();
  });

  it('applies data-testid correctly', () => {
    render(
      <CollapsibleSection title="Test Section" data-testid="custom-section" defaultOpen={true}>
        <div>Test Content</div>
      </CollapsibleSection>
    );

    expect(screen.getByTestId('custom-section-toggle')).toBeInTheDocument();
  });

  it('has correct ARIA attributes', () => {
    render(
      <CollapsibleSection title="Test Section" defaultOpen={false}>
        <div>Test Content</div>
      </CollapsibleSection>
    );

    const button = screen.getByRole('button', { name: /test section/i });
    expect(button).toHaveAttribute('aria-expanded', 'false');
  });

  it('updates ARIA attributes when expanded', () => {
    render(
      <CollapsibleSection title="Test Section" defaultOpen={true}>
        <div>Test Content</div>
      </CollapsibleSection>
    );

    const button = screen.getByRole('button', { name: /test section/i });
    expect(button).toHaveAttribute('aria-expanded', 'true');
  });
});
