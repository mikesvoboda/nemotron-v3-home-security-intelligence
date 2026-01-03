import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import EnrichmentPanel from './EnrichmentPanel';

import type { EnrichmentData } from '../../types/enrichment';

/**
 * Helper function to expand an accordion section by clicking its header
 */
async function expandAccordion(headerText: string) {
  const user = userEvent.setup();
  const header = screen.getByText(headerText);
  const button = header.closest('button');
  if (button) {
    await user.click(button);
  }
}

describe('EnrichmentPanel', () => {
  describe('rendering with no enrichment data', () => {
    it('renders nothing when enrichment_data is undefined', () => {
      const { container } = render(<EnrichmentPanel enrichment_data={undefined} />);
      expect(container.firstChild).toBeNull();
    });

    it('renders nothing when enrichment_data is null', () => {
      const { container } = render(<EnrichmentPanel enrichment_data={null as unknown as EnrichmentData} />);
      expect(container.firstChild).toBeNull();
    });

    it('renders nothing when enrichment_data is an empty object', () => {
      const { container } = render(<EnrichmentPanel enrichment_data={{}} />);
      expect(container.firstChild).toBeNull();
    });
  });

  describe('vehicle enrichment', () => {
    const vehicleEnrichment: EnrichmentData = {
      vehicle: {
        type: 'sedan',
        color: 'blue',
        confidence: 0.92,
      },
    };

    it('renders vehicle section when vehicle data exists', () => {
      render(<EnrichmentPanel enrichment_data={vehicleEnrichment} />);
      expect(screen.getByText('Vehicle')).toBeInTheDocument();
    });

    it('displays vehicle type', async () => {
      render(<EnrichmentPanel enrichment_data={vehicleEnrichment} />);
      await expandAccordion('Vehicle');
      expect(screen.getByText('sedan')).toBeInTheDocument();
    });

    it('displays vehicle color', async () => {
      render(<EnrichmentPanel enrichment_data={vehicleEnrichment} />);
      await expandAccordion('Vehicle');
      expect(screen.getByText('blue')).toBeInTheDocument();
    });

    it('displays confidence badge for vehicle', () => {
      render(<EnrichmentPanel enrichment_data={vehicleEnrichment} />);
      expect(screen.getByText('92%')).toBeInTheDocument();
    });

    it('displays damage when present', async () => {
      const vehicleWithDamage: EnrichmentData = {
        vehicle: {
          type: 'SUV',
          color: 'red',
          damage: ['dents', 'scratches'],
          confidence: 0.88,
        },
      };
      render(<EnrichmentPanel enrichment_data={vehicleWithDamage} />);
      await expandAccordion('Vehicle');
      expect(screen.getByText(/dents/)).toBeInTheDocument();
      expect(screen.getByText(/scratches/)).toBeInTheDocument();
    });

    it('displays commercial indicator when true', async () => {
      const commercialVehicle: EnrichmentData = {
        vehicle: {
          type: 'van',
          color: 'white',
          commercial: true,
          confidence: 0.95,
        },
      };
      render(<EnrichmentPanel enrichment_data={commercialVehicle} />);
      await expandAccordion('Vehicle');
      expect(screen.getByText(/Commercial/)).toBeInTheDocument();
    });

    it('does not display commercial indicator when false', () => {
      const personalVehicle: EnrichmentData = {
        vehicle: {
          type: 'sedan',
          color: 'black',
          commercial: false,
          confidence: 0.90,
        },
      };
      render(<EnrichmentPanel enrichment_data={personalVehicle} />);
      expect(screen.queryByText(/Commercial/)).not.toBeInTheDocument();
    });
  });

  describe('pet enrichment', () => {
    const petEnrichment: EnrichmentData = {
      pet: {
        type: 'dog',
        breed: 'Golden Retriever',
        confidence: 0.95,
      },
    };

    it('renders pet section when pet data exists', () => {
      render(<EnrichmentPanel enrichment_data={petEnrichment} />);
      expect(screen.getByText('Pet')).toBeInTheDocument();
    });

    it('displays pet type', async () => {
      render(<EnrichmentPanel enrichment_data={petEnrichment} />);
      await expandAccordion('Pet');
      expect(screen.getByText('dog')).toBeInTheDocument();
    });

    it('displays breed when present', async () => {
      render(<EnrichmentPanel enrichment_data={petEnrichment} />);
      await expandAccordion('Pet');
      expect(screen.getByText('Golden Retriever')).toBeInTheDocument();
    });

    it('displays confidence badge for pet', () => {
      render(<EnrichmentPanel enrichment_data={petEnrichment} />);
      expect(screen.getByText('95%')).toBeInTheDocument();
    });

    it('handles pet without breed', async () => {
      const petWithoutBreed: EnrichmentData = {
        pet: {
          type: 'cat',
          confidence: 0.87,
        },
      };
      render(<EnrichmentPanel enrichment_data={petWithoutBreed} />);
      await expandAccordion('Pet');
      expect(screen.getByText('cat')).toBeInTheDocument();
      expect(screen.getByText('87%')).toBeInTheDocument();
    });
  });

  describe('person enrichment', () => {
    const personEnrichment: EnrichmentData = {
      person: {
        clothing: 'dark jacket, jeans',
        action: 'walking',
        carrying: 'backpack',
        confidence: 0.91,
      },
    };

    it('renders person section when person data exists', () => {
      render(<EnrichmentPanel enrichment_data={personEnrichment} />);
      expect(screen.getByText('Person')).toBeInTheDocument();
    });

    it('displays clothing description', async () => {
      render(<EnrichmentPanel enrichment_data={personEnrichment} />);
      await expandAccordion('Person');
      expect(screen.getByText('dark jacket, jeans')).toBeInTheDocument();
    });

    it('displays action', async () => {
      render(<EnrichmentPanel enrichment_data={personEnrichment} />);
      await expandAccordion('Person');
      expect(screen.getByText('walking')).toBeInTheDocument();
    });

    it('displays carrying items', async () => {
      render(<EnrichmentPanel enrichment_data={personEnrichment} />);
      await expandAccordion('Person');
      expect(screen.getByText('backpack')).toBeInTheDocument();
    });

    it('displays suspicious attire warning when true', async () => {
      const suspiciousPerson: EnrichmentData = {
        person: {
          suspicious_attire: true,
          confidence: 0.85,
        },
      };
      render(<EnrichmentPanel enrichment_data={suspiciousPerson} />);
      await expandAccordion('Person');
      expect(screen.getByText(/Suspicious Attire/)).toBeInTheDocument();
    });

    it('displays service uniform indicator when true', async () => {
      const serviceWorker: EnrichmentData = {
        person: {
          service_uniform: true,
          confidence: 0.93,
        },
      };
      render(<EnrichmentPanel enrichment_data={serviceWorker} />);
      await expandAccordion('Person');
      expect(screen.getByText(/Service Uniform/)).toBeInTheDocument();
    });

    it('displays confidence badge for person', () => {
      render(<EnrichmentPanel enrichment_data={personEnrichment} />);
      expect(screen.getByText('91%')).toBeInTheDocument();
    });
  });

  describe('license plate enrichment', () => {
    const licensePlateEnrichment: EnrichmentData = {
      license_plate: {
        text: 'ABC-1234',
        confidence: 0.98,
      },
    };

    it('renders license plate section when data exists', () => {
      render(<EnrichmentPanel enrichment_data={licensePlateEnrichment} />);
      expect(screen.getByText('License Plate')).toBeInTheDocument();
    });

    it('displays license plate text', async () => {
      render(<EnrichmentPanel enrichment_data={licensePlateEnrichment} />);
      await expandAccordion('License Plate');
      expect(screen.getByText('ABC-1234')).toBeInTheDocument();
    });

    it('displays confidence badge for license plate', () => {
      render(<EnrichmentPanel enrichment_data={licensePlateEnrichment} />);
      expect(screen.getByText('98%')).toBeInTheDocument();
    });
  });

  describe('weather enrichment', () => {
    const weatherEnrichment: EnrichmentData = {
      weather: {
        condition: 'rain',
        confidence: 0.89,
      },
    };

    it('renders weather section when data exists', () => {
      render(<EnrichmentPanel enrichment_data={weatherEnrichment} />);
      expect(screen.getByText('Weather')).toBeInTheDocument();
    });

    it('displays weather condition', async () => {
      render(<EnrichmentPanel enrichment_data={weatherEnrichment} />);
      await expandAccordion('Weather');
      expect(screen.getByText('rain')).toBeInTheDocument();
    });

    it('displays confidence badge for weather', () => {
      render(<EnrichmentPanel enrichment_data={weatherEnrichment} />);
      expect(screen.getByText('89%')).toBeInTheDocument();
    });
  });

  describe('image quality enrichment', () => {
    const imageQualityEnrichment: EnrichmentData = {
      image_quality: {
        score: 0.75,
        issues: ['blur', 'low_light'],
      },
    };

    it('renders image quality section when data exists', () => {
      render(<EnrichmentPanel enrichment_data={imageQualityEnrichment} />);
      expect(screen.getByText('Image Quality')).toBeInTheDocument();
    });

    it('displays quality score as percentage', () => {
      render(<EnrichmentPanel enrichment_data={imageQualityEnrichment} />);
      expect(screen.getByText('75%')).toBeInTheDocument();
    });

    it('displays quality issues', async () => {
      render(<EnrichmentPanel enrichment_data={imageQualityEnrichment} />);
      await expandAccordion('Image Quality');
      expect(screen.getByText(/blur/)).toBeInTheDocument();
      expect(screen.getByText(/low_light/)).toBeInTheDocument();
    });

    it('handles empty issues array', () => {
      const perfectQuality: EnrichmentData = {
        image_quality: {
          score: 0.98,
          issues: [],
        },
      };
      render(<EnrichmentPanel enrichment_data={perfectQuality} />);
      expect(screen.getByText('98%')).toBeInTheDocument();
    });
  });

  describe('confidence badge colors', () => {
    it('displays green badge for high confidence (>0.9)', () => {
      const highConfidence: EnrichmentData = {
        vehicle: {
          type: 'sedan',
          color: 'blue',
          confidence: 0.95,
        },
      };
      render(<EnrichmentPanel enrichment_data={highConfidence} />);
      const badge = screen.getByText('95%');
      expect(badge).toHaveClass('bg-green-500/20');
    });

    it('displays yellow badge for medium confidence (0.7-0.9)', () => {
      const mediumConfidence: EnrichmentData = {
        vehicle: {
          type: 'sedan',
          color: 'blue',
          confidence: 0.75,
        },
      };
      render(<EnrichmentPanel enrichment_data={mediumConfidence} />);
      const badge = screen.getByText('75%');
      expect(badge).toHaveClass('bg-yellow-500/20');
    });

    it('displays red badge for low confidence (<0.7)', () => {
      const lowConfidence: EnrichmentData = {
        vehicle: {
          type: 'sedan',
          color: 'blue',
          confidence: 0.55,
        },
      };
      render(<EnrichmentPanel enrichment_data={lowConfidence} />);
      const badge = screen.getByText('55%');
      expect(badge).toHaveClass('bg-red-500/20');
    });
  });

  describe('multiple enrichment types', () => {
    const multipleEnrichments: EnrichmentData = {
      vehicle: {
        type: 'pickup',
        color: 'silver',
        confidence: 0.92,
      },
      license_plate: {
        text: 'XYZ-9876',
        confidence: 0.96,
      },
      weather: {
        condition: 'clear',
        confidence: 0.99,
      },
    };

    it('renders all enrichment sections that have data', () => {
      render(<EnrichmentPanel enrichment_data={multipleEnrichments} />);
      expect(screen.getByText('Vehicle')).toBeInTheDocument();
      expect(screen.getByText('License Plate')).toBeInTheDocument();
      expect(screen.getByText('Weather')).toBeInTheDocument();
    });

    it('does not render sections without data', () => {
      render(<EnrichmentPanel enrichment_data={multipleEnrichments} />);
      expect(screen.queryByText('Pet')).not.toBeInTheDocument();
      expect(screen.queryByText('Person')).not.toBeInTheDocument();
      expect(screen.queryByText('Image Quality')).not.toBeInTheDocument();
    });
  });

  describe('accordion behavior', () => {
    const enrichmentData: EnrichmentData = {
      vehicle: {
        type: 'SUV',
        color: 'black',
        confidence: 0.91,
      },
      pet: {
        type: 'dog',
        breed: 'Labrador',
        confidence: 0.88,
      },
    };

    it('can expand vehicle accordion section', async () => {
      const user = userEvent.setup();
      render(<EnrichmentPanel enrichment_data={enrichmentData} />);

      const vehicleHeader = screen.getByText('Vehicle');
      await user.click(vehicleHeader);

      // After click, details should be visible
      expect(screen.getByText('SUV')).toBeInTheDocument();
    });

    it('can expand pet accordion section', async () => {
      const user = userEvent.setup();
      render(<EnrichmentPanel enrichment_data={enrichmentData} />);

      const petHeader = screen.getByText('Pet');
      await user.click(petHeader);

      // After click, details should be visible
      expect(screen.getByText('Labrador')).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    const enrichmentData: EnrichmentData = {
      vehicle: {
        type: 'sedan',
        color: 'red',
        confidence: 0.90,
      },
    };

    it('has accessible panel structure', () => {
      render(<EnrichmentPanel enrichment_data={enrichmentData} />);
      expect(screen.getByTestId('enrichment-panel')).toBeInTheDocument();
    });

    it('has semantic section headers', () => {
      render(<EnrichmentPanel enrichment_data={enrichmentData} />);
      expect(screen.getByText('Vehicle')).toBeInTheDocument();
    });
  });

  describe('className prop', () => {
    it('applies custom className to container', () => {
      const enrichmentData: EnrichmentData = {
        weather: {
          condition: 'sunny',
          confidence: 0.95,
        },
      };
      render(<EnrichmentPanel enrichment_data={enrichmentData} className="custom-class" />);
      const panel = screen.getByTestId('enrichment-panel');
      expect(panel).toHaveClass('custom-class');
    });
  });

  describe('edge cases', () => {
    it('handles confidence at exact boundary values', () => {
      const exactBoundary: EnrichmentData = {
        vehicle: {
          type: 'sedan',
          color: 'white',
          confidence: 0.9, // Exactly at boundary
        },
      };
      render(<EnrichmentPanel enrichment_data={exactBoundary} />);
      expect(screen.getByText('90%')).toBeInTheDocument();
    });

    it('handles very long text values gracefully', async () => {
      const longText: EnrichmentData = {
        person: {
          clothing: 'Very long description of clothing items including dark blue jacket with multiple pockets, light gray hoodie underneath, faded blue jeans',
          confidence: 0.85,
        },
      };
      render(<EnrichmentPanel enrichment_data={longText} />);
      await expandAccordion('Person');
      expect(screen.getByText(/Very long description/)).toBeInTheDocument();
    });

    it('handles special characters in license plate', async () => {
      const specialChars: EnrichmentData = {
        license_plate: {
          text: 'ABC-1234 (CA)',
          confidence: 0.92,
        },
      };
      render(<EnrichmentPanel enrichment_data={specialChars} />);
      await expandAccordion('License Plate');
      expect(screen.getByText('ABC-1234 (CA)')).toBeInTheDocument();
    });
  });
});
