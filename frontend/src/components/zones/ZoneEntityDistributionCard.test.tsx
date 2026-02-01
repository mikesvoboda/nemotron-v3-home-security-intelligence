/**
 * Tests for ZoneEntityDistributionCard component (NEM-4937)
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { ZoneEntityDistributionCard } from './ZoneEntityDistributionCard';

import type { ZoneEntityDistribution } from '../../hooks/useZoneEntityDistribution';

// ============================================================================
// Test Data
// ============================================================================

const mockDistribution: ZoneEntityDistribution = {
  zone_id: 1,
  zone_name: 'Front Yard',
  total_entities: 64,
  entity_types: [
    { entity_type: 'person', count: 42, percentage: 65.63 },
    { entity_type: 'vehicle', count: 15, percentage: 23.44 },
    { entity_type: 'dog', count: 7, percentage: 10.94 },
  ],
};

const emptyDistribution: ZoneEntityDistribution = {
  zone_id: 2,
  zone_name: 'Empty Zone',
  total_entities: 0,
  entity_types: [],
};

// ============================================================================
// Tests
// ============================================================================

describe('ZoneEntityDistributionCard', () => {
  it('should render zone name and total count', () => {
    render(<ZoneEntityDistributionCard distribution={mockDistribution} />);

    expect(screen.getByText('Front Yard')).toBeInTheDocument();
    expect(screen.getByTestId('total-count')).toHaveTextContent('64 total');
  });

  it('should render all entity types with counts and percentages', () => {
    render(<ZoneEntityDistributionCard distribution={mockDistribution} />);

    // Check person row
    expect(screen.getByTestId('entity-type-person')).toBeInTheDocument();
    expect(screen.getByText('Person')).toBeInTheDocument();
    expect(screen.getByText('42')).toBeInTheDocument();
    expect(screen.getByText('(65.6%)')).toBeInTheDocument();

    // Check vehicle row
    expect(screen.getByTestId('entity-type-vehicle')).toBeInTheDocument();
    expect(screen.getByText('Vehicle')).toBeInTheDocument();
    expect(screen.getByText('15')).toBeInTheDocument();

    // Check dog row
    expect(screen.getByTestId('entity-type-dog')).toBeInTheDocument();
    expect(screen.getByText('Dog')).toBeInTheDocument();
    expect(screen.getByText('7')).toBeInTheDocument();
  });

  it('should render progress bars with correct widths', () => {
    render(<ZoneEntityDistributionCard distribution={mockDistribution} />);

    const personBar = screen.getByTestId('entity-bar-person');
    expect(personBar).toHaveStyle({ width: '65.63%' });

    const vehicleBar = screen.getByTestId('entity-bar-vehicle');
    expect(vehicleBar).toHaveStyle({ width: '23.44%' });

    const dogBar = screen.getByTestId('entity-bar-dog');
    expect(dogBar).toHaveStyle({ width: '10.94%' });
  });

  it('should show loading skeleton when isLoading', () => {
    render(<ZoneEntityDistributionCard distribution={mockDistribution} isLoading />);

    expect(screen.getByTestId('loading-skeleton')).toBeInTheDocument();
    expect(screen.queryByText('Front Yard')).not.toBeInTheDocument();
  });

  it('should show empty state when no entities', () => {
    render(<ZoneEntityDistributionCard distribution={emptyDistribution} />);

    expect(screen.getByTestId('empty-state')).toBeInTheDocument();
    expect(screen.getByText('No entities detected')).toBeInTheDocument();
  });

  it('should call onClick when clicked', () => {
    const handleClick = vi.fn();
    render(<ZoneEntityDistributionCard distribution={mockDistribution} onClick={handleClick} />);

    const card = screen.getByTestId('entity-distribution-card-1');
    fireEvent.click(card);

    expect(handleClick).toHaveBeenCalledWith(1);
  });

  it('should call onClick on Enter key press', () => {
    const handleClick = vi.fn();
    render(<ZoneEntityDistributionCard distribution={mockDistribution} onClick={handleClick} />);

    const card = screen.getByTestId('entity-distribution-card-1');
    fireEvent.keyDown(card, { key: 'Enter' });

    expect(handleClick).toHaveBeenCalledWith(1);
  });

  it('should call onClick on Space key press', () => {
    const handleClick = vi.fn();
    render(<ZoneEntityDistributionCard distribution={mockDistribution} onClick={handleClick} />);

    const card = screen.getByTestId('entity-distribution-card-1');
    fireEvent.keyDown(card, { key: ' ' });

    expect(handleClick).toHaveBeenCalledWith(1);
  });

  it('should apply selected styles when isSelected', () => {
    render(
      <ZoneEntityDistributionCard distribution={mockDistribution} onClick={() => {}} isSelected />
    );

    const card = screen.getByTestId('entity-distribution-card-1');
    expect(card).toHaveClass('border-[#76B900]');
    expect(card).toHaveAttribute('aria-pressed', 'true');
  });

  it('should be accessible with button role when clickable', () => {
    render(<ZoneEntityDistributionCard distribution={mockDistribution} onClick={() => {}} />);

    const card = screen.getByTestId('entity-distribution-card-1');
    expect(card).toHaveAttribute('role', 'button');
    expect(card).toHaveAttribute('tabIndex', '0');
  });

  it('should not have button role when not clickable', () => {
    render(<ZoneEntityDistributionCard distribution={mockDistribution} />);

    const card = screen.getByTestId('entity-distribution-card-1');
    expect(card).not.toHaveAttribute('role');
    expect(card).not.toHaveAttribute('tabIndex');
  });

  it('should apply custom className', () => {
    render(
      <ZoneEntityDistributionCard distribution={mockDistribution} className="custom-class" />
    );

    const card = screen.getByTestId('entity-distribution-card-1');
    expect(card).toHaveClass('custom-class');
  });
});
