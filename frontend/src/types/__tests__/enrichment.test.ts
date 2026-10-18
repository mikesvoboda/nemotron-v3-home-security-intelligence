/**
 * TDD Tests for Enrichment Type Guards and Utilities (NEM-5078)
 *
 * These tests define the behavior of type guards and utility functions
 * for enrichment data validation and manipulation.
 *
 * Type guards tested:
 * - isVehicleEnrichment
 * - isPetEnrichment
 * - isPersonEnrichment
 * - isPostureEnrichment
 * - isLicensePlateEnrichment
 * - isWeatherEnrichment
 * - isImageQualityEnrichment
 * - isPoseEnrichment
 *
 * Utilities tested:
 * - hasAnyEnrichment
 * - countEnrichments
 * - getEnrichmentValue
 *
 * @see frontend/src/types/enrichment.ts
 */

import { describe, it, expect } from 'vitest';

import {
  isVehicleEnrichment,
  isPetEnrichment,
  isPersonEnrichment,
  isPostureEnrichment,
  isLicensePlateEnrichment,
  isWeatherEnrichment,
  isImageQualityEnrichment,
  isPoseEnrichment,
  hasAnyEnrichment,
  countEnrichments,
  getEnrichmentValue,
} from '../enrichment';

import type {
  VehicleEnrichment,
  PetEnrichment,
  PersonEnrichment,
  PostureEnrichment,
  LicensePlateEnrichment,
  WeatherEnrichment,
  ImageQualityEnrichment,
  PoseEnrichment,
  EnrichmentData,
} from '../enrichment';

// ============================================================================
// Type Guard Tests: VehicleEnrichment
// ============================================================================

describe('isVehicleEnrichment type guard', () => {
  it('test_valid_vehicle_enrichment_returns_true', () => {
    const vehicle: VehicleEnrichment = {
      type: 'sedan',
      color: 'blue',
      confidence: 0.92,
    };

    expect(isVehicleEnrichment(vehicle)).toBe(true);
  });

  it('test_vehicle_with_optional_fields_returns_true', () => {
    const vehicle: VehicleEnrichment = {
      type: 'SUV',
      color: 'black',
      damage: ['dents', 'scratches'],
      commercial: true,
      caption: 'Black SUV with damage',
      confidence: 0.88,
    };

    expect(isVehicleEnrichment(vehicle)).toBe(true);
  });

  it('test_vehicle_missing_type_returns_false', () => {
    const invalid = {
      color: 'red',
      confidence: 0.9,
    };

    expect(isVehicleEnrichment(invalid)).toBe(false);
  });

  it('test_vehicle_missing_color_returns_false', () => {
    const invalid = {
      type: 'sedan',
      confidence: 0.9,
    };

    expect(isVehicleEnrichment(invalid)).toBe(false);
  });

  it('test_vehicle_missing_confidence_returns_false', () => {
    const invalid = {
      type: 'sedan',
      color: 'blue',
    };

    expect(isVehicleEnrichment(invalid)).toBe(false);
  });

  it('test_vehicle_invalid_confidence_returns_false', () => {
    const invalid = {
      type: 'sedan',
      color: 'blue',
      confidence: 1.5, // Invalid: > 1
    };

    expect(isVehicleEnrichment(invalid)).toBe(false);
  });

  it('test_vehicle_null_returns_false', () => {
    expect(isVehicleEnrichment(null)).toBe(false);
  });

  it('test_vehicle_undefined_returns_false', () => {
    expect(isVehicleEnrichment(undefined)).toBe(false);
  });
});

// ============================================================================
// Type Guard Tests: PetEnrichment
// ============================================================================

describe('isPetEnrichment type guard', () => {
  it('test_valid_pet_enrichment_returns_true', () => {
    const pet: PetEnrichment = {
      type: 'dog',
      confidence: 0.88,
    };

    expect(isPetEnrichment(pet)).toBe(true);
  });

  it('test_pet_with_breed_returns_true', () => {
    const pet: PetEnrichment = {
      type: 'cat',
      breed: 'Siamese',
      confidence: 0.85,
    };

    expect(isPetEnrichment(pet)).toBe(true);
  });

  it('test_pet_missing_type_returns_false', () => {
    const invalid = {
      breed: 'Labrador',
      confidence: 0.9,
    };

    expect(isPetEnrichment(invalid)).toBe(false);
  });

  it('test_pet_invalid_type_returns_false', () => {
    const invalid = {
      type: 'bird', // Not a valid PetType
      confidence: 0.9,
    };

    expect(isPetEnrichment(invalid)).toBe(false);
  });

  it('test_pet_missing_confidence_returns_false', () => {
    const invalid = {
      type: 'dog',
    };

    expect(isPetEnrichment(invalid)).toBe(false);
  });

  it('test_pet_null_returns_false', () => {
    expect(isPetEnrichment(null)).toBe(false);
  });
});

// ============================================================================
// Type Guard Tests: PersonEnrichment
// ============================================================================

describe('isPersonEnrichment type guard', () => {
  it('test_valid_person_enrichment_returns_true', () => {
    const person: PersonEnrichment = {
      clothing: 'dark hoodie',
      confidence: 0.85,
    };

    expect(isPersonEnrichment(person)).toBe(true);
  });

  it('test_person_with_all_fields_returns_true', () => {
    const person: PersonEnrichment = {
      clothing: 'blue shirt, jeans',
      action: 'walking',
      carrying: 'backpack',
      suspicious_attire: true,
      service_uniform: false,
      caption: 'Person in casual attire',
      confidence: 0.91,
    };

    expect(isPersonEnrichment(person)).toBe(true);
  });

  it('test_person_only_confidence_returns_true', () => {
    // PersonEnrichment has no required fields beyond confidence
    const person: PersonEnrichment = {
      confidence: 0.8,
    };

    expect(isPersonEnrichment(person)).toBe(true);
  });

  it('test_person_missing_confidence_returns_false', () => {
    const invalid = {
      clothing: 'red jacket',
    };

    expect(isPersonEnrichment(invalid)).toBe(false);
  });

  it('test_person_null_returns_false', () => {
    expect(isPersonEnrichment(null)).toBe(false);
  });
});

// ============================================================================
// Type Guard Tests: PostureEnrichment
// ============================================================================

describe('isPostureEnrichment type guard', () => {
  it('test_valid_posture_enrichment_returns_true', () => {
    const posture: PostureEnrichment = {
      posture: 'standing',
      confidence: 0.92,
    };

    expect(isPostureEnrichment(posture)).toBe(true);
  });

  it('test_posture_missing_posture_field_returns_false', () => {
    const invalid = {
      confidence: 0.9,
    };

    expect(isPostureEnrichment(invalid)).toBe(false);
  });

  it('test_posture_missing_confidence_returns_false', () => {
    const invalid = {
      posture: 'sitting',
    };

    expect(isPostureEnrichment(invalid)).toBe(false);
  });

  it('test_posture_null_returns_false', () => {
    expect(isPostureEnrichment(null)).toBe(false);
  });
});

// ============================================================================
// Type Guard Tests: LicensePlateEnrichment
// ============================================================================

describe('isLicensePlateEnrichment type guard', () => {
  it('test_valid_license_plate_returns_true', () => {
    const plate: LicensePlateEnrichment = {
      text: 'ABC-1234',
      confidence: 0.96,
    };

    expect(isLicensePlateEnrichment(plate)).toBe(true);
  });

  it('test_license_plate_missing_text_returns_false', () => {
    const invalid = {
      confidence: 0.95,
    };

    expect(isLicensePlateEnrichment(invalid)).toBe(false);
  });

  it('test_license_plate_missing_confidence_returns_false', () => {
    const invalid = {
      text: 'XYZ-9876',
    };

    expect(isLicensePlateEnrichment(invalid)).toBe(false);
  });

  it('test_license_plate_null_returns_false', () => {
    expect(isLicensePlateEnrichment(null)).toBe(false);
  });
});

// ============================================================================
// Type Guard Tests: WeatherEnrichment
// ============================================================================

describe('isWeatherEnrichment type guard', () => {
  it('test_valid_weather_enrichment_returns_true', () => {
    const weather: WeatherEnrichment = {
      condition: 'rain',
      confidence: 0.78,
    };

    expect(isWeatherEnrichment(weather)).toBe(true);
  });

  it('test_weather_missing_condition_returns_false', () => {
    const invalid = {
      confidence: 0.8,
    };

    expect(isWeatherEnrichment(invalid)).toBe(false);
  });

  it('test_weather_missing_confidence_returns_false', () => {
    const invalid = {
      condition: 'clear',
    };

    expect(isWeatherEnrichment(invalid)).toBe(false);
  });

  it('test_weather_null_returns_false', () => {
    expect(isWeatherEnrichment(null)).toBe(false);
  });
});

// ============================================================================
// Type Guard Tests: ImageQualityEnrichment
// ============================================================================

describe('isImageQualityEnrichment type guard', () => {
  it('test_valid_image_quality_returns_true', () => {
    const quality: ImageQualityEnrichment = {
      score: 0.85,
      issues: ['blur', 'noise'],
    };

    expect(isImageQualityEnrichment(quality)).toBe(true);
  });

  it('test_image_quality_empty_issues_returns_true', () => {
    const quality: ImageQualityEnrichment = {
      score: 0.92,
      issues: [],
    };

    expect(isImageQualityEnrichment(quality)).toBe(true);
  });

  it('test_image_quality_missing_score_returns_false', () => {
    const invalid = {
      issues: ['blur'],
    };

    expect(isImageQualityEnrichment(invalid)).toBe(false);
  });

  it('test_image_quality_missing_issues_returns_false', () => {
    const invalid = {
      score: 0.9,
    };

    expect(isImageQualityEnrichment(invalid)).toBe(false);
  });

  it('test_image_quality_issues_not_array_returns_false', () => {
    const invalid = {
      score: 0.9,
      issues: 'blur',
    };

    expect(isImageQualityEnrichment(invalid)).toBe(false);
  });

  it('test_image_quality_null_returns_false', () => {
    expect(isImageQualityEnrichment(null)).toBe(false);
  });
});

// ============================================================================
// Type Guard Tests: PoseEnrichment
// ============================================================================

describe('isPoseEnrichment type guard', () => {
  it('test_valid_pose_enrichment_returns_true', () => {
    const pose: PoseEnrichment = {
      posture: 'standing',
      alerts: [],
      keypoints: [
        [0.5, 0.3, 0.95],
        [0.52, 0.35, 0.9],
      ],
      keypoint_count: 15,
      confidence: 0.91,
    };

    expect(isPoseEnrichment(pose)).toBe(true);
  });

  it('test_pose_with_alerts_returns_true', () => {
    const pose: PoseEnrichment = {
      posture: 'crouching',
      alerts: ['crouching', 'hands_raised'],
      keypoints: [],
      keypoint_count: 12,
      confidence: 0.87,
    };

    expect(isPoseEnrichment(pose)).toBe(true);
  });

  it('test_pose_missing_posture_returns_false', () => {
    const invalid = {
      alerts: [],
      keypoints: [],
      confidence: 0.9,
    };

    expect(isPoseEnrichment(invalid)).toBe(false);
  });

  it('test_pose_missing_alerts_returns_false', () => {
    const invalid = {
      posture: 'walking',
      keypoints: [],
      confidence: 0.9,
    };

    expect(isPoseEnrichment(invalid)).toBe(false);
  });

  it('test_pose_missing_keypoints_returns_false', () => {
    const invalid = {
      posture: 'walking',
      alerts: [],
      confidence: 0.9,
    };

    expect(isPoseEnrichment(invalid)).toBe(false);
  });

  it('test_pose_alerts_not_array_returns_false', () => {
    const invalid = {
      posture: 'walking',
      alerts: 'crouching',
      keypoints: [],
      confidence: 0.9,
    };

    expect(isPoseEnrichment(invalid)).toBe(false);
  });

  it('test_pose_keypoints_not_array_returns_false', () => {
    const invalid = {
      posture: 'walking',
      alerts: [],
      keypoints: {},
      confidence: 0.9,
    };

    expect(isPoseEnrichment(invalid)).toBe(false);
  });

  it('test_pose_null_returns_false', () => {
    expect(isPoseEnrichment(null)).toBe(false);
  });
});

// ============================================================================
// Utility Function Tests: hasAnyEnrichment
// ============================================================================

describe('hasAnyEnrichment utility', () => {
  it('test_enrichment_with_data_returns_true', () => {
    const data: EnrichmentData = {
      vehicle: {
        type: 'sedan',
        color: 'blue',
        confidence: 0.9,
      },
    };

    expect(hasAnyEnrichment(data)).toBe(true);
  });

  it('test_enrichment_with_multiple_fields_returns_true', () => {
    const data: EnrichmentData = {
      vehicle: {
        type: 'SUV',
        color: 'black',
        confidence: 0.92,
      },
      pet: {
        type: 'dog',
        confidence: 0.85,
      },
    };

    expect(hasAnyEnrichment(data)).toBe(true);
  });

  it('test_empty_enrichment_object_returns_false', () => {
    const data: EnrichmentData = {};

    expect(hasAnyEnrichment(data)).toBe(false);
  });

  it('test_enrichment_with_null_fields_returns_false', () => {
    const data: EnrichmentData = {
      vehicle: null,
      pet: null,
      person: null,
    };

    expect(hasAnyEnrichment(data)).toBe(false);
  });

  it('test_enrichment_with_undefined_fields_returns_false', () => {
    const data: EnrichmentData = {
      vehicle: undefined,
      pet: undefined,
    };

    expect(hasAnyEnrichment(data)).toBe(false);
  });

  it('test_null_enrichment_data_returns_false', () => {
    expect(hasAnyEnrichment(null)).toBe(false);
  });

  it('test_undefined_enrichment_data_returns_false', () => {
    expect(hasAnyEnrichment(undefined)).toBe(false);
  });
});

// ============================================================================
// Utility Function Tests: countEnrichments
// ============================================================================

describe('countEnrichments utility', () => {
  it('test_count_zero_for_empty_object', () => {
    const data: EnrichmentData = {};

    expect(countEnrichments(data)).toBe(0);
  });

  it('test_count_one_for_single_enrichment', () => {
    const data: EnrichmentData = {
      vehicle: {
        type: 'sedan',
        color: 'blue',
        confidence: 0.9,
      },
    };

    expect(countEnrichments(data)).toBe(1);
  });

  it('test_count_multiple_enrichments', () => {
    const data: EnrichmentData = {
      vehicle: {
        type: 'SUV',
        color: 'black',
        confidence: 0.92,
      },
      pet: {
        type: 'dog',
        confidence: 0.85,
      },
      person: {
        clothing: 'blue shirt',
        confidence: 0.88,
      },
    };

    expect(countEnrichments(data)).toBe(3);
  });

  it('test_count_ignores_null_values', () => {
    const data: EnrichmentData = {
      vehicle: {
        type: 'sedan',
        color: 'red',
        confidence: 0.9,
      },
      pet: null,
      person: null,
    };

    expect(countEnrichments(data)).toBe(1);
  });

  it('test_count_ignores_undefined_values', () => {
    const data: EnrichmentData = {
      vehicle: {
        type: 'sedan',
        color: 'red',
        confidence: 0.9,
      },
      pet: undefined,
    };

    expect(countEnrichments(data)).toBe(1);
  });

  it('test_count_zero_for_null_data', () => {
    expect(countEnrichments(null)).toBe(0);
  });

  it('test_count_zero_for_undefined_data', () => {
    expect(countEnrichments(undefined)).toBe(0);
  });

  it('test_count_all_enrichment_types', () => {
    const data: EnrichmentData = {
      vehicle: { type: 'sedan', color: 'blue', confidence: 0.9 },
      pet: { type: 'dog', confidence: 0.85 },
      person: { confidence: 0.88 },
      posture: { posture: 'standing', confidence: 0.91 },
      license_plate: { text: 'ABC-1234', confidence: 0.96 },
      weather: { condition: 'clear', confidence: 0.82 },
      image_quality: { score: 0.87, issues: [] },
      pose: { posture: 'walking', alerts: [], keypoints: [], confidence: 0.93 },
    };

    expect(countEnrichments(data)).toBe(8);
  });
});

// ============================================================================
// Utility Function Tests: getEnrichmentValue
// ============================================================================

describe('getEnrichmentValue utility', () => {
  it('test_get_existing_vehicle_enrichment', () => {
    const data: EnrichmentData = {
      vehicle: {
        type: 'sedan',
        color: 'blue',
        confidence: 0.9,
      },
    };

    const vehicle = getEnrichmentValue(data, 'vehicle');
    expect(vehicle).toBeDefined();
    expect(vehicle?.type).toBe('sedan');
  });

  it('test_get_existing_pet_enrichment', () => {
    const data: EnrichmentData = {
      pet: {
        type: 'cat',
        breed: 'Siamese',
        confidence: 0.85,
      },
    };

    const pet = getEnrichmentValue(data, 'pet');
    expect(pet).toBeDefined();
    expect(pet?.type).toBe('cat');
    expect(pet?.breed).toBe('Siamese');
  });

  it('test_get_null_field_returns_undefined', () => {
    const data: EnrichmentData = {
      vehicle: null,
    };

    const vehicle = getEnrichmentValue(data, 'vehicle');
    expect(vehicle).toBeUndefined();
  });

  it('test_get_undefined_field_returns_undefined', () => {
    const data: EnrichmentData = {
      vehicle: undefined,
    };

    const vehicle = getEnrichmentValue(data, 'vehicle');
    expect(vehicle).toBeUndefined();
  });

  it('test_get_from_null_data_returns_undefined', () => {
    const vehicle = getEnrichmentValue(null, 'vehicle');
    expect(vehicle).toBeUndefined();
  });

  it('test_get_from_undefined_data_returns_undefined', () => {
    const vehicle = getEnrichmentValue(undefined, 'vehicle');
    expect(vehicle).toBeUndefined();
  });

  it('test_get_missing_field_returns_undefined', () => {
    const data: EnrichmentData = {
      vehicle: {
        type: 'sedan',
        color: 'blue',
        confidence: 0.9,
      },
    };

    const pet = getEnrichmentValue(data, 'pet');
    expect(pet).toBeUndefined();
  });

  it('test_get_all_enrichment_types', () => {
    const data: EnrichmentData = {
      vehicle: { type: 'sedan', color: 'blue', confidence: 0.9 },
      pet: { type: 'dog', confidence: 0.85 },
      person: { confidence: 0.88 },
      posture: { posture: 'standing', confidence: 0.91 },
      license_plate: { text: 'ABC-1234', confidence: 0.96 },
      weather: { condition: 'clear', confidence: 0.82 },
      image_quality: { score: 0.87, issues: [] },
      pose: { posture: 'walking', alerts: [], keypoints: [], confidence: 0.93 },
    };

    expect(getEnrichmentValue(data, 'vehicle')).toBeDefined();
    expect(getEnrichmentValue(data, 'pet')).toBeDefined();
    expect(getEnrichmentValue(data, 'person')).toBeDefined();
    expect(getEnrichmentValue(data, 'posture')).toBeDefined();
    expect(getEnrichmentValue(data, 'license_plate')).toBeDefined();
    expect(getEnrichmentValue(data, 'weather')).toBeDefined();
    expect(getEnrichmentValue(data, 'image_quality')).toBeDefined();
    expect(getEnrichmentValue(data, 'pose')).toBeDefined();
  });
});
