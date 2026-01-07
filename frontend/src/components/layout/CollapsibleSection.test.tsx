import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';

import CollapsibleSection from './CollapsibleSection';

describe('CollapsibleSection', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('renders with title and children when expanded', () => {
    render(
      <CollapsibleSection title="Test Section" storageKey="test-section">
        <div>Test Content</div>
      </CollapsibleSection>
    );

    expect(screen.getByText('Test Section')).toBeInTheDocument();
    expect(screen.getByText('Test Content')).toBeInTheDocument();
  });

  it('starts expanded by default when defaultExpanded is true', () => {
    render(
      <CollapsibleSection title="Test Section" storageKey="test-section" defaultExpanded={true}>
        <div>Test Content</div>
      </CollapsibleSection>
    );

    expect(screen.getByText('Test Content')).toBeInTheDocument();
  });

  it('starts collapsed when defaultExpanded is false', () => {
    render(
      <CollapsibleSection title="Test Section" storageKey="test-section" defaultExpanded={false}>
        <div>Test Content</div>
      </CollapsibleSection>
    );

    expect(screen.queryByText('Test Content')).not.toBeInTheDocument();
  });

  it('toggles expanded state on button click', () => {
    render(
      <CollapsibleSection title="Test Section" storageKey="test-section" defaultExpanded={true}>
        <div>Test Content</div>
      </CollapsibleSection>
    );

    const button = screen.getByRole('button', { name: /test section/i });

    // Initially expanded
    expect(screen.getByText('Test Content')).toBeInTheDocument();

    // Click to collapse
    fireEvent.click(button);
    expect(screen.queryByText('Test Content')).not.toBeInTheDocument();

    // Click to expand
    fireEvent.click(button);
    expect(screen.getByText('Test Content')).toBeInTheDocument();
  });

  it('persists collapsed state to localStorage', () => {
    render(
      <CollapsibleSection title="Test Section" storageKey="test-section" defaultExpanded={true}>
        <div>Test Content</div>
      </CollapsibleSection>
    );

    const button = screen.getByRole('button', { name: /test section/i });

    // Collapse section
    fireEvent.click(button);

    // Check localStorage
    const stored = localStorage.getItem('collapsible-test-section');
    expect(stored).toBe('false');
  });

  it('persists expanded state to localStorage', () => {
    render(
      <CollapsibleSection title="Test Section" storageKey="test-section" defaultExpanded={false}>
        <div>Test Content</div>
      </CollapsibleSection>
    );

    const button = screen.getByRole('button', { name: /test section/i });

    // Expand section
    fireEvent.click(button);

    // Check localStorage
    const stored = localStorage.getItem('collapsible-test-section');
    expect(stored).toBe('true');
  });

  it('restores state from localStorage on mount', () => {
    // Set collapsed state in localStorage
    localStorage.setItem('collapsible-test-section', 'false');

    render(
      <CollapsibleSection title="Test Section" storageKey="test-section" defaultExpanded={true}>
        <div>Test Content</div>
      </CollapsibleSection>
    );

    // Should be collapsed despite defaultExpanded=true
    expect(screen.queryByText('Test Content')).not.toBeInTheDocument();
  });

  it('uses different storage keys for different sections', () => {
    const { rerender } = render(
      <CollapsibleSection title="Section 1" storageKey="section-1" defaultExpanded={true}>
        <div>Content 1</div>
      </CollapsibleSection>
    );

    const button1 = screen.getByRole('button', { name: /section 1/i });
    fireEvent.click(button1);

    // Check first section's storage
    expect(localStorage.getItem('collapsible-section-1')).toBe('false');

    // Render second section
    rerender(
      <CollapsibleSection title="Section 2" storageKey="section-2" defaultExpanded={false}>
        <div>Content 2</div>
      </CollapsibleSection>
    );

    const button2 = screen.getByRole('button', { name: /section 2/i });
    fireEvent.click(button2);

    // Check second section's storage
    expect(localStorage.getItem('collapsible-section-2')).toBe('true');

    // First section's storage should be unchanged
    expect(localStorage.getItem('collapsible-section-1')).toBe('false');
  });

  it('displays chevron down icon when expanded', () => {
    render(
      <CollapsibleSection title="Test Section" storageKey="test-section" defaultExpanded={true}>
        <div>Test Content</div>
      </CollapsibleSection>
    );

    const button = screen.getByRole('button', { name: /test section/i });
    expect(button.querySelector('[class*="lucide-chevron-down"]')).toBeInTheDocument();
  });

  it('displays chevron right icon when collapsed', () => {
    render(
      <CollapsibleSection title="Test Section" storageKey="test-section" defaultExpanded={false}>
        <div>Test Content</div>
      </CollapsibleSection>
    );

    const button = screen.getByRole('button', { name: /test section/i });
    expect(button.querySelector('[class*="lucide-chevron-right"]')).toBeInTheDocument();
  });

  it('has proper aria-expanded attribute', () => {
    render(
      <CollapsibleSection title="Test Section" storageKey="test-section" defaultExpanded={true}>
        <div>Test Content</div>
      </CollapsibleSection>
    );

    const button = screen.getByRole('button', { name: /test section/i });
    expect(button).toHaveAttribute('aria-expanded', 'true');

    fireEvent.click(button);
    expect(button).toHaveAttribute('aria-expanded', 'false');
  });

  it('applies custom className to container', () => {
    const { container } = render(
      <CollapsibleSection
        title="Test Section"
        storageKey="test-section"
        className="custom-class"
      >
        <div>Test Content</div>
      </CollapsibleSection>
    );

    expect(container.firstChild).toHaveClass('custom-class');
  });

  it('is keyboard accessible with proper button semantics', () => {
    render(
      <CollapsibleSection title="Test Section" storageKey="test-section" defaultExpanded={true}>
        <div>Test Content</div>
      </CollapsibleSection>
    );

    const button = screen.getByRole('button', { name: /test section/i });

    // Button should be keyboard focusable
    expect(button).toHaveAttribute('type', 'button');

    // Aria-expanded should be set
    expect(button).toHaveAttribute('aria-expanded', 'true');

    // Button should have aria-controls
    expect(button).toHaveAttribute('aria-controls');
  });
});
