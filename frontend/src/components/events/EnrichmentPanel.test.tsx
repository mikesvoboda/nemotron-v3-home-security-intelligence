import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import EnrichmentPanel from './EnrichmentPanel';

import type { EnrichmentData } from '../../types/generated';

describe('EnrichmentPanel', () => {
  // Mock enrichment data
  const mockFullEnrichment: EnrichmentData = {
    vehicle: {
      type: 'SUV',
      color: 'Black',
      damage: ['Scratched bumper', 'Dented door'],
      confidence: 0.92,
    },
    pet: {
      type: 'Dog',
      breed: 'Golden Retriever',
      confidence: 0.88,
    },
    person: {
      clothing: 'Blue jacket, jeans',
      action: 'Walking',
      carrying: 'Backpack',
      confidence: 0.95,
    },
    license_plate: {
      text: 'ABC-1234',
      confidence: 0.75,
    },
    weather: {
      condition: 'Partly Cloudy',
      confidence: 0.85,
    },
    image_quality: {
      score: 0.78,
      issues: ['Low light', 'Motion blur'],
    },
  };

  describe('rendering', () => {
    it('renders empty state when enrichment is null', () => {
      render(<EnrichmentPanel enrichment={null} />);
      expect(screen.getByText('No enrichment data available for this event.')).toBeInTheDocument();
    });

    it('renders empty state when enrichment is undefined', () => {
      render(<EnrichmentPanel />);
      expect(screen.getByText('No enrichment data available for this event.')).toBeInTheDocument();
    });

    it('renders empty state when enrichment has no data', () => {
      render(<EnrichmentPanel enrichment={{}} />);
      expect(screen.getByText('No enrichment data available for this event.')).toBeInTheDocument();
    });

    it('renders panel with test id when enrichment data is present', () => {
      render(<EnrichmentPanel enrichment={mockFullEnrichment} />);
      expect(screen.getByTestId('enrichment-panel')).toBeInTheDocument();
    });

    it('renders correct count of enrichment types', () => {
      render(<EnrichmentPanel enrichment={mockFullEnrichment} />);
      expect(screen.getByText('AI Enrichment (6 types)')).toBeInTheDocument();
    });

    it('renders singular type text when only one enrichment type', () => {
      const singleEnrichment: EnrichmentData = {
        vehicle: { type: 'Car', color: 'Red', confidence: 0.9 },
      };
      render(<EnrichmentPanel enrichment={singleEnrichment} />);
      expect(screen.getByText('AI Enrichment (1 type)')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      render(<EnrichmentPanel enrichment={mockFullEnrichment} className="custom-class" />);
      expect(screen.getByTestId('enrichment-panel')).toHaveClass('custom-class');
    });
  });

  describe('vehicle section', () => {
    const vehicleEnrichment: EnrichmentData = {
      vehicle: {
        type: 'SUV',
        color: 'Black',
        damage: ['Scratched bumper'],
        confidence: 0.92,
      },
    };

    it('renders vehicle section when vehicle data is present', () => {
      render(<EnrichmentPanel enrichment={vehicleEnrichment} />);
      expect(screen.getByText('Vehicle')).toBeInTheDocument();
    });

    it('displays vehicle type', () => {
      render(<EnrichmentPanel enrichment={vehicleEnrichment} />);
      expect(screen.getByText('SUV')).toBeInTheDocument();
    });

    it('displays vehicle color', () => {
      render(<EnrichmentPanel enrichment={vehicleEnrichment} />);
      expect(screen.getByText('Black')).toBeInTheDocument();
    });

    it('displays damage when present', () => {
      render(<EnrichmentPanel enrichment={vehicleEnrichment} />);
      expect(screen.getByText('Scratched bumper')).toBeInTheDocument();
    });

    it('displays multiple damage items', () => {
      render(<EnrichmentPanel enrichment={mockFullEnrichment} />);
      expect(screen.getByText('Scratched bumper')).toBeInTheDocument();
      expect(screen.getByText('Dented door')).toBeInTheDocument();
    });

    it('does not display damage section when damage array is empty', () => {
      const vehicleNoDamage: EnrichmentData = {
        vehicle: {
          type: 'Car',
          color: 'Blue',
          damage: [],
          confidence: 0.9,
        },
      };
      render(<EnrichmentPanel enrichment={vehicleNoDamage} />);
      expect(screen.queryByText('Damage')).not.toBeInTheDocument();
    });

    it('displays confidence percentage', () => {
      render(<EnrichmentPanel enrichment={vehicleEnrichment} />);
      expect(screen.getByText('92%')).toBeInTheDocument();
    });

    it('vehicle section is open by default', () => {
      render(<EnrichmentPanel enrichment={vehicleEnrichment} />);
      // If it's open, the Type label should be visible
      expect(screen.getByText('Type')).toBeInTheDocument();
    });
  });

  describe('pet section', () => {
    const petEnrichment: EnrichmentData = {
      pet: {
        type: 'Dog',
        breed: 'Golden Retriever',
        confidence: 0.88,
      },
    };

    it('renders pet section when pet data is present', () => {
      render(<EnrichmentPanel enrichment={petEnrichment} />);
      expect(screen.getByText('Pet')).toBeInTheDocument();
    });

    it('displays pet type after expanding', async () => {
      const user = userEvent.setup();
      render(<EnrichmentPanel enrichment={petEnrichment} />);
      // Expand the section first
      await user.click(screen.getByText('Pet'));
      expect(screen.getByText('Dog')).toBeInTheDocument();
    });

    it('displays breed when present after expanding', async () => {
      const user = userEvent.setup();
      render(<EnrichmentPanel enrichment={petEnrichment} />);
      await user.click(screen.getByText('Pet'));
      expect(screen.getByText('Golden Retriever')).toBeInTheDocument();
    });

    it('does not display breed label when breed is not present', async () => {
      const petNoBreed: EnrichmentData = {
        pet: {
          type: 'Cat',
          confidence: 0.9,
        },
      };
      const user = userEvent.setup();
      render(<EnrichmentPanel enrichment={petNoBreed} />);

      // Click to expand the pet section
      await user.click(screen.getByText('Pet'));

      expect(screen.getByText('Cat')).toBeInTheDocument();
      expect(screen.queryByText('Breed')).not.toBeInTheDocument();
    });

    it('displays confidence percentage after expanding', async () => {
      const user = userEvent.setup();
      render(<EnrichmentPanel enrichment={petEnrichment} />);
      await user.click(screen.getByText('Pet'));
      expect(screen.getByText('88%')).toBeInTheDocument();
    });
  });

  describe('person section', () => {
    const personEnrichment: EnrichmentData = {
      person: {
        clothing: 'Blue jacket, jeans',
        action: 'Walking',
        carrying: 'Backpack',
        confidence: 0.95,
      },
    };

    it('renders person section when person data is present', () => {
      render(<EnrichmentPanel enrichment={personEnrichment} />);
      expect(screen.getByText('Person Attributes')).toBeInTheDocument();
    });

    it('displays clothing after expanding', async () => {
      const user = userEvent.setup();
      render(<EnrichmentPanel enrichment={personEnrichment} />);
      await user.click(screen.getByText('Person Attributes'));
      expect(screen.getByText('Blue jacket, jeans')).toBeInTheDocument();
    });

    it('displays action when present after expanding', async () => {
      const user = userEvent.setup();
      render(<EnrichmentPanel enrichment={personEnrichment} />);
      await user.click(screen.getByText('Person Attributes'));
      expect(screen.getByText('Walking')).toBeInTheDocument();
    });

    it('displays carrying when present after expanding', async () => {
      const user = userEvent.setup();
      render(<EnrichmentPanel enrichment={personEnrichment} />);
      await user.click(screen.getByText('Person Attributes'));
      expect(screen.getByText('Backpack')).toBeInTheDocument();
    });

    it('does not display optional fields when not present', async () => {
      const personMinimal: EnrichmentData = {
        person: {
          clothing: 'T-shirt',
          confidence: 0.9,
        },
      };
      const user = userEvent.setup();
      render(<EnrichmentPanel enrichment={personMinimal} />);

      // Expand section
      await user.click(screen.getByText('Person Attributes'));

      expect(screen.getByText('T-shirt')).toBeInTheDocument();
      expect(screen.queryByText('Action')).not.toBeInTheDocument();
      expect(screen.queryByText('Carrying')).not.toBeInTheDocument();
    });

    it('displays confidence percentage after expanding', async () => {
      const user = userEvent.setup();
      render(<EnrichmentPanel enrichment={personEnrichment} />);
      await user.click(screen.getByText('Person Attributes'));
      expect(screen.getByText('95%')).toBeInTheDocument();
    });
  });

  describe('license plate section', () => {
    const licensePlateEnrichment: EnrichmentData = {
      license_plate: {
        text: 'ABC-1234',
        confidence: 0.75,
      },
    };

    it('renders license plate section when data is present', () => {
      render(<EnrichmentPanel enrichment={licensePlateEnrichment} />);
      expect(screen.getByText('License Plate')).toBeInTheDocument();
    });

    it('displays plate text in monospace after expanding', async () => {
      const user = userEvent.setup();
      render(<EnrichmentPanel enrichment={licensePlateEnrichment} />);
      await user.click(screen.getByText('License Plate'));
      const plateText = screen.getByText('ABC-1234');
      expect(plateText).toHaveClass('font-mono');
    });

    it('displays confidence percentage after expanding', async () => {
      const user = userEvent.setup();
      render(<EnrichmentPanel enrichment={licensePlateEnrichment} />);
      await user.click(screen.getByText('License Plate'));
      expect(screen.getByText('75%')).toBeInTheDocument();
    });
  });

  describe('weather section', () => {
    const weatherEnrichment: EnrichmentData = {
      weather: {
        condition: 'Partly Cloudy',
        confidence: 0.85,
      },
    };

    it('renders weather section when data is present', () => {
      render(<EnrichmentPanel enrichment={weatherEnrichment} />);
      expect(screen.getByText('Weather')).toBeInTheDocument();
    });

    it('displays weather condition after expanding', async () => {
      const user = userEvent.setup();
      render(<EnrichmentPanel enrichment={weatherEnrichment} />);
      await user.click(screen.getByText('Weather'));
      expect(screen.getByText('Partly Cloudy')).toBeInTheDocument();
    });

    it('displays confidence percentage after expanding', async () => {
      const user = userEvent.setup();
      render(<EnrichmentPanel enrichment={weatherEnrichment} />);
      await user.click(screen.getByText('Weather'));
      expect(screen.getByText('85%')).toBeInTheDocument();
    });
  });

  describe('image quality section', () => {
    const imageQualityEnrichment: EnrichmentData = {
      image_quality: {
        score: 0.78,
        issues: ['Low light', 'Motion blur'],
      },
    };

    it('renders image quality section when data is present', () => {
      render(<EnrichmentPanel enrichment={imageQualityEnrichment} />);
      expect(screen.getByText('Image Quality')).toBeInTheDocument();
    });

    it('displays quality score as percentage after expanding', async () => {
      const user = userEvent.setup();
      render(<EnrichmentPanel enrichment={imageQualityEnrichment} />);
      await user.click(screen.getByText('Image Quality'));
      expect(screen.getByText('78%')).toBeInTheDocument();
    });

    it('displays quality issues when present after expanding', async () => {
      const user = userEvent.setup();
      render(<EnrichmentPanel enrichment={imageQualityEnrichment} />);
      await user.click(screen.getByText('Image Quality'));
      expect(screen.getByText('- Low light')).toBeInTheDocument();
      expect(screen.getByText('- Motion blur')).toBeInTheDocument();
    });

    it('does not display issues when array is empty', async () => {
      const noIssues: EnrichmentData = {
        image_quality: {
          score: 0.95,
          issues: [],
        },
      };
      const user = userEvent.setup();
      render(<EnrichmentPanel enrichment={noIssues} />);

      // Expand section
      await user.click(screen.getByText('Image Quality'));

      expect(screen.queryByText('Issues')).not.toBeInTheDocument();
    });

    it('applies green color for high quality scores after expanding', async () => {
      const highQuality: EnrichmentData = {
        image_quality: { score: 0.9, issues: [] },
      };
      const user = userEvent.setup();
      render(<EnrichmentPanel enrichment={highQuality} />);
      await user.click(screen.getByText('Image Quality'));
      const scoreText = screen.getByText('90%');
      expect(scoreText).toHaveClass('text-green-400');
    });

    it('applies yellow color for medium quality scores after expanding', async () => {
      const mediumQuality: EnrichmentData = {
        image_quality: { score: 0.6, issues: [] },
      };
      const user = userEvent.setup();
      render(<EnrichmentPanel enrichment={mediumQuality} />);
      await user.click(screen.getByText('Image Quality'));
      const scoreText = screen.getByText('60%');
      expect(scoreText).toHaveClass('text-yellow-400');
    });

    it('applies red color for low quality scores after expanding', async () => {
      const lowQuality: EnrichmentData = {
        image_quality: { score: 0.3, issues: [] },
      };
      const user = userEvent.setup();
      render(<EnrichmentPanel enrichment={lowQuality} />);
      await user.click(screen.getByText('Image Quality'));
      const scoreText = screen.getByText('30%');
      expect(scoreText).toHaveClass('text-red-400');
    });
  });

  describe('accordion behavior', () => {
    it('can expand and collapse sections by clicking', async () => {
      const user = userEvent.setup();
      const petEnrichment: EnrichmentData = {
        pet: { type: 'Cat', confidence: 0.9 },
      };
      render(<EnrichmentPanel enrichment={petEnrichment} />);

      // Pet section should be collapsed by default (not defaultOpen)
      // The button text is visible but details might be in a panel
      const button = screen.getByText('Pet');

      // Click to expand
      await user.click(button);

      // Should see the type value after expansion
      expect(screen.getByText('Cat')).toBeInTheDocument();
    });

    it('vehicle section is expanded by default', () => {
      const vehicleEnrichment: EnrichmentData = {
        vehicle: { type: 'Truck', color: 'White', confidence: 0.85 },
      };
      render(<EnrichmentPanel enrichment={vehicleEnrichment} />);

      // Details should be visible without clicking
      expect(screen.getByText('Truck')).toBeInTheDocument();
      expect(screen.getByText('White')).toBeInTheDocument();
    });
  });

  describe('confidence indicators', () => {
    it('displays green for high confidence (>= 85%)', () => {
      const highConfidence: EnrichmentData = {
        vehicle: { type: 'Car', color: 'Red', confidence: 0.92 },
      };
      render(<EnrichmentPanel enrichment={highConfidence} />);
      const confidenceText = screen.getByText('92%');
      expect(confidenceText).toHaveClass('text-green-400');
    });

    it('displays yellow for medium confidence (70-85%)', () => {
      const mediumConfidence: EnrichmentData = {
        vehicle: { type: 'Car', color: 'Red', confidence: 0.75 },
      };
      render(<EnrichmentPanel enrichment={mediumConfidence} />);
      const confidenceText = screen.getByText('75%');
      expect(confidenceText).toHaveClass('text-yellow-400');
    });

    it('displays red for low confidence (< 70%)', () => {
      const lowConfidence: EnrichmentData = {
        vehicle: { type: 'Car', color: 'Red', confidence: 0.55 },
      };
      render(<EnrichmentPanel enrichment={lowConfidence} />);
      const confidenceText = screen.getByText('55%');
      expect(confidenceText).toHaveClass('text-red-400');
    });
  });

  describe('partial enrichment data', () => {
    it('renders only available sections', () => {
      const partialEnrichment: EnrichmentData = {
        vehicle: { type: 'Car', color: 'Blue', confidence: 0.9 },
        weather: { condition: 'Sunny', confidence: 0.95 },
      };
      render(<EnrichmentPanel enrichment={partialEnrichment} />);

      expect(screen.getByText('AI Enrichment (2 types)')).toBeInTheDocument();
      expect(screen.getByText('Vehicle')).toBeInTheDocument();
      expect(screen.getByText('Weather')).toBeInTheDocument();
      expect(screen.queryByText('Pet')).not.toBeInTheDocument();
      expect(screen.queryByText('Person Attributes')).not.toBeInTheDocument();
      expect(screen.queryByText('License Plate')).not.toBeInTheDocument();
      expect(screen.queryByText('Image Quality')).not.toBeInTheDocument();
    });

    it('handles enrichment with only image quality', () => {
      const imageOnly: EnrichmentData = {
        image_quality: { score: 0.82, issues: [] },
      };
      render(<EnrichmentPanel enrichment={imageOnly} />);

      expect(screen.getByText('AI Enrichment (1 type)')).toBeInTheDocument();
      expect(screen.getByText('Image Quality')).toBeInTheDocument();
    });

    it('handles enrichment with only license plate', () => {
      const plateOnly: EnrichmentData = {
        license_plate: { text: 'XYZ-9999', confidence: 0.65 },
      };
      render(<EnrichmentPanel enrichment={plateOnly} />);

      expect(screen.getByText('AI Enrichment (1 type)')).toBeInTheDocument();
      expect(screen.getByText('License Plate')).toBeInTheDocument();
    });
  });

  describe('edge cases', () => {
    it('handles confidence at boundary values', async () => {
      const boundaryEnrichment: EnrichmentData = {
        vehicle: { type: 'Car', color: 'Red', confidence: 0.85 }, // exactly at high boundary
        pet: { type: 'Dog', confidence: 0.70 }, // exactly at medium boundary
      };
      const user = userEvent.setup();
      render(<EnrichmentPanel enrichment={boundaryEnrichment} />);

      // 0.85 should be high (green) - Vehicle is open by default
      expect(screen.getByText('85%')).toHaveClass('text-green-400');

      // 0.70 should be medium (yellow) - need to expand pet section
      await user.click(screen.getByText('Pet'));
      expect(screen.getByText('70%')).toHaveClass('text-yellow-400');
    });

    it('handles confidence of 0', () => {
      const zeroConfidence: EnrichmentData = {
        vehicle: { type: 'Unknown', color: 'Unknown', confidence: 0 },
      };
      render(<EnrichmentPanel enrichment={zeroConfidence} />);
      expect(screen.getByText('0%')).toBeInTheDocument();
      expect(screen.getByText('0%')).toHaveClass('text-red-400');
    });

    it('handles confidence of 1 (100%)', () => {
      const perfectConfidence: EnrichmentData = {
        vehicle: { type: 'Car', color: 'Blue', confidence: 1.0 },
      };
      render(<EnrichmentPanel enrichment={perfectConfidence} />);
      expect(screen.getByText('100%')).toBeInTheDocument();
      expect(screen.getByText('100%')).toHaveClass('text-green-400');
    });

    it('handles long text values gracefully after expanding', async () => {
      const longTextEnrichment: EnrichmentData = {
        person: {
          clothing:
            'Very detailed description of clothing including blue denim jacket with patches, white t-shirt, black jeans with ripped knees, and red sneakers',
          action: 'Walking while talking on phone and carrying multiple bags',
          carrying:
            'Large backpack, grocery bags, laptop bag, and what appears to be a musical instrument case',
          confidence: 0.88,
        },
      };
      const user = userEvent.setup();
      render(<EnrichmentPanel enrichment={longTextEnrichment} />);
      await user.click(screen.getByText('Person Attributes'));
      expect(screen.getByText(/Very detailed description/)).toBeInTheDocument();
    });

    it('handles special characters in text after expanding', async () => {
      const specialChars: EnrichmentData = {
        license_plate: { text: 'ABC-123 & XYZ', confidence: 0.8 },
      };
      const user = userEvent.setup();
      render(<EnrichmentPanel enrichment={specialChars} />);
      await user.click(screen.getByText('License Plate'));
      expect(screen.getByText('ABC-123 & XYZ')).toBeInTheDocument();
    });
  });
});
