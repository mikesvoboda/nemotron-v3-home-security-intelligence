import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import AccessViolationBadge, {
  AccessViolationIcon,
  isWithinSchedule,
} from './AccessViolationBadge';

import type { WeeklySchedule } from '../../hooks/useHouseholdApi';

describe('AccessViolationBadge', () => {
  const businessHoursSchedule: WeeklySchedule = {
    monday: [9, 10, 11, 12, 13, 14, 15, 16, 17],
    tuesday: [9, 10, 11, 12, 13, 14, 15, 16, 17],
    wednesday: [9, 10, 11, 12, 13, 14, 15, 16, 17],
    thursday: [9, 10, 11, 12, 13, 14, 15, 16, 17],
    friday: [9, 10, 11, 12, 13, 14, 15, 16, 17],
    saturday: [],
    sunday: [],
  };

  describe('Rendering', () => {
    it('renders badge when detection is outside schedule', () => {
      // Saturday 10am - outside business hours schedule
      const saturdayMorning = new Date('2025-01-25T10:00:00');
      render(
        <AccessViolationBadge
          detectedAt={saturdayMorning}
          schedule={businessHoursSchedule}
        />
      );

      expect(screen.getByText('Outside Schedule')).toBeInTheDocument();
    });

    it('does not render when detection is within schedule', () => {
      // Monday 10am - within business hours
      const mondayMorning = new Date('2025-01-27T10:00:00');
      render(
        <AccessViolationBadge
          detectedAt={mondayMorning}
          schedule={businessHoursSchedule}
        />
      );

      expect(screen.queryByText('Outside Schedule')).not.toBeInTheDocument();
    });

    it('does not render when schedule is null', () => {
      const anyTime = new Date('2025-01-25T03:00:00');
      render(
        <AccessViolationBadge detectedAt={anyTime} schedule={null} />
      );

      expect(screen.queryByText('Outside Schedule')).not.toBeInTheDocument();
    });

    it('does not render when schedule is undefined', () => {
      const anyTime = new Date('2025-01-25T03:00:00');
      render(
        <AccessViolationBadge detectedAt={anyTime} schedule={undefined} />
      );

      expect(screen.queryByText('Outside Schedule')).not.toBeInTheDocument();
    });

    it('accepts string timestamp', () => {
      render(
        <AccessViolationBadge
          detectedAt="2025-01-25T03:00:00Z"
          schedule={businessHoursSchedule}
        />
      );

      expect(screen.getByText('Outside Schedule')).toBeInTheDocument();
    });
  });

  describe('Size variants', () => {
    it('renders small size by default', () => {
      const saturday = new Date('2025-01-25T10:00:00');
      render(
        <AccessViolationBadge
          detectedAt={saturday}
          schedule={businessHoursSchedule}
        />
      );

      const badge = screen.getByText('Outside Schedule').parentElement;
      expect(badge).toHaveClass('text-xs');
    });

    it('renders medium size', () => {
      const saturday = new Date('2025-01-25T10:00:00');
      render(
        <AccessViolationBadge
          detectedAt={saturday}
          schedule={businessHoursSchedule}
          size="md"
        />
      );

      const badge = screen.getByText('Outside Schedule').parentElement;
      expect(badge).toHaveClass('text-sm');
    });

    it('renders large size', () => {
      const saturday = new Date('2025-01-25T10:00:00');
      render(
        <AccessViolationBadge
          detectedAt={saturday}
          schedule={businessHoursSchedule}
          size="lg"
        />
      );

      const badge = screen.getByText('Outside Schedule').parentElement;
      expect(badge).toHaveClass('text-base');
    });
  });

  describe('Accessibility', () => {
    it('has role="status"', () => {
      const saturday = new Date('2025-01-25T10:00:00');
      render(
        <AccessViolationBadge
          detectedAt={saturday}
          schedule={businessHoursSchedule}
        />
      );

      expect(screen.getByRole('status')).toBeInTheDocument();
    });

    it('has descriptive aria-label', () => {
      const saturday = new Date('2025-01-25T10:00:00');
      render(
        <AccessViolationBadge
          detectedAt={saturday}
          schedule={businessHoursSchedule}
        />
      );

      expect(screen.getByRole('status')).toHaveAttribute(
        'aria-label',
        'Schedule violation'
      );
    });

    it('has tooltip with violation details', () => {
      const saturday = new Date('2025-01-25T10:00:00');
      render(
        <AccessViolationBadge
          detectedAt={saturday}
          schedule={businessHoursSchedule}
        />
      );

      const badge = screen.getByRole('status');
      expect(badge).toHaveAttribute('title');
      expect(badge.title).toContain('Schedule violation');
    });
  });
});

describe('AccessViolationIcon', () => {
  const businessHoursSchedule: WeeklySchedule = {
    monday: [9, 10, 11, 12, 13, 14, 15, 16, 17],
    tuesday: [9, 10, 11, 12, 13, 14, 15, 16, 17],
    wednesday: [9, 10, 11, 12, 13, 14, 15, 16, 17],
    thursday: [9, 10, 11, 12, 13, 14, 15, 16, 17],
    friday: [9, 10, 11, 12, 13, 14, 15, 16, 17],
    saturday: [],
    sunday: [],
  };

  it('renders icon when detection is outside schedule', () => {
    const saturday = new Date('2025-01-25T10:00:00');
    render(
      <AccessViolationIcon
        detectedAt={saturday}
        schedule={businessHoursSchedule}
      />
    );

    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('does not render when detection is within schedule', () => {
    const monday = new Date('2025-01-27T10:00:00');
    render(
      <AccessViolationIcon
        detectedAt={monday}
        schedule={businessHoursSchedule}
      />
    );

    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });
});

describe('isWithinSchedule', () => {
  const businessHoursSchedule: WeeklySchedule = {
    monday: [9, 10, 11, 12, 13, 14, 15, 16, 17],
    tuesday: [9, 10, 11, 12, 13, 14, 15, 16, 17],
    wednesday: [9, 10, 11, 12, 13, 14, 15, 16, 17],
    thursday: [9, 10, 11, 12, 13, 14, 15, 16, 17],
    friday: [9, 10, 11, 12, 13, 14, 15, 16, 17],
    saturday: [],
    sunday: [],
  };

  it('returns true when within schedule', () => {
    // Monday 10am
    const monday = new Date('2025-01-27T10:00:00');
    expect(isWithinSchedule(monday, businessHoursSchedule)).toBe(true);
  });

  it('returns false when outside schedule - wrong day', () => {
    // Saturday 10am
    const saturday = new Date('2025-01-25T10:00:00');
    expect(isWithinSchedule(saturday, businessHoursSchedule)).toBe(false);
  });

  it('returns false when outside schedule - wrong hour', () => {
    // Monday 3am
    const mondayEarly = new Date('2025-01-27T03:00:00');
    expect(isWithinSchedule(mondayEarly, businessHoursSchedule)).toBe(false);
  });

  it('returns true when schedule is null', () => {
    const anyTime = new Date('2025-01-25T03:00:00');
    expect(isWithinSchedule(anyTime, null)).toBe(true);
  });

  it('returns true when schedule is undefined', () => {
    const anyTime = new Date('2025-01-25T03:00:00');
    expect(isWithinSchedule(anyTime, undefined)).toBe(true);
  });

  it('handles Date objects as timestamps', () => {
    // Use Date objects to avoid timezone parsing issues
    // Monday 10am local time - should be within schedule
    const mondayLocalTime = new Date(2025, 0, 27, 10, 0, 0); // Jan 27, 2025 10:00 local
    expect(isWithinSchedule(mondayLocalTime, businessHoursSchedule)).toBe(true);

    // Saturday 10am local time - should be outside schedule
    const saturdayLocalTime = new Date(2025, 0, 25, 10, 0, 0); // Jan 25, 2025 10:00 local
    expect(isWithinSchedule(saturdayLocalTime, businessHoursSchedule)).toBe(false);
  });

  it('correctly maps all days of the week', () => {
    const fullSchedule: WeeklySchedule = {
      monday: [0],
      tuesday: [0],
      wednesday: [0],
      thursday: [0],
      friday: [0],
      saturday: [0],
      sunday: [0],
    };

    // Sunday = 0, Monday = 1, ... Saturday = 6
    expect(isWithinSchedule(new Date('2025-01-26T00:00:00'), fullSchedule)).toBe(true); // Sunday
    expect(isWithinSchedule(new Date('2025-01-27T00:00:00'), fullSchedule)).toBe(true); // Monday
    expect(isWithinSchedule(new Date('2025-01-28T00:00:00'), fullSchedule)).toBe(true); // Tuesday
    expect(isWithinSchedule(new Date('2025-01-29T00:00:00'), fullSchedule)).toBe(true); // Wednesday
    expect(isWithinSchedule(new Date('2025-01-30T00:00:00'), fullSchedule)).toBe(true); // Thursday
    expect(isWithinSchedule(new Date('2025-01-31T00:00:00'), fullSchedule)).toBe(true); // Friday
    expect(isWithinSchedule(new Date('2025-02-01T00:00:00'), fullSchedule)).toBe(true); // Saturday
  });
});
