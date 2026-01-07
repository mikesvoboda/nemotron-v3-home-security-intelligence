import { render, screen, fireEvent } from '@testing-library/react';
import { Camera, Clock, FileText, Users } from 'lucide-react';
import { describe, it, expect, vi } from 'vitest';

import EmptyState from './EmptyState';

describe('EmptyState', () => {
  describe('rendering', () => {
    it('renders with required props', () => {
      render(
        <EmptyState
          icon={Camera}
          title="No Cameras"
          description="No cameras have been configured yet."
        />
      );

      expect(screen.getByText('No Cameras')).toBeInTheDocument();
      expect(screen.getByText('No cameras have been configured yet.')).toBeInTheDocument();
      expect(screen.getByTestId('empty-state')).toBeInTheDocument();
    });

    it('renders icon correctly', () => {
      render(
        <EmptyState
          icon={Camera}
          title="No Cameras"
          description="No cameras found."
        />
      );

      // Icon should be present and hidden from accessibility
      const icon = screen.getByTestId('empty-state').querySelector('svg');
      expect(icon).toBeInTheDocument();
      expect(icon).toHaveAttribute('aria-hidden', 'true');
    });

    it('renders with custom testId', () => {
      render(
        <EmptyState
          icon={Clock}
          title="No Events"
          description="No events found."
          testId="custom-empty-state"
        />
      );

      expect(screen.getByTestId('custom-empty-state')).toBeInTheDocument();
    });

    it('renders description as ReactNode', () => {
      render(
        <EmptyState
          icon={Camera}
          title="Test"
          description={
            <div data-testid="custom-description">
              <strong>Custom</strong> description
            </div>
          }
        />
      );

      expect(screen.getByTestId('custom-description')).toBeInTheDocument();
      expect(screen.getByText('Custom')).toBeInTheDocument();
    });

    it('renders children content', () => {
      render(
        <EmptyState
          icon={Camera}
          title="Test"
          description="Description"
        >
          <div data-testid="child-content">Additional content</div>
        </EmptyState>
      );

      expect(screen.getByTestId('child-content')).toBeInTheDocument();
      expect(screen.getByText('Additional content')).toBeInTheDocument();
    });
  });

  describe('variants', () => {
    it('renders default variant with NVIDIA green accent', () => {
      render(
        <EmptyState
          icon={Camera}
          title="Test"
          description="Description"
          variant="default"
        />
      );

      const container = screen.getByTestId('empty-state');
      // Check for NVIDIA green color class on icon container
      const iconContainer = container.querySelector('.bg-\\[\\#76B900\\]\\/10');
      expect(iconContainer).toBeInTheDocument();
    });

    it('renders muted variant with gray accent', () => {
      render(
        <EmptyState
          icon={Clock}
          title="Test"
          description="Description"
          variant="muted"
        />
      );

      const container = screen.getByTestId('empty-state');
      const iconContainer = container.querySelector('.bg-gray-800');
      expect(iconContainer).toBeInTheDocument();
    });

    it('renders warning variant with yellow accent', () => {
      render(
        <EmptyState
          icon={FileText}
          title="Test"
          description="Description"
          variant="warning"
        />
      );

      const container = screen.getByTestId('empty-state');
      const iconContainer = container.querySelector('.bg-yellow-500\\/10');
      expect(iconContainer).toBeInTheDocument();
    });
  });

  describe('sizes', () => {
    it('renders small size', () => {
      render(
        <EmptyState
          icon={Camera}
          title="Test"
          description="Description"
          size="sm"
        />
      );

      const container = screen.getByTestId('empty-state');
      expect(container).toHaveClass('min-h-[200px]');
    });

    it('renders medium size (default)', () => {
      render(
        <EmptyState
          icon={Camera}
          title="Test"
          description="Description"
          size="md"
        />
      );

      const container = screen.getByTestId('empty-state');
      expect(container).toHaveClass('min-h-[300px]');
    });

    it('renders large size', () => {
      render(
        <EmptyState
          icon={Camera}
          title="Test"
          description="Description"
          size="lg"
        />
      );

      const container = screen.getByTestId('empty-state');
      expect(container).toHaveClass('min-h-[400px]');
    });
  });

  describe('actions', () => {
    it('renders single action button', () => {
      const handleClick = vi.fn();

      render(
        <EmptyState
          icon={Camera}
          title="Test"
          description="Description"
          actions={[{ label: 'Add Camera', onClick: handleClick }]}
        />
      );

      const button = screen.getByRole('button', { name: 'Add Camera' });
      expect(button).toBeInTheDocument();

      fireEvent.click(button);
      expect(handleClick).toHaveBeenCalledTimes(1);
    });

    it('renders multiple action buttons', () => {
      const handlePrimary = vi.fn();
      const handleSecondary = vi.fn();

      render(
        <EmptyState
          icon={Camera}
          title="Test"
          description="Description"
          actions={[
            { label: 'Primary Action', onClick: handlePrimary, variant: 'primary' },
            { label: 'Secondary Action', onClick: handleSecondary, variant: 'secondary' },
          ]}
        />
      );

      expect(screen.getByRole('button', { name: 'Primary Action' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Secondary Action' })).toBeInTheDocument();
    });

    it('renders primary variant with NVIDIA green background', () => {
      render(
        <EmptyState
          icon={Camera}
          title="Test"
          description="Description"
          actions={[{ label: 'Primary', onClick: vi.fn(), variant: 'primary' }]}
        />
      );

      const button = screen.getByRole('button', { name: 'Primary' });
      expect(button).toHaveClass('bg-[#76B900]');
    });

    it('renders secondary variant with gray border', () => {
      render(
        <EmptyState
          icon={Camera}
          title="Test"
          description="Description"
          actions={[{ label: 'Secondary', onClick: vi.fn(), variant: 'secondary' }]}
        />
      );

      const button = screen.getByRole('button', { name: 'Secondary' });
      expect(button).toHaveClass('border-gray-700');
    });

    it('does not render actions section when no actions provided', () => {
      render(
        <EmptyState
          icon={Camera}
          title="Test"
          description="Description"
        />
      );

      expect(screen.queryByRole('button')).not.toBeInTheDocument();
    });
  });

  describe('className', () => {
    it('applies additional className', () => {
      render(
        <EmptyState
          icon={Camera}
          title="Test"
          description="Description"
          className="custom-class"
        />
      );

      expect(screen.getByTestId('empty-state')).toHaveClass('custom-class');
    });
  });

  describe('accessibility', () => {
    it('has correct heading hierarchy', () => {
      render(
        <EmptyState
          icon={Users}
          title="No Users Found"
          description="No users match the current filters."
        />
      );

      const heading = screen.getByRole('heading', { level: 2, name: 'No Users Found' });
      expect(heading).toBeInTheDocument();
    });

    it('icon is hidden from screen readers', () => {
      render(
        <EmptyState
          icon={Camera}
          title="Test"
          description="Description"
        />
      );

      const icon = screen.getByTestId('empty-state').querySelector('svg');
      expect(icon).toHaveAttribute('aria-hidden', 'true');
    });
  });

  describe('dark theme compatibility', () => {
    it('uses dark theme colors for text', () => {
      render(
        <EmptyState
          icon={Camera}
          title="Test Title"
          description="Test description"
        />
      );

      const title = screen.getByText('Test Title');
      expect(title).toHaveClass('text-white');

      const container = screen.getByTestId('empty-state');
      const description = container.querySelector('.text-gray-400');
      expect(description).toBeInTheDocument();
    });
  });
});
