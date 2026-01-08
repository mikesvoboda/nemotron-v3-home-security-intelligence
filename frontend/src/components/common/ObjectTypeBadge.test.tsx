import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import ObjectTypeBadge from './ObjectTypeBadge';

describe('ObjectTypeBadge', () => {
  describe('basic rendering', () => {
    it('renders badge with type label', () => {
      render(<ObjectTypeBadge type="person" />);
      expect(screen.getByRole('status')).toBeInTheDocument();
      expect(screen.getByText('Person')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      const { container } = render(<ObjectTypeBadge type="person" className="custom-class" />);
      const badge = container.querySelector('[role="status"]');
      expect(badge).toHaveClass('custom-class');
    });

    it('merges custom className with default classes', () => {
      const { container } = render(<ObjectTypeBadge type="person" className="ml-2" />);
      const badge = container.querySelector('[role="status"]');
      expect(badge).toHaveClass('ml-2', 'inline-flex', 'items-center');
    });
  });

  describe('object type display names', () => {
    it('displays "Person" for person type', () => {
      render(<ObjectTypeBadge type="person" />);
      expect(screen.getByText('Person')).toBeInTheDocument();
    });

    it('displays "Vehicle" for car type', () => {
      render(<ObjectTypeBadge type="car" />);
      expect(screen.getByText('Vehicle')).toBeInTheDocument();
    });

    it('displays "Vehicle" for truck type', () => {
      render(<ObjectTypeBadge type="truck" />);
      expect(screen.getByText('Vehicle')).toBeInTheDocument();
    });

    it('displays "Vehicle" for bus type', () => {
      render(<ObjectTypeBadge type="bus" />);
      expect(screen.getByText('Vehicle')).toBeInTheDocument();
    });

    it('displays "Vehicle" for motorcycle type', () => {
      render(<ObjectTypeBadge type="motorcycle" />);
      expect(screen.getByText('Vehicle')).toBeInTheDocument();
    });

    it('displays "Bicycle" for bicycle type', () => {
      render(<ObjectTypeBadge type="bicycle" />);
      expect(screen.getByText('Bicycle')).toBeInTheDocument();
    });

    it('displays "Animal" for dog type', () => {
      render(<ObjectTypeBadge type="dog" />);
      expect(screen.getByText('Animal')).toBeInTheDocument();
    });

    it('displays "Animal" for cat type', () => {
      render(<ObjectTypeBadge type="cat" />);
      expect(screen.getByText('Animal')).toBeInTheDocument();
    });

    it('displays "Animal" for bird type', () => {
      render(<ObjectTypeBadge type="bird" />);
      expect(screen.getByText('Animal')).toBeInTheDocument();
    });

    it('displays "Package" for package type', () => {
      render(<ObjectTypeBadge type="package" />);
      expect(screen.getByText('Package')).toBeInTheDocument();
    });
  });

  describe('case insensitivity', () => {
    it('handles uppercase input', () => {
      render(<ObjectTypeBadge type="PERSON" />);
      expect(screen.getByText('Person')).toBeInTheDocument();
    });

    it('handles mixed case input', () => {
      render(<ObjectTypeBadge type="PeRsOn" />);
      expect(screen.getByText('Person')).toBeInTheDocument();
    });

    it('handles lowercase input', () => {
      render(<ObjectTypeBadge type="person" />);
      expect(screen.getByText('Person')).toBeInTheDocument();
    });

    it('handles input with whitespace', () => {
      render(<ObjectTypeBadge type=" person " />);
      expect(screen.getByText('Person')).toBeInTheDocument();
    });
  });

  describe('unknown object types', () => {
    it('displays capitalized type name for unknown types', () => {
      render(<ObjectTypeBadge type="unknown" />);
      expect(screen.getByText('Unknown')).toBeInTheDocument();
    });

    it('capitalizes first letter of unknown type', () => {
      render(<ObjectTypeBadge type="custom" />);
      expect(screen.getByText('Custom')).toBeInTheDocument();
    });

    it('preserves rest of string case for unknown types', () => {
      render(<ObjectTypeBadge type="customObject" />);
      expect(screen.getByText('CustomObject')).toBeInTheDocument();
    });
  });

  describe('color coding', () => {
    it('applies blue colors for person type', () => {
      const { container } = render(<ObjectTypeBadge type="person" />);
      const badge = container.querySelector('[role="status"]');
      expect(badge).toHaveClass('bg-blue-500/10', 'text-blue-400');
    });

    it('applies purple colors for vehicle types', () => {
      const { container } = render(<ObjectTypeBadge type="car" />);
      const badge = container.querySelector('[role="status"]');
      expect(badge).toHaveClass('bg-purple-500/10', 'text-purple-400');
    });

    it('applies cyan colors for bicycle type', () => {
      const { container } = render(<ObjectTypeBadge type="bicycle" />);
      const badge = container.querySelector('[role="status"]');
      expect(badge).toHaveClass('bg-cyan-500/10', 'text-cyan-400');
    });

    it('applies amber colors for animal types', () => {
      const { container } = render(<ObjectTypeBadge type="dog" />);
      const badge = container.querySelector('[role="status"]');
      expect(badge).toHaveClass('bg-amber-500/10', 'text-amber-400');
    });

    it('applies green colors for package type', () => {
      const { container } = render(<ObjectTypeBadge type="package" />);
      const badge = container.querySelector('[role="status"]');
      expect(badge).toHaveClass('bg-green-500/10', 'text-green-400');
    });

    it('applies gray colors for unknown types', () => {
      const { container } = render(<ObjectTypeBadge type="unknown" />);
      const badge = container.querySelector('[role="status"]');
      expect(badge).toHaveClass('bg-gray-500/10', 'text-gray-400');
    });
  });

  describe('icons', () => {
    it('renders User icon for person type', () => {
      const { container } = render(<ObjectTypeBadge type="person" />);
      const icon = container.querySelector('svg.lucide-user');
      expect(icon).toBeInTheDocument();
    });

    it('renders Car icon for vehicle types', () => {
      const { container } = render(<ObjectTypeBadge type="car" />);
      const icon = container.querySelector('svg.lucide-car');
      expect(icon).toBeInTheDocument();
    });

    it('renders PawPrint icon for animal types', () => {
      const { container } = render(<ObjectTypeBadge type="dog" />);
      const icon = container.querySelector('svg.lucide-paw-print');
      expect(icon).toBeInTheDocument();
    });

    it('renders Package icon for package type', () => {
      const { container } = render(<ObjectTypeBadge type="package" />);
      const icon = container.querySelector('svg.lucide-package');
      expect(icon).toBeInTheDocument();
    });

    it('renders AlertTriangle icon for unknown types', () => {
      const { container } = render(<ObjectTypeBadge type="unknown" />);
      const icon = container.querySelector('svg.lucide-triangle-alert');
      expect(icon).toBeInTheDocument();
    });

    it('marks icon as aria-hidden', () => {
      const { container } = render(<ObjectTypeBadge type="person" />);
      const icon = container.querySelector('svg[aria-hidden="true"]');
      expect(icon).toBeInTheDocument();
    });
  });

  describe('size variants', () => {
    it('applies small size classes when size="sm"', () => {
      const { container } = render(<ObjectTypeBadge type="person" size="sm" />);
      const badge = container.querySelector('[role="status"]');
      expect(badge).toHaveClass('text-xs', 'px-2', 'py-0.5');
    });

    it('applies medium size classes when size="md"', () => {
      const { container } = render(<ObjectTypeBadge type="person" size="md" />);
      const badge = container.querySelector('[role="status"]');
      expect(badge).toHaveClass('text-sm', 'px-2.5', 'py-1');
    });

    it('applies large size classes when size="lg"', () => {
      const { container } = render(<ObjectTypeBadge type="person" size="lg" />);
      const badge = container.querySelector('[role="status"]');
      expect(badge).toHaveClass('text-base', 'px-3', 'py-1.5');
    });

    it('defaults to small size when size prop is omitted', () => {
      const { container } = render(<ObjectTypeBadge type="person" />);
      const badge = container.querySelector('[role="status"]');
      expect(badge).toHaveClass('text-xs');
    });

    it('applies correct icon size for sm', () => {
      const { container } = render(<ObjectTypeBadge type="person" size="sm" />);
      const icon = container.querySelector('svg');
      expect(icon).toHaveClass('w-3', 'h-3');
    });

    it('applies correct icon size for md', () => {
      const { container } = render(<ObjectTypeBadge type="person" size="md" />);
      const icon = container.querySelector('svg');
      expect(icon).toHaveClass('w-4', 'h-4');
    });

    it('applies correct icon size for lg', () => {
      const { container } = render(<ObjectTypeBadge type="person" size="lg" />);
      const icon = container.querySelector('svg');
      expect(icon).toHaveClass('w-5', 'h-5');
    });
  });

  describe('accessibility', () => {
    it('has role="status"', () => {
      render(<ObjectTypeBadge type="person" />);
      expect(screen.getByRole('status')).toBeInTheDocument();
    });

    it('has descriptive aria-label for person', () => {
      render(<ObjectTypeBadge type="person" />);
      const badge = screen.getByRole('status');
      expect(badge).toHaveAttribute('aria-label', 'Detected object: Person');
    });

    it('has descriptive aria-label for vehicle', () => {
      render(<ObjectTypeBadge type="car" />);
      const badge = screen.getByRole('status');
      expect(badge).toHaveAttribute('aria-label', 'Detected object: Vehicle');
    });

    it('has descriptive aria-label for animal', () => {
      render(<ObjectTypeBadge type="dog" />);
      const badge = screen.getByRole('status');
      expect(badge).toHaveAttribute('aria-label', 'Detected object: Animal');
    });

    it('has descriptive aria-label for unknown types', () => {
      render(<ObjectTypeBadge type="customType" />);
      const badge = screen.getByRole('status');
      expect(badge).toHaveAttribute('aria-label', 'Detected object: CustomType');
    });
  });

  describe('layout and styling', () => {
    it('applies rounded-full class', () => {
      const { container } = render(<ObjectTypeBadge type="person" />);
      const badge = container.querySelector('[role="status"]');
      expect(badge).toHaveClass('rounded-full');
    });

    it('applies border class', () => {
      const { container } = render(<ObjectTypeBadge type="person" />);
      const badge = container.querySelector('[role="status"]');
      expect(badge).toHaveClass('border');
    });

    it('applies font-medium class', () => {
      const { container } = render(<ObjectTypeBadge type="person" />);
      const badge = container.querySelector('[role="status"]');
      expect(badge).toHaveClass('font-medium');
    });

    it('applies inline-flex layout', () => {
      const { container } = render(<ObjectTypeBadge type="person" />);
      const badge = container.querySelector('[role="status"]');
      expect(badge).toHaveClass('inline-flex', 'items-center');
    });

    it('applies gap between icon and text', () => {
      const { container } = render(<ObjectTypeBadge type="person" />);
      const badge = container.querySelector('[role="status"]');
      expect(badge).toHaveClass('gap-1');
    });
  });

  describe('multiple types', () => {
    it('renders multiple badges with different types', () => {
      const { container } = render(
        <>
          <ObjectTypeBadge type="person" />
          <ObjectTypeBadge type="car" />
          <ObjectTypeBadge type="dog" />
        </>
      );
      expect(screen.getByText('Person')).toBeInTheDocument();
      expect(screen.getByText('Vehicle')).toBeInTheDocument();
      expect(screen.getByText('Animal')).toBeInTheDocument();
      expect(container.querySelectorAll('[role="status"]')).toHaveLength(3);
    });
  });

  describe('edge cases', () => {
    it('handles empty string type', () => {
      render(<ObjectTypeBadge type="" />);
      const badge = screen.getByRole('status');
      expect(badge).toBeInTheDocument();
    });

    it('handles type with only whitespace', () => {
      render(<ObjectTypeBadge type="   " />);
      const badge = screen.getByRole('status');
      expect(badge).toBeInTheDocument();
    });

    it('handles type with special characters', () => {
      render(<ObjectTypeBadge type="test-type" />);
      expect(screen.getByText('Test-type')).toBeInTheDocument();
    });

    it('handles type with numbers', () => {
      render(<ObjectTypeBadge type="type123" />);
      expect(screen.getByText('Type123')).toBeInTheDocument();
    });

    it('handles very long type names', () => {
      const longType = 'verylongobjecttypename';
      render(<ObjectTypeBadge type={longType} />);
      expect(screen.getByText('Verylongobjecttypename')).toBeInTheDocument();
    });
  });

  describe('snapshots', () => {
    it('renders person type with icon and styling', () => {
      const { container } = render(<ObjectTypeBadge type="person" />);
      expect(container.firstChild).toMatchSnapshot();
    });

    it('renders vehicle type (car) with icon and styling', () => {
      const { container } = render(<ObjectTypeBadge type="car" />);
      expect(container.firstChild).toMatchSnapshot();
    });

    it('renders bicycle type with icon and styling', () => {
      const { container } = render(<ObjectTypeBadge type="bicycle" />);
      expect(container.firstChild).toMatchSnapshot();
    });

    it('renders animal type (dog) with icon and styling', () => {
      const { container } = render(<ObjectTypeBadge type="dog" />);
      expect(container.firstChild).toMatchSnapshot();
    });

    it('renders package type with icon and styling', () => {
      const { container } = render(<ObjectTypeBadge type="package" />);
      expect(container.firstChild).toMatchSnapshot();
    });

    it('renders unknown type with icon and styling', () => {
      const { container } = render(<ObjectTypeBadge type="unknown_object" />);
      expect(container.firstChild).toMatchSnapshot();
    });

    it.each(['sm', 'md', 'lg'] as const)('renders %s size variant correctly', (size) => {
      const { container } = render(<ObjectTypeBadge type="person" size={size} />);
      expect(container.firstChild).toMatchSnapshot();
    });

    it('renders with custom className', () => {
      const { container } = render(
        <ObjectTypeBadge type="car" className="custom-badge ml-2" />
      );
      expect(container.firstChild).toMatchSnapshot();
    });

    it('renders case-insensitive input (PERSON)', () => {
      const { container } = render(<ObjectTypeBadge type="PERSON" />);
      expect(container.firstChild).toMatchSnapshot();
    });
  });
});
