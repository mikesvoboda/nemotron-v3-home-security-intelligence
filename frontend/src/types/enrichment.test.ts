/**
 * Tests for Enrichment Types
 */

import { describe, it, expect } from 'vitest';

import {
  VEHICLE_TYPES,
  VEHICLE_DAMAGE_TYPES,
  PET_TYPES,
  PERSON_ACTIONS,
  CARRYING_ITEMS,
  WEATHER_CONDITIONS,
  IMAGE_QUALITY_ISSUES,
  isVehicleEnrichment,
  isPetEnrichment,
  isPersonEnrichment,
  isLicensePlateEnrichment,
  isWeatherEnrichment,
  isImageQualityEnrichment,
  isEnrichmentData,
  getEnrichmentValue,
  hasAnyEnrichment,
  countEnrichments,
  type VehicleEnrichment,
  type PetEnrichment,
  type PersonEnrichment,
  type LicensePlateEnrichment,
  type WeatherEnrichment,
  type ImageQualityEnrichment,
  type EnrichmentData,
} from './enrichment';

// ============================================================================
// Constants Tests
// ============================================================================

describe('Enrichment Constants', () => {
  describe('VEHICLE_TYPES', () => {
    it('contains expected vehicle types', () => {
      expect(VEHICLE_TYPES).toContain('sedan');
      expect(VEHICLE_TYPES).toContain('SUV');
      expect(VEHICLE_TYPES).toContain('truck');
    });
  });

  describe('VEHICLE_DAMAGE_TYPES', () => {
    it('contains expected damage types', () => {
      expect(VEHICLE_DAMAGE_TYPES).toContain('dents');
      expect(VEHICLE_DAMAGE_TYPES).toContain('scratches');
      expect(VEHICLE_DAMAGE_TYPES).toContain('tire_flat');
    });
  });

  describe('PET_TYPES', () => {
    it('contains cat and dog', () => {
      expect(PET_TYPES).toEqual(['cat', 'dog']);
    });
  });

  describe('PERSON_ACTIONS', () => {
    it('contains expected actions', () => {
      expect(PERSON_ACTIONS).toContain('walking');
      expect(PERSON_ACTIONS).toContain('standing');
      expect(PERSON_ACTIONS).toContain('running');
    });
  });

  describe('CARRYING_ITEMS', () => {
    it('contains expected items', () => {
      expect(CARRYING_ITEMS).toContain('backpack');
      expect(CARRYING_ITEMS).toContain('package');
      expect(CARRYING_ITEMS).toContain('none');
    });
  });

  describe('WEATHER_CONDITIONS', () => {
    it('contains expected weather conditions', () => {
      expect(WEATHER_CONDITIONS).toContain('clear');
      expect(WEATHER_CONDITIONS).toContain('rain');
      expect(WEATHER_CONDITIONS).toContain('fog');
    });
  });

  describe('IMAGE_QUALITY_ISSUES', () => {
    it('contains expected quality issues', () => {
      expect(IMAGE_QUALITY_ISSUES).toContain('blur');
      expect(IMAGE_QUALITY_ISSUES).toContain('low_light');
      expect(IMAGE_QUALITY_ISSUES).toContain('noise');
    });
  });
});

// ============================================================================
// Type Guard Tests
// ============================================================================

describe('Enrichment Type Guards', () => {
  describe('isVehicleEnrichment', () => {
    it('returns true for valid vehicle enrichment', () => {
      const vehicle: VehicleEnrichment = {
        type: 'sedan',
        color: 'blue',
        confidence: 0.95,
      };
      expect(isVehicleEnrichment(vehicle)).toBe(true);
    });

    it('returns true for vehicle with all optional fields', () => {
      const vehicle: VehicleEnrichment = {
        type: 'truck',
        color: 'white',
        damage: ['dents', 'scratches'],
        commercial: true,
        confidence: 0.88,
      };
      expect(isVehicleEnrichment(vehicle)).toBe(true);
    });

    it('returns false for missing type', () => {
      expect(isVehicleEnrichment({ color: 'blue', confidence: 0.9 })).toBe(false);
    });

    it('returns false for missing color', () => {
      expect(isVehicleEnrichment({ type: 'sedan', confidence: 0.9 })).toBe(false);
    });

    it('returns false for invalid confidence', () => {
      expect(isVehicleEnrichment({ type: 'sedan', color: 'blue', confidence: 1.5 })).toBe(false);
      expect(isVehicleEnrichment({ type: 'sedan', color: 'blue', confidence: -0.1 })).toBe(false);
    });

    it('returns false for null/undefined', () => {
      expect(isVehicleEnrichment(null)).toBe(false);
      expect(isVehicleEnrichment(undefined)).toBe(false);
    });
  });

  describe('isPetEnrichment', () => {
    it('returns true for valid cat enrichment', () => {
      const pet: PetEnrichment = {
        type: 'cat',
        confidence: 0.92,
      };
      expect(isPetEnrichment(pet)).toBe(true);
    });

    it('returns true for valid dog enrichment with breed', () => {
      const pet: PetEnrichment = {
        type: 'dog',
        breed: 'Golden Retriever',
        confidence: 0.85,
      };
      expect(isPetEnrichment(pet)).toBe(true);
    });

    it('returns false for invalid pet type', () => {
      expect(isPetEnrichment({ type: 'bird', confidence: 0.9 })).toBe(false);
    });

    it('returns false for missing type', () => {
      expect(isPetEnrichment({ confidence: 0.9 })).toBe(false);
    });
  });

  describe('isPersonEnrichment', () => {
    it('returns true for minimal person enrichment', () => {
      const person: PersonEnrichment = {
        confidence: 0.9,
      };
      expect(isPersonEnrichment(person)).toBe(true);
    });

    it('returns true for full person enrichment', () => {
      const person: PersonEnrichment = {
        clothing: 'dark jacket',
        action: 'walking',
        carrying: 'backpack',
        suspicious_attire: false,
        service_uniform: false,
        confidence: 0.95,
      };
      expect(isPersonEnrichment(person)).toBe(true);
    });

    it('returns false for invalid confidence', () => {
      expect(isPersonEnrichment({ confidence: 2.0 })).toBe(false);
    });
  });

  describe('isLicensePlateEnrichment', () => {
    it('returns true for valid license plate', () => {
      const plate: LicensePlateEnrichment = {
        text: 'ABC123',
        confidence: 0.99,
      };
      expect(isLicensePlateEnrichment(plate)).toBe(true);
    });

    it('returns false for missing text', () => {
      expect(isLicensePlateEnrichment({ confidence: 0.9 })).toBe(false);
    });
  });

  describe('isWeatherEnrichment', () => {
    it('returns true for valid weather enrichment', () => {
      const weather: WeatherEnrichment = {
        condition: 'clear',
        confidence: 0.88,
      };
      expect(isWeatherEnrichment(weather)).toBe(true);
    });

    it('returns false for missing condition', () => {
      expect(isWeatherEnrichment({ confidence: 0.9 })).toBe(false);
    });
  });

  describe('isImageQualityEnrichment', () => {
    it('returns true for valid image quality enrichment', () => {
      const quality: ImageQualityEnrichment = {
        score: 0.85,
        issues: [],
      };
      expect(isImageQualityEnrichment(quality)).toBe(true);
    });

    it('returns true for quality with issues', () => {
      const quality: ImageQualityEnrichment = {
        score: 0.65,
        issues: ['blur', 'low_light'],
      };
      expect(isImageQualityEnrichment(quality)).toBe(true);
    });

    it('returns false for missing score', () => {
      expect(isImageQualityEnrichment({ issues: [] })).toBe(false);
    });

    it('returns false for missing issues', () => {
      expect(isImageQualityEnrichment({ score: 0.9 })).toBe(false);
    });
  });

  describe('isEnrichmentData', () => {
    it('returns true for empty enrichment data', () => {
      expect(isEnrichmentData({})).toBe(true);
    });

    it('returns true for enrichment data with null fields', () => {
      const data: EnrichmentData = {
        vehicle: null,
        pet: null,
      };
      expect(isEnrichmentData(data)).toBe(true);
    });

    it('returns true for enrichment data with valid vehicle', () => {
      const data: EnrichmentData = {
        vehicle: { type: 'sedan', color: 'red', confidence: 0.9 },
      };
      expect(isEnrichmentData(data)).toBe(true);
    });

    it('returns true for full enrichment data', () => {
      const data: EnrichmentData = {
        vehicle: { type: 'SUV', color: 'black', confidence: 0.95 },
        pet: { type: 'dog', breed: 'Labrador', confidence: 0.85 },
        person: { action: 'walking', confidence: 0.9 },
        license_plate: { text: 'XYZ789', confidence: 0.98 },
        weather: { condition: 'cloudy', confidence: 0.8 },
        image_quality: { score: 0.9, issues: [] },
      };
      expect(isEnrichmentData(data)).toBe(true);
    });

    it('returns false for invalid vehicle in enrichment', () => {
      const data = {
        vehicle: { type: 123, color: 'red', confidence: 0.9 }, // type should be string
      };
      expect(isEnrichmentData(data)).toBe(false);
    });

    it('returns false for null', () => {
      expect(isEnrichmentData(null)).toBe(false);
    });
  });
});

// ============================================================================
// Utility Function Tests
// ============================================================================

describe('Enrichment Utility Functions', () => {
  describe('getEnrichmentValue', () => {
    it('returns value when present', () => {
      const data: EnrichmentData = {
        vehicle: { type: 'sedan', color: 'blue', confidence: 0.9 },
      };
      const vehicle = getEnrichmentValue(data, 'vehicle');
      expect(vehicle).toEqual({ type: 'sedan', color: 'blue', confidence: 0.9 });
    });

    it('returns undefined when field is null', () => {
      const data: EnrichmentData = {
        vehicle: null,
      };
      expect(getEnrichmentValue(data, 'vehicle')).toBeUndefined();
    });

    it('returns undefined when field is undefined', () => {
      const data: EnrichmentData = {};
      expect(getEnrichmentValue(data, 'vehicle')).toBeUndefined();
    });

    it('returns undefined when data is null', () => {
      expect(getEnrichmentValue(null, 'vehicle')).toBeUndefined();
    });

    it('returns undefined when data is undefined', () => {
      expect(getEnrichmentValue(undefined, 'vehicle')).toBeUndefined();
    });
  });

  describe('hasAnyEnrichment', () => {
    it('returns true when any enrichment is present', () => {
      const data: EnrichmentData = {
        weather: { condition: 'clear', confidence: 0.9 },
      };
      expect(hasAnyEnrichment(data)).toBe(true);
    });

    it('returns false for empty object', () => {
      expect(hasAnyEnrichment({})).toBe(false);
    });

    it('returns false when all fields are null', () => {
      const data: EnrichmentData = {
        vehicle: null,
        pet: null,
        person: null,
      };
      expect(hasAnyEnrichment(data)).toBe(false);
    });

    it('returns false for null data', () => {
      expect(hasAnyEnrichment(null)).toBe(false);
    });

    it('returns false for undefined data', () => {
      expect(hasAnyEnrichment(undefined)).toBe(false);
    });
  });

  describe('countEnrichments', () => {
    it('returns correct count', () => {
      const data: EnrichmentData = {
        vehicle: { type: 'sedan', color: 'blue', confidence: 0.9 },
        weather: { condition: 'clear', confidence: 0.8 },
        pet: null,
      };
      expect(countEnrichments(data)).toBe(2);
    });

    it('returns 0 for empty object', () => {
      expect(countEnrichments({})).toBe(0);
    });

    it('returns 0 for all null fields', () => {
      const data: EnrichmentData = {
        vehicle: null,
        pet: null,
        person: null,
        license_plate: null,
        weather: null,
        image_quality: null,
      };
      expect(countEnrichments(data)).toBe(0);
    });

    it('returns 0 for null data', () => {
      expect(countEnrichments(null)).toBe(0);
    });

    it('returns 0 for undefined data', () => {
      expect(countEnrichments(undefined)).toBe(0);
    });
  });
});

// ============================================================================
// Type Inference Tests
// ============================================================================

describe('Type Inference', () => {
  it('narrows vehicle type correctly', () => {
    const data: unknown = {
      type: 'SUV',
      color: 'white',
      damage: ['dents'],
      confidence: 0.95,
    };

    if (isVehicleEnrichment(data)) {
      // TypeScript knows data is VehicleEnrichment
      expect(data.type).toBe('SUV');
      expect(data.color).toBe('white');
      expect(data.damage).toContain('dents');
    }
  });

  it('narrows pet type correctly', () => {
    const data: unknown = {
      type: 'dog',
      breed: 'Beagle',
      confidence: 0.88,
    };

    if (isPetEnrichment(data)) {
      // TypeScript knows data is PetEnrichment
      expect(data.type).toBe('dog');
      expect(data.breed).toBe('Beagle');
    }
  });

  it('allows safe access with getEnrichmentValue', () => {
    const data: EnrichmentData = {
      weather: { condition: 'rain', confidence: 0.9 },
    };

    const weather = getEnrichmentValue(data, 'weather');
    if (weather) {
      // TypeScript knows weather is WeatherEnrichment
      expect(weather.condition).toBe('rain');
    }
  });
});
