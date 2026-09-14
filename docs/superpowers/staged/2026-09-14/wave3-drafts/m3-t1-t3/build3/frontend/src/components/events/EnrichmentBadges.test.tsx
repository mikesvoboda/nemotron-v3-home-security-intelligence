import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import EnrichmentBadges, {
  enrichmentDataToSummary,
  type EnrichmentSummary,
} from './EnrichmentBadges';

import type { EnrichmentData } from '../../types/enrichment';

describe('EnrichmentBadges', () => {
  describe('rendering with no enrichment data', () => {
    it('renders nothing when enrichmentSummary is undefined', () => {
      const { container } = render(<EnrichmentBadges enrichmentSummary={undefined} />);
      expect(container.firstChild).toBeNull();
    });

    it('renders nothing when enrichmentSummary is null', () => {
      const { container } = render(<EnrichmentBadges enrichmentSummary={null} />);
      expect(container.firstChild).toBeNull();
    });

    it('renders nothing when enrichmentSummary is an empty object', () => {
      const { container } = render(<EnrichmentBadges enrichmentSummary={{}} />);
      expect(container.firstChild).toBeNull();
    });
  });

  describe('pending state', () => {
    it('renders pending badge when isEnrichmentPending is true', () => {
      render(<EnrichmentBadges isEnrichmentPending={true} />);
      expect(screen.getByTestId('enrichment-badges-pending')).toBeInTheDocument();
      expect(screen.getByText('Enriching...')).toBeInTheDocument();
    });

    it('shows spinner icon when pending', () => {
      render(<EnrichmentBadges isEnrichmentPending={true} />);
      // The Loader2 icon should have animate-spin class
      const badge = screen.getByTestId('enrichment-badge-enriching...');
      expect(badge.querySelector('svg')).toHaveClass('animate-spin');
    });
  });

  describe('face count badge', () => {
    it('renders face badge when faceCount > 0', () => {
      const summary: EnrichmentSummary = { faceCount: 2 };
      render(<EnrichmentBadges enrichmentSummary={summary} />);
      expect(screen.getByText('2 Faces')).toBeInTheDocument();
    });

    it('renders singular face text for count of 1', () => {
      const summary: EnrichmentSummary = { faceCount: 1 };
      render(<EnrichmentBadges enrichmentSummary={summary} />);
      expect(screen.getByText('1 Face')).toBeInTheDocument();
    });

    it('does not render face badge when faceCount is 0', () => {
      const summary: EnrichmentSummary = { faceCount: 0, hasVehicle: true };
      render(<EnrichmentBadges enrichmentSummary={summary} />);
      expect(screen.queryByText(/Face/)).not.toBeInTheDocument();
    });
  });

  describe('license plate badge', () => {
    it('renders plate badge when hasLicensePlate is true', () => {
      const summary: EnrichmentSummary = { hasLicensePlate: true };
      render(<EnrichmentBadges enrichmentSummary={summary} />);
      expect(screen.getByText('Plate')).toBeInTheDocument();
    });

    it('does not render plate badge when hasLicensePlate is false', () => {
      const summary: EnrichmentSummary = { hasLicensePlate: false, hasVehicle: true };
      render(<EnrichmentBadges enrichmentSummary={summary} />);
      expect(screen.queryByText('Plate')).not.toBeInTheDocument();
    });
  });

  describe('violence score badge', () => {
    it('renders threat badge when violenceScore > 0.5', () => {
      const summary: EnrichmentSummary = { violenceScore: 0.75 };
      render(<EnrichmentBadges enrichmentSummary={summary} />);
      expect(screen.getByText('Threat 75%')).toBeInTheDocument();
    });

    it('does not render threat badge when violenceScore <= 0.5', () => {
      const summary: EnrichmentSummary = { violenceScore: 0.5, hasVehicle: true };
      render(<EnrichmentBadges enrichmentSummary={summary} />);
      expect(screen.queryByText(/Threat/)).not.toBeInTheDocument();
    });

    it('does not render threat badge when violenceScore is 0', () => {
      const summary: EnrichmentSummary = { violenceScore: 0, hasVehicle: true };
      render(<EnrichmentBadges enrichmentSummary={summary} />);
      expect(screen.queryByText(/Threat/)).not.toBeInTheDocument();
    });

    it('rounds violence score to nearest percentage', () => {
      const summary: EnrichmentSummary = { violenceScore: 0.678 };
      render(<EnrichmentBadges enrichmentSummary={summary} />);
      expect(screen.getByText('Threat 68%')).toBeInTheDocument();
    });
  });

  describe('pet type badge', () => {
    it('renders pet badge when petType is set', () => {
      const summary: EnrichmentSummary = { petType: 'dog' };
      render(<EnrichmentBadges enrichmentSummary={summary} />);
      expect(screen.getByText('Dog')).toBeInTheDocument();
    });

    it('capitalizes pet type', () => {
      const summary: EnrichmentSummary = { petType: 'cat' };
      render(<EnrichmentBadges enrichmentSummary={summary} />);
      expect(screen.getByText('Cat')).toBeInTheDocument();
    });

    it('does not render pet badge when petType is undefined', () => {
      const summary: EnrichmentSummary = { hasVehicle: true };
      render(<EnrichmentBadges enrichmentSummary={summary} />);
      expect(screen.queryByText('Dog')).not.toBeInTheDocument();
      expect(screen.queryByText('Cat')).not.toBeInTheDocument();
    });
  });

  describe('vehicle badge', () => {
    it('renders vehicle badge when hasVehicle is true', () => {
      const summary: EnrichmentSummary = { hasVehicle: true };
      render(<EnrichmentBadges enrichmentSummary={summary} />);
      expect(screen.getByText('Vehicle')).toBeInTheDocument();
    });

    it('does not render vehicle badge when hasVehicle is false', () => {
      const summary: EnrichmentSummary = { hasVehicle: false, petType: 'dog' };
      render(<EnrichmentBadges enrichmentSummary={summary} />);
      expect(screen.queryByText('Vehicle')).not.toBeInTheDocument();
    });
  });

  describe('person badge', () => {
    it('renders person badge when hasPerson is true and no other person-related badges', () => {
      const summary: EnrichmentSummary = { hasPerson: true };
      render(<EnrichmentBadges enrichmentSummary={summary} />);
      expect(screen.getByText('Person')).toBeInTheDocument();
    });

    it('does not render person badge when faceCount is set', () => {
      const summary: EnrichmentSummary = { hasPerson: true, faceCount: 1 };
      render(<EnrichmentBadges enrichmentSummary={summary} />);
      // Should show "1 Face" instead of generic "Person"
      expect(screen.getByText('1 Face')).toBeInTheDocument();
      expect(screen.queryByText('Person')).not.toBeInTheDocument();
    });

    it('does not render person badge when poseAlertCount is set', () => {
      const summary: EnrichmentSummary = { hasPerson: true, poseAlertCount: 1 };
      render(<EnrichmentBadges enrichmentSummary={summary} />);
      // Should show "1 Alert" instead of generic "Person"
      expect(screen.getByText('1 Alert')).toBeInTheDocument();
      expect(screen.queryByText('Person')).not.toBeInTheDocument();
    });
  });

  describe('pose alerts badge', () => {
    it('renders alert badge when poseAlertCount > 0', () => {
      const summary: EnrichmentSummary = { poseAlertCount: 2 };
      render(<EnrichmentBadges enrichmentSummary={summary} />);
      expect(screen.getByText('2 Alerts')).toBeInTheDocument();
    });

    it('renders singular alert text for count of 1', () => {
      const summary: EnrichmentSummary = { poseAlertCount: 1 };
      render(<EnrichmentBadges enrichmentSummary={summary} />);
      expect(screen.getByText('1 Alert')).toBeInTheDocument();
    });

    it('does not render alert badge when poseAlertCount is 0', () => {
      const summary: EnrichmentSummary = { poseAlertCount: 0, hasVehicle: true };
      render(<EnrichmentBadges enrichmentSummary={summary} />);
      expect(screen.queryByText(/Alert/)).not.toBeInTheDocument();
    });

    it('uses alert variant styling for pose alerts', () => {
      const summary: EnrichmentSummary = { poseAlertCount: 1 };
      render(<EnrichmentBadges enrichmentSummary={summary} />);
      const badge = screen.getByTestId('enrichment-badge-1-alert');
      expect(badge).toHaveClass('bg-red-500/20');
    });
  });

  describe('click interactions', () => {
    it('calls onExpandEnrichment when badge is clicked', async () => {
      const user = userEvent.setup();
      const onExpand = vi.fn();
      const summary: EnrichmentSummary = { hasVehicle: true };
      render(<EnrichmentBadges enrichmentSummary={summary} onExpandEnrichment={onExpand} />);

      await user.click(screen.getByText('Vehicle'));
      expect(onExpand).toHaveBeenCalledTimes(1);
    });

    it('calls onExpandEnrichment when pressing Enter on badge', async () => {
      const user = userEvent.setup();
      const onExpand = vi.fn();
      const summary: EnrichmentSummary = { hasVehicle: true };
      render(<EnrichmentBadges enrichmentSummary={summary} onExpandEnrichment={onExpand} />);

      const badge = screen.getByText('Vehicle');
      badge.focus();
      await user.keyboard('{Enter}');
      expect(onExpand).toHaveBeenCalledTimes(1);
    });

    it('shows "Details" badge when onExpandEnrichment is provided', () => {
      const summary: EnrichmentSummary = { hasVehicle: true };
      render(<EnrichmentBadges enrichmentSummary={summary} onExpandEnrichment={() => {}} />);
      expect(screen.getByText('Details')).toBeInTheDocument();
    });

    it('does not show "Details" badge when onExpandEnrichment is not provided', () => {
      const summary: EnrichmentSummary = { hasVehicle: true };
      render(<EnrichmentBadges enrichmentSummary={summary} />);
      expect(screen.queryByText('Details')).not.toBeInTheDocument();
    });

    it('clicking badge does not propagate event to parent', async () => {
      const user = userEvent.setup();
      const parentClick = vi.fn();
      const onExpand = vi.fn();
      const summary: EnrichmentSummary = { hasVehicle: true };

      render(
        // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions -- test wrapper
        <div onClick={parentClick}>
          <EnrichmentBadges enrichmentSummary={summary} onExpandEnrichment={onExpand} />
        </div>
      );

      await user.click(screen.getByText('Vehicle'));
      expect(onExpand).toHaveBeenCalledTimes(1);
      expect(parentClick).not.toHaveBeenCalled();
    });
  });

  describe('badge variants', () => {
    it('uses info variant for face count badge', () => {
      const summary: EnrichmentSummary = { faceCount: 1 };
      render(<EnrichmentBadges enrichmentSummary={summary} />);
      const badge = screen.getByTestId('enrichment-badge-1-face');
      expect(badge).toHaveClass('bg-blue-500/20');
    });

    it('uses info variant for license plate badge', () => {
      const summary: EnrichmentSummary = { hasLicensePlate: true };
      render(<EnrichmentBadges enrichmentSummary={summary} />);
      const badge = screen.getByTestId('enrichment-badge-plate');
      expect(badge).toHaveClass('bg-blue-500/20');
    });

    it('uses alert variant for violence score badge', () => {
      const summary: EnrichmentSummary = { violenceScore: 0.8 };
      render(<EnrichmentBadges enrichmentSummary={summary} />);
      const badge = screen.getByTestId('enrichment-badge-threat-80%');
      expect(badge).toHaveClass('bg-red-500/20');
    });

    it('uses info variant for pet badge', () => {
      const summary: EnrichmentSummary = { petType: 'dog' };
      render(<EnrichmentBadges enrichmentSummary={summary} />);
      const badge = screen.getByTestId('enrichment-badge-dog');
      expect(badge).toHaveClass('bg-blue-500/20');
    });

    it('uses info variant for vehicle badge', () => {
      const summary: EnrichmentSummary = { hasVehicle: true };
      render(<EnrichmentBadges enrichmentSummary={summary} />);
      const badge = screen.getByTestId('enrichment-badge-vehicle');
      expect(badge).toHaveClass('bg-blue-500/20');
    });
  });

  describe('multiple badges', () => {
    it('renders all applicable badges', () => {
      const summary: EnrichmentSummary = {
        faceCount: 2,
        hasLicensePlate: true,
        hasVehicle: true,
        petType: 'cat',
      };
      render(<EnrichmentBadges enrichmentSummary={summary} />);
      expect(screen.getByText('2 Faces')).toBeInTheDocument();
      expect(screen.getByText('Plate')).toBeInTheDocument();
      expect(screen.getByText('Vehicle')).toBeInTheDocument();
      expect(screen.getByText('Cat')).toBeInTheDocument();
    });

    it('displays badges in priority order', () => {
      const summary: EnrichmentSummary = {
        hasVehicle: true,
        poseAlertCount: 1,
        violenceScore: 0.8,
      };
      render(<EnrichmentBadges enrichmentSummary={summary} />);
      const badges = screen.getByTestId('enrichment-badges');
      const badgeTexts = badges.textContent;
      // Alert badges should come before vehicle
      expect(badgeTexts?.indexOf('Alert')).toBeLessThan(badgeTexts?.indexOf('Vehicle') ?? Infinity);
    });
  });

  describe('className prop', () => {
    it('applies custom className', () => {
      const summary: EnrichmentSummary = { hasVehicle: true };
      render(<EnrichmentBadges enrichmentSummary={summary} className="custom-class" />);
      const container = screen.getByTestId('enrichment-badges');
      expect(container).toHaveClass('custom-class');
    });

    it('merges with default classes', () => {
      const summary: EnrichmentSummary = { hasVehicle: true };
      render(<EnrichmentBadges enrichmentSummary={summary} className="mt-2" />);
      const container = screen.getByTestId('enrichment-badges');
      expect(container).toHaveClass('mt-2', 'flex', 'flex-wrap', 'gap-1.5');
    });
  });

  describe('enrichmentDataToSummary', () => {
    it('returns empty object for null data', () => {
      const summary = enrichmentDataToSummary(null);
      expect(summary).toEqual({});
    });

    it('returns empty object for undefined data', () => {
      const summary = enrichmentDataToSummary(undefined);
      expect(summary).toEqual({});
    });

    it('extracts hasVehicle from vehicle data', () => {
      const data: EnrichmentData = {
        vehicle: { type: 'sedan', color: 'blue', confidence: 0.9 },
      };
      const summary = enrichmentDataToSummary(data);
      expect(summary.hasVehicle).toBe(true);
    });

    it('extracts hasLicensePlate from license_plate data', () => {
      const data: EnrichmentData = {
        license_plate: { text: 'ABC-123', confidence: 0.95 },
      };
      const summary = enrichmentDataToSummary(data);
      expect(summary.hasLicensePlate).toBe(true);
    });

    it('extracts petType from pet data', () => {
      const data: EnrichmentData = {
        pet: { type: 'dog', confidence: 0.9 },
      };
      const summary = enrichmentDataToSummary(data);
      expect(summary.petType).toBe('dog');
    });

    it('extracts hasPerson from person data', () => {
      const data: EnrichmentData = {
        person: { clothing: 'dark jacket', confidence: 0.85 },
      };
      const summary = enrichmentDataToSummary(data);
      expect(summary.hasPerson).toBe(true);
    });

    it('extracts poseAlertCount from pose alerts', () => {
      const data: EnrichmentData = {
        pose: {
          keypoints: [],
          posture: 'crouching',
          alerts: ['crouching', 'hands_raised'],
        },
      };
      const summary = enrichmentDataToSummary(data);
      expect(summary.poseAlertCount).toBe(2);
    });

    it('extracts poseAlertCount from security_alerts fallback', () => {
      const data: EnrichmentData = {
        pose: {
          keypoints: [],
          posture: 'crouching',
          alerts: [],
          security_alerts: ['crouching'],
        },
      };
      const summary = enrichmentDataToSummary(data);
      expect(summary.poseAlertCount).toBe(1);
    });

    it('does not set poseAlertCount when alerts array is empty', () => {
      const data: EnrichmentData = {
        pose: {
          keypoints: [],
          posture: 'standing',
          alerts: [],
        },
      };
      const summary = enrichmentDataToSummary(data);
      expect(summary.poseAlertCount).toBeUndefined();
    });

    it('handles multiple enrichment types', () => {
      const data: EnrichmentData = {
        vehicle: { type: 'SUV', color: 'black', confidence: 0.9 },
        license_plate: { text: 'XYZ-789', confidence: 0.95 },
        pet: { type: 'cat', confidence: 0.88 },
        person: { clothing: 'uniform', confidence: 0.85 },
      };
      const summary = enrichmentDataToSummary(data);
      expect(summary.hasVehicle).toBe(true);
      expect(summary.hasLicensePlate).toBe(true);
      expect(summary.petType).toBe('cat');
      expect(summary.hasPerson).toBe(true);
    });
  });

  describe('using enrichmentData prop', () => {
    it('converts enrichmentData to summary and displays badges', () => {
      const data: EnrichmentData = {
        vehicle: { type: 'sedan', color: 'red', confidence: 0.9 },
        license_plate: { text: 'TEST-123', confidence: 0.95 },
      };
      render(<EnrichmentBadges enrichmentData={data} />);
      expect(screen.getByText('Vehicle')).toBeInTheDocument();
      expect(screen.getByText('Plate')).toBeInTheDocument();
    });

    it('prefers enrichmentSummary over enrichmentData if both provided', () => {
      const summary: EnrichmentSummary = { hasVehicle: true };
      const data: EnrichmentData = {
        pet: { type: 'dog', confidence: 0.9 },
      };
      render(<EnrichmentBadges enrichmentSummary={summary} enrichmentData={data} />);
      // Should show vehicle (from summary) not dog (from data)
      expect(screen.getByText('Vehicle')).toBeInTheDocument();
      expect(screen.queryByText('Dog')).not.toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('clickable badges have role="button"', () => {
      const summary: EnrichmentSummary = { hasVehicle: true };
      render(<EnrichmentBadges enrichmentSummary={summary} onExpandEnrichment={() => {}} />);
      const badge = screen.getByTestId('enrichment-badge-vehicle');
      expect(badge).toHaveAttribute('role', 'button');
    });

    it('clickable badges have tabIndex=0', () => {
      const summary: EnrichmentSummary = { hasVehicle: true };
      render(<EnrichmentBadges enrichmentSummary={summary} onExpandEnrichment={() => {}} />);
      const badge = screen.getByTestId('enrichment-badge-vehicle');
      expect(badge).toHaveAttribute('tabIndex', '0');
    });

    it('non-clickable badges do not have role="button"', () => {
      const summary: EnrichmentSummary = { hasVehicle: true };
      render(<EnrichmentBadges enrichmentSummary={summary} />);
      const badge = screen.getByTestId('enrichment-badge-vehicle');
      expect(badge).not.toHaveAttribute('role');
    });
  });
});
