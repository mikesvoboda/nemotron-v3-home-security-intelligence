/**
 * TDD Tests for EnrichmentViewer Component (NEM-5078)
 *
 * These tests define the API and behavior for the EnrichmentViewer component,
 * which displays enrichment data in multiple variants (full, compact, modal)
 * with security alert highlighting.
 *
 * Component requirements:
 * - Display enrichment data: vehicle, pet, person, pose, license plate, weather, image quality
 * - Expandable/collapsible sections with accordion UI
 * - Multiple variants: full (accordions), compact (badges), modal (expanded)
 * - Security alert highlighting (auto-open dangerous sections)
 * - Controlled expansion state management
 * - Loading and error states
 * - Accessibility support (keyboard navigation, ARIA labels)
 *
 * @see docs/plans/2026-02-01-platform-enhancement-strategy-design.md
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import EnrichmentViewer from '../EnrichmentViewer';

import type { EnrichmentData } from '../../../types/enrichment';

// ============================================================================
// Test Data Fixtures
// ============================================================================

const vehicleEnrichment: EnrichmentData = {
  vehicle: {
    type: 'sedan',
    color: 'blue',
    damage: ['dents', 'scratches'],
    commercial: false,
    caption: 'Blue sedan with visible damage',
    confidence: 0.92,
  },
};

const petEnrichment: EnrichmentData = {
  pet: {
    type: 'dog',
    breed: 'Golden Retriever',
    confidence: 0.88,
  },
};

const personEnrichment: EnrichmentData = {
  person: {
    clothing: 'dark hoodie, jeans',
    action: 'walking',
    carrying: 'backpack',
    suspicious_attire: true,
    service_uniform: false,
    caption: 'Person in dark clothing with backpack',
    confidence: 0.85,
  },
};

const poseEnrichment: EnrichmentData = {
  pose: {
    posture: 'standing',
    alerts: [],
    keypoints: [
      [0.5, 0.3, 0.95],
      [0.52, 0.35, 0.9],
      [0.48, 0.35, 0.88],
    ],
    keypoint_count: 15,
    confidence: 0.91,
  },
};

const poseWithAlertsEnrichment: EnrichmentData = {
  pose: {
    posture: 'crouching',
    alerts: ['crouching', 'hands_raised'],
    keypoints: [
      [0.5, 0.4, 0.92],
      [0.52, 0.42, 0.88],
    ],
    keypoint_count: 12,
    confidence: 0.87,
  },
};

const licensePlateEnrichment: EnrichmentData = {
  license_plate: {
    text: 'ABC-1234',
    confidence: 0.96,
  },
};

const weatherEnrichment: EnrichmentData = {
  weather: {
    condition: 'rain',
    confidence: 0.78,
  },
};

const imageQualityEnrichment: EnrichmentData = {
  image_quality: {
    score: 0.72,
    issues: ['blur', 'low_light'],
  },
};

const completeEnrichment: EnrichmentData = {
  vehicle: {
    type: 'SUV',
    color: 'black',
    confidence: 0.94,
  },
  pet: {
    type: 'cat',
    confidence: 0.82,
  },
  person: {
    clothing: 'blue shirt',
    confidence: 0.89,
  },
  pose: {
    posture: 'walking',
    alerts: [],
    keypoints: [],
    keypoint_count: 17,
    confidence: 0.93,
  },
  license_plate: {
    text: 'XYZ-9876',
    confidence: 0.91,
  },
  weather: {
    condition: 'clear',
    confidence: 0.88,
  },
  image_quality: {
    score: 0.85,
    issues: [],
  },
};

// ============================================================================
// Rendering Tests
// ============================================================================

describe('EnrichmentViewer - Rendering', () => {
  it('test_renders_vehicle_enrichment_section', () => {
    render(<EnrichmentViewer enrichmentData={vehicleEnrichment} />);

    expect(screen.getByTestId('enrichment-section-vehicle')).toBeInTheDocument();
    expect(screen.getByText('Vehicle')).toBeInTheDocument();
    expect(screen.getByText('sedan')).toBeInTheDocument();
    expect(screen.getByText('blue')).toBeInTheDocument();
    expect(screen.getByText('dents')).toBeInTheDocument();
    expect(screen.getByText('scratches')).toBeInTheDocument();
    expect(screen.getByText('92%')).toBeInTheDocument();
  });

  it('test_renders_pet_enrichment_section', () => {
    render(<EnrichmentViewer enrichmentData={petEnrichment} />);

    expect(screen.getByTestId('enrichment-section-pet')).toBeInTheDocument();
    expect(screen.getByText('Pet')).toBeInTheDocument();
    expect(screen.getByText('dog')).toBeInTheDocument();
    expect(screen.getByText('Golden Retriever')).toBeInTheDocument();
    expect(screen.getByText('88%')).toBeInTheDocument();
  });

  it('test_renders_person_enrichment_section', () => {
    render(<EnrichmentViewer enrichmentData={personEnrichment} />);

    expect(screen.getByTestId('enrichment-section-person')).toBeInTheDocument();
    expect(screen.getByText('Person')).toBeInTheDocument();
    expect(screen.getByText('dark hoodie, jeans')).toBeInTheDocument();
    expect(screen.getByText('walking')).toBeInTheDocument();
    expect(screen.getByText('backpack')).toBeInTheDocument();
    expect(screen.getByText('Suspicious Attire')).toBeInTheDocument();
  });

  it('test_renders_pose_enrichment_section', () => {
    render(<EnrichmentViewer enrichmentData={poseEnrichment} />);

    expect(screen.getByTestId('enrichment-section-pose')).toBeInTheDocument();
    expect(screen.getByText('Pose Analysis')).toBeInTheDocument();
    expect(screen.getByText('standing')).toBeInTheDocument();
    expect(screen.getByText('15 / 17')).toBeInTheDocument();
    expect(screen.getByText('91%')).toBeInTheDocument();
  });

  it('test_renders_license_plate_section', () => {
    render(<EnrichmentViewer enrichmentData={licensePlateEnrichment} />);

    expect(screen.getByTestId('enrichment-section-license-plate')).toBeInTheDocument();
    expect(screen.getByText('License Plate')).toBeInTheDocument();
    expect(screen.getByText('ABC-1234')).toBeInTheDocument();
    expect(screen.getByText('96%')).toBeInTheDocument();
  });

  it('test_renders_weather_section', () => {
    render(<EnrichmentViewer enrichmentData={weatherEnrichment} />);

    expect(screen.getByTestId('enrichment-section-weather')).toBeInTheDocument();
    expect(screen.getByText('Weather')).toBeInTheDocument();
    expect(screen.getByText('rain')).toBeInTheDocument();
    expect(screen.getByText('78%')).toBeInTheDocument();
  });

  it('test_renders_image_quality_section', () => {
    render(<EnrichmentViewer enrichmentData={imageQualityEnrichment} />);

    expect(screen.getByTestId('enrichment-section-image-quality')).toBeInTheDocument();
    expect(screen.getByText('Image Quality')).toBeInTheDocument();
    expect(screen.getByText('72%')).toBeInTheDocument();
    expect(screen.getByText('blur')).toBeInTheDocument();
    expect(screen.getByText('low_light')).toBeInTheDocument();
  });

  it('test_hides_empty_sections_by_default', () => {
    render(<EnrichmentViewer enrichmentData={vehicleEnrichment} />);

    // Only vehicle section should be present
    expect(screen.getByTestId('enrichment-section-vehicle')).toBeInTheDocument();
    expect(screen.queryByTestId('enrichment-section-pet')).not.toBeInTheDocument();
    expect(screen.queryByTestId('enrichment-section-person')).not.toBeInTheDocument();
    expect(screen.queryByTestId('enrichment-section-pose')).not.toBeInTheDocument();
  });
});

// ============================================================================
// Variant Tests
// ============================================================================

describe('EnrichmentViewer - Variants', () => {
  it('test_full_variant_shows_accordions', () => {
    render(<EnrichmentViewer enrichmentData={completeEnrichment} variant="full" />);

    // Should render accordion containers
    expect(screen.getByTestId('enrichment-viewer-full')).toBeInTheDocument();
    expect(screen.getAllByRole('button', { expanded: false })).toHaveLength(7);
  });

  it('test_compact_variant_shows_badges', () => {
    render(<EnrichmentViewer enrichmentData={completeEnrichment} variant="compact" />);

    // Should render compact badge view
    expect(screen.getByTestId('enrichment-viewer-compact')).toBeInTheDocument();
    expect(screen.getByTestId('enrichment-badge-vehicle')).toBeInTheDocument();
    expect(screen.getByTestId('enrichment-badge-pet')).toBeInTheDocument();
    expect(screen.getByTestId('enrichment-badge-person')).toBeInTheDocument();
  });

  it('test_modal_variant_expanded_view', () => {
    render(<EnrichmentViewer enrichmentData={completeEnrichment} variant="modal" />);

    // Modal variant should have all sections expanded by default
    expect(screen.getByTestId('enrichment-viewer-modal')).toBeInTheDocument();
    expect(screen.getAllByRole('button', { expanded: true })).toHaveLength(7);
  });
});

// ============================================================================
// Security Highlighting Tests
// ============================================================================

describe('EnrichmentViewer - Security Highlighting', () => {
  it('test_pose_alerts_section_auto_opens', () => {
    render(<EnrichmentViewer enrichmentData={poseWithAlertsEnrichment} />);

    // Pose section with alerts should be auto-expanded
    const poseSection = screen.getByTestId('enrichment-section-pose');
    expect(poseSection).toHaveAttribute('data-expanded', 'true');
  });

  it('test_violence_detection_highlighted', () => {
    render(<EnrichmentViewer enrichmentData={poseWithAlertsEnrichment} />);

    // Security alerts should have alert styling
    expect(screen.getByTestId('security-alert-crouching')).toBeInTheDocument();
    expect(screen.getByTestId('security-alert-hands_raised')).toBeInTheDocument();

    const alertSection = screen.getByTestId('pose-security-alerts');
    expect(alertSection).toHaveClass('border-red-500');
  });

  it('test_threat_detection_prominent_display', () => {
    render(<EnrichmentViewer enrichmentData={poseWithAlertsEnrichment} />);

    // Should show alert count badge
    expect(screen.getByText('2 Alerts')).toBeInTheDocument();

    // Alert section should be visually prominent
    const poseHeader = screen.getByTestId('enrichment-header-pose');
    expect(poseHeader).toHaveClass('bg-red-900/20');
  });
});

// ============================================================================
// Interaction Tests
// ============================================================================

describe('EnrichmentViewer - Interactions', () => {
  it('test_section_expand_collapse', async () => {
    const user = userEvent.setup();
    render(<EnrichmentViewer enrichmentData={completeEnrichment} />);

    // Initially collapsed
    const vehicleButton = screen.getByRole('button', { name: /vehicle/i });
    expect(vehicleButton).toHaveAttribute('aria-expanded', 'false');

    // Click to expand
    await user.click(vehicleButton);
    expect(vehicleButton).toHaveAttribute('aria-expanded', 'true');

    // Click to collapse
    await user.click(vehicleButton);
    expect(vehicleButton).toHaveAttribute('aria-expanded', 'false');
  });

  it('test_controlled_expanded_sections', () => {
    render(
      <EnrichmentViewer
        enrichmentData={completeEnrichment}
        expandedSections={['vehicle', 'pet']}
      />
    );

    // Specified sections should be expanded
    const vehicleButton = screen.getByRole('button', { name: /vehicle/i });
    const petButton = screen.getByRole('button', { name: /pet/i });
    const personButton = screen.getByRole('button', { name: /person/i });

    expect(vehicleButton).toHaveAttribute('aria-expanded', 'true');
    expect(petButton).toHaveAttribute('aria-expanded', 'true');
    expect(personButton).toHaveAttribute('aria-expanded', 'false');
  });

  it('test_on_section_toggle_callback', async () => {
    const user = userEvent.setup();
    const onToggle = vi.fn();

    render(
      <EnrichmentViewer enrichmentData={vehicleEnrichment} onSectionToggle={onToggle} />
    );

    const vehicleButton = screen.getByRole('button', { name: /vehicle/i });
    await user.click(vehicleButton);

    expect(onToggle).toHaveBeenCalledWith('vehicle', true);

    await user.click(vehicleButton);
    expect(onToggle).toHaveBeenCalledWith('vehicle', false);
  });

  it('test_on_entity_click_callback', async () => {
    const user = userEvent.setup();
    const onEntityClick = vi.fn();

    render(
      <EnrichmentViewer
        enrichmentData={licensePlateEnrichment}
        onEntityClick={onEntityClick}
      />
    );

    // Expand section first
    const plateButton = screen.getByRole('button', { name: /license plate/i });
    await user.click(plateButton);

    // Click on plate text
    const plateText = screen.getByText('ABC-1234');
    await user.click(plateText);

    expect(onEntityClick).toHaveBeenCalledWith('license_plate', 'ABC-1234');
  });
});

// ============================================================================
// Loading and Error State Tests
// ============================================================================

describe('EnrichmentViewer - Loading and Error States', () => {
  it('test_loading_state_shows_skeleton', () => {
    render(<EnrichmentViewer enrichmentData={null} isLoading={true} />);

    expect(screen.getByTestId('enrichment-viewer-skeleton')).toBeInTheDocument();
    expect(screen.getByText('Loading enrichment data...')).toBeInTheDocument();
  });

  it('test_error_state_shows_message', () => {
    render(
      <EnrichmentViewer enrichmentData={null} error="Failed to load enrichment data" />
    );

    expect(screen.getByTestId('enrichment-viewer-error')).toBeInTheDocument();
    expect(screen.getByText('Failed to load enrichment data')).toBeInTheDocument();
  });

  it('test_refresh_button_calls_handler', async () => {
    const user = userEvent.setup();
    const onRefresh = vi.fn();

    render(
      <EnrichmentViewer
        enrichmentData={null}
        error="Failed to load"
        onRefresh={onRefresh}
      />
    );

    const refreshButton = screen.getByRole('button', { name: /retry/i });
    await user.click(refreshButton);

    expect(onRefresh).toHaveBeenCalledTimes(1);
  });
});

// ============================================================================
// Accessibility Tests
// ============================================================================

describe('EnrichmentViewer - Accessibility', () => {
  it('test_keyboard_navigation', async () => {
    const user = userEvent.setup();
    render(<EnrichmentViewer enrichmentData={completeEnrichment} />);

    const vehicleButton = screen.getByRole('button', { name: /vehicle/i });

    // Tab to focus
    await user.tab();
    expect(vehicleButton).toHaveFocus();

    // Enter to expand
    await user.keyboard('{Enter}');
    await waitFor(() => {
      expect(vehicleButton).toHaveAttribute('aria-expanded', 'true');
    });

    // Space to collapse
    await user.keyboard(' ');
    await waitFor(() => {
      expect(vehicleButton).toHaveAttribute('aria-expanded', 'false');
    });
  });

  it('test_aria_labels_present', () => {
    render(<EnrichmentViewer enrichmentData={completeEnrichment} />);

    // Check ARIA labels on accordion buttons
    expect(screen.getByRole('button', { name: /vehicle/i })).toHaveAttribute(
      'aria-controls'
    );
    expect(screen.getByRole('button', { name: /pet/i })).toHaveAttribute('aria-controls');
  });

  it('test_focus_management', async () => {
    const user = userEvent.setup();
    render(<EnrichmentViewer enrichmentData={vehicleEnrichment} />);

    const vehicleButton = screen.getByRole('button', { name: /vehicle/i });

    // Expand section
    await user.click(vehicleButton);

    // Focus should remain on button after expansion
    expect(vehicleButton).toHaveFocus();
  });
});

// ============================================================================
// Edge Cases and Empty State Tests
// ============================================================================

describe('EnrichmentViewer - Edge Cases', () => {
  it('test_null_enrichment_data_shows_nothing', () => {
    const { container } = render(<EnrichmentViewer enrichmentData={null} />);

    expect(container.firstChild).toBeNull();
  });

  it('test_undefined_enrichment_data_shows_nothing', () => {
    const { container } = render(<EnrichmentViewer enrichmentData={undefined} />);

    expect(container.firstChild).toBeNull();
  });

  it('test_empty_enrichment_object_shows_nothing', () => {
    const { container } = render(<EnrichmentViewer enrichmentData={{}} />);

    expect(container.firstChild).toBeNull();
  });

  it('test_partial_enrichment_shows_only_available_sections', () => {
    const partialData: EnrichmentData = {
      vehicle: {
        type: 'truck',
        color: 'red',
        confidence: 0.89,
      },
      weather: {
        condition: 'fog',
        confidence: 0.75,
      },
    };

    render(<EnrichmentViewer enrichmentData={partialData} />);

    expect(screen.getByTestId('enrichment-section-vehicle')).toBeInTheDocument();
    expect(screen.getByTestId('enrichment-section-weather')).toBeInTheDocument();
    expect(screen.queryByTestId('enrichment-section-pet')).not.toBeInTheDocument();
    expect(screen.queryByTestId('enrichment-section-person')).not.toBeInTheDocument();
  });

  it('test_pose_without_alerts_shows_normal_state', () => {
    render(<EnrichmentViewer enrichmentData={poseEnrichment} />);

    const poseSection = screen.getByTestId('enrichment-section-pose');
    expect(poseSection).toHaveAttribute('data-expanded', 'false');

    // Should not have alert styling
    expect(screen.queryByTestId('pose-security-alerts')).not.toBeInTheDocument();
  });

  it('test_vehicle_without_damage_hides_damage_field', () => {
    const noDamageData: EnrichmentData = {
      vehicle: {
        type: 'sedan',
        color: 'white',
        confidence: 0.91,
      },
    };

    render(<EnrichmentViewer enrichmentData={noDamageData} />);

    expect(screen.queryByText('Damage')).not.toBeInTheDocument();
  });

  it('test_commercial_flag_shows_badge', () => {
    const commercialData: EnrichmentData = {
      vehicle: {
        type: 'van',
        color: 'white',
        commercial: true,
        confidence: 0.93,
      },
    };

    render(<EnrichmentViewer enrichmentData={commercialData} />);

    expect(screen.getByText('Commercial Vehicle')).toBeInTheDocument();
  });
});
