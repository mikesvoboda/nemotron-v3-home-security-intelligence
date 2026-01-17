/**
 * Tests for SeedRow component
 *
 * Tests the row component for seeding data with count selection.
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';

import SeedRow from './SeedRow';

describe('SeedRow', () => {
  const defaultProps = {
    label: 'Cameras',
    options: [5, 10, 25, 50] as const,
    defaultValue: 10,
    onSeed: vi.fn().mockResolvedValue(undefined),
    isLoading: false,
  };

  it('should render label and seed button', () => {
    render(<SeedRow {...defaultProps} />);

    expect(screen.getByText('Cameras')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /seed cameras/i })).toBeInTheDocument();
  });

  it('should render count dropdown with options', () => {
    render(<SeedRow {...defaultProps} />);

    // Find the select/combobox
    const select = screen.getByRole('combobox');
    expect(select).toBeInTheDocument();

    // The select should show the default value (using getAllByText since it appears multiple places)
    const defaultValues = screen.getAllByText('10');
    expect(defaultValues.length).toBeGreaterThan(0);
  });

  it('should call onSeed with selected count when button is clicked', async () => {
    const user = userEvent.setup();
    const onSeed = vi.fn().mockResolvedValue(undefined);
    render(<SeedRow {...defaultProps} onSeed={onSeed} />);

    const button = screen.getByRole('button', { name: /seed cameras/i });
    await user.click(button);

    await waitFor(() => {
      expect(onSeed).toHaveBeenCalledWith(10);
    });
  });

  it('should disable button while loading', () => {
    render(<SeedRow {...defaultProps} isLoading={true} />);

    const button = screen.getByRole('button', { name: /seeding/i });
    expect(button).toBeDisabled();
  });

  it('should show loading text while loading', () => {
    render(<SeedRow {...defaultProps} isLoading={true} />);

    expect(screen.getByText(/seeding/i)).toBeInTheDocument();
  });

  it('should disable dropdown while loading', () => {
    render(<SeedRow {...defaultProps} isLoading={true} />);

    const select = screen.getByRole('combobox');
    expect(select).toBeDisabled();
  });

  it('should support custom button text', () => {
    render(
      <SeedRow
        {...defaultProps}
        buttonText="Create Cameras"
        loadingText="Creating..."
      />
    );

    expect(screen.getByRole('button', { name: /create cameras/i })).toBeInTheDocument();
  });

  it('should show custom loading text', () => {
    render(
      <SeedRow
        {...defaultProps}
        buttonText="Create Cameras"
        loadingText="Creating..."
        isLoading={true}
      />
    );

    expect(screen.getByText(/creating/i)).toBeInTheDocument();
  });

  it('should render with description', () => {
    render(
      <SeedRow
        {...defaultProps}
        description="Creates test cameras in the database"
      />
    );

    expect(screen.getByText('Creates test cameras in the database')).toBeInTheDocument();
  });
});
