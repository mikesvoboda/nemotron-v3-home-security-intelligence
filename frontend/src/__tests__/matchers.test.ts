/**
 * Unit tests for custom Vitest matchers.
 *
 * These tests validate that the domain-specific matchers correctly identify
 * valid and invalid data structures, and provide clear error messages.
 */

import { describe, expect, it } from 'vitest';

import './matchers'; // Import to register custom matchers

describe('Custom Matchers', () => {
  describe('toBeValidCamera', () => {
    it('passes for valid camera object', () => {
      const validCamera = {
        id: 'front_door',
        name: 'Front Door Camera',
        folder_path: '/export/foscam/front_door',
        status: 'online',
        created_at: new Date().toISOString(),
        last_seen_at: new Date().toISOString(),
      };

      expect(validCamera).toBeValidCamera();
    });

    it('passes for camera without optional last_seen_at', () => {
      const validCamera = {
        id: 'front_door',
        name: 'Front Door',
        folder_path: '/export/foscam/front_door',
        status: 'online',
        created_at: new Date().toISOString(),
      };

      expect(validCamera).toBeValidCamera();
    });

    it('fails for camera missing id', () => {
      const invalidCamera = {
        name: 'Front Door',
        folder_path: '/export/foscam/front_door',
        status: 'online',
        created_at: new Date().toISOString(),
      };

      expect(() => expect(invalidCamera).toBeValidCamera()).toThrow();
    });

    it('fails for camera with empty name', () => {
      const invalidCamera = {
        id: 'front_door',
        name: '',
        folder_path: '/export/foscam/front_door',
        status: 'online',
        created_at: new Date().toISOString(),
      };

      expect(() => expect(invalidCamera).toBeValidCamera()).toThrow();
    });

    it('fails for camera with invalid status', () => {
      const invalidCamera = {
        id: 'front_door',
        name: 'Front Door',
        folder_path: '/export/foscam/front_door',
        status: 'active', // Invalid status
        created_at: new Date().toISOString(),
      };

      expect(() => expect(invalidCamera).toBeValidCamera()).toThrow();
    });

    it('fails for camera with invalid created_at', () => {
      const invalidCamera = {
        id: 'front_door',
        name: 'Front Door',
        folder_path: '/export/foscam/front_door',
        status: 'online',
        created_at: 'not-a-date',
      };

      expect(() => expect(invalidCamera).toBeValidCamera()).toThrow();
    });

    it('fails for non-object input', () => {
      expect(() => expect('not-an-object').toBeValidCamera()).toThrow();
      expect(() => expect(null).toBeValidCamera()).toThrow();
      expect(() => expect(undefined).toBeValidCamera()).toThrow();
    });
  });

  describe('toBeValidEvent', () => {
    it('passes for valid event object', () => {
      const validEvent = {
        id: 1,
        camera_id: 'front_door',
        started_at: new Date().toISOString(),
        ended_at: new Date().toISOString(),
        risk_score: 75,
        risk_level: 'medium',
        summary: 'Person detected',
        reasoning: 'Walking by',
        reviewed: false,
        detection_count: 5,
        detection_ids: [1, 2, 3, 4, 5],
      };

      expect(validEvent).toBeValidEvent();
    });

    it('passes for minimal valid event', () => {
      const minimalEvent = {
        id: 1,
        camera_id: 'front_door',
        started_at: new Date().toISOString(),
      };

      expect(minimalEvent).toBeValidEvent();
    });

    it('fails for event with negative id', () => {
      const invalidEvent = {
        id: -1,
        camera_id: 'front_door',
        started_at: new Date().toISOString(),
      };

      expect(() => expect(invalidEvent).toBeValidEvent()).toThrow();
    });

    it('fails for event missing camera_id', () => {
      const invalidEvent = {
        id: 1,
        started_at: new Date().toISOString(),
      };

      expect(() => expect(invalidEvent).toBeValidEvent()).toThrow();
    });

    it('fails for event with invalid risk_score', () => {
      const invalidEvent = {
        id: 1,
        camera_id: 'front_door',
        started_at: new Date().toISOString(),
        risk_score: 150, // Out of range
      };

      expect(() => expect(invalidEvent).toBeValidEvent()).toThrow();
    });

    it('fails for event with invalid risk_level', () => {
      const invalidEvent = {
        id: 1,
        camera_id: 'front_door',
        started_at: new Date().toISOString(),
        risk_level: 'super-high', // Invalid level
      };

      expect(() => expect(invalidEvent).toBeValidEvent()).toThrow();
    });

    it('fails for event with non-boolean reviewed', () => {
      const invalidEvent = {
        id: 1,
        camera_id: 'front_door',
        started_at: new Date().toISOString(),
        reviewed: 'yes', // Should be boolean
      };

      expect(() => expect(invalidEvent).toBeValidEvent()).toThrow();
    });

    it('fails for event with negative detection_count', () => {
      const invalidEvent = {
        id: 1,
        camera_id: 'front_door',
        started_at: new Date().toISOString(),
        detection_count: -5,
      };

      expect(() => expect(invalidEvent).toBeValidEvent()).toThrow();
    });

    it('fails for event with non-number detection_ids', () => {
      const invalidEvent = {
        id: 1,
        camera_id: 'front_door',
        started_at: new Date().toISOString(),
        detection_ids: [1, 'two', 3], // Contains non-number
      };

      expect(() => expect(invalidEvent).toBeValidEvent()).toThrow();
    });
  });

  describe('toBeValidDetection', () => {
    it('passes for valid detection object', () => {
      const validDetection = {
        id: 1,
        camera_id: 'front_door',
        file_path: '/export/foscam/front_door/image.jpg',
        detected_at: new Date().toISOString(),
        object_type: 'person',
        confidence: 0.95,
        bbox_x: 100,
        bbox_y: 150,
        bbox_width: 200,
        bbox_height: 400,
        media_type: 'image',
      };

      expect(validDetection).toBeValidDetection();
    });

    it('passes for minimal valid detection', () => {
      const minimalDetection = {
        id: 1,
        camera_id: 'front_door',
        file_path: '/path/to/file.jpg',
        detected_at: new Date().toISOString(),
      };

      expect(minimalDetection).toBeValidDetection();
    });

    it('fails for detection with confidence out of range', () => {
      const invalidDetection = {
        id: 1,
        camera_id: 'front_door',
        file_path: '/path/to/file.jpg',
        detected_at: new Date().toISOString(),
        confidence: 1.5, // Out of 0-1 range
      };

      expect(() => expect(invalidDetection).toBeValidDetection()).toThrow();
    });

    it('fails for detection with partial bounding box', () => {
      const invalidDetection = {
        id: 1,
        camera_id: 'front_door',
        file_path: '/path/to/file.jpg',
        detected_at: new Date().toISOString(),
        bbox_x: 100,
        bbox_y: 150,
        // Missing bbox_width and bbox_height
      };

      expect(() => expect(invalidDetection).toBeValidDetection()).toThrow();
    });

    it('fails for detection with negative bbox values', () => {
      const invalidDetection = {
        id: 1,
        camera_id: 'front_door',
        file_path: '/path/to/file.jpg',
        detected_at: new Date().toISOString(),
        bbox_x: -100,
        bbox_y: 150,
        bbox_width: 200,
        bbox_height: 400,
      };

      expect(() => expect(invalidDetection).toBeValidDetection()).toThrow();
    });

    it('fails for detection with invalid media_type', () => {
      const invalidDetection = {
        id: 1,
        camera_id: 'front_door',
        file_path: '/path/to/file.jpg',
        detected_at: new Date().toISOString(),
        media_type: 'audio', // Invalid type
      };

      expect(() => expect(invalidDetection).toBeValidDetection()).toThrow();
    });

    it('fails for detection with negative duration', () => {
      const invalidDetection = {
        id: 1,
        camera_id: 'front_door',
        file_path: '/path/to/video.mp4',
        detected_at: new Date().toISOString(),
        duration: -5, // Negative
      };

      expect(() => expect(invalidDetection).toBeValidDetection()).toThrow();
    });
  });

  describe('toHaveRiskLevel', () => {
    it('passes when object has expected risk level', () => {
      const obj = { risk_level: 'high' };
      expect(obj).toHaveRiskLevel('high');
    });

    it('fails when risk level does not match', () => {
      const obj = { risk_level: 'low' };
      expect(() => expect(obj).toHaveRiskLevel('high')).toThrow();
    });

    it('fails for non-object input', () => {
      expect(() => expect('not-an-object').toHaveRiskLevel('low')).toThrow();
    });
  });

  describe('toBeValidRiskScore', () => {
    it('passes for valid risk scores', () => {
      expect(0).toBeValidRiskScore();
      expect(50).toBeValidRiskScore();
      expect(100).toBeValidRiskScore();
      expect(75.5).toBeValidRiskScore();
    });

    it('fails for negative risk score', () => {
      expect(() => expect(-1).toBeValidRiskScore()).toThrow();
    });

    it('fails for risk score above 100', () => {
      expect(() => expect(101).toBeValidRiskScore()).toThrow();
    });

    it('fails for non-numeric value', () => {
      expect(() => expect('high').toBeValidRiskScore()).toThrow();
    });
  });

  describe('toBeAccessible', () => {
    it('passes for button with text content', () => {
      const button = document.createElement('button');
      button.textContent = 'Click me';
      expect(button).toBeAccessible();
    });

    it('passes for button with aria-label', () => {
      const button = document.createElement('button');
      button.setAttribute('aria-label', 'Close dialog');
      expect(button).toBeAccessible();
    });

    it('passes for image with alt text', () => {
      const img = document.createElement('img');
      img.setAttribute('alt', 'Description');
      expect(img).toBeAccessible();
    });

    it('passes for non-interactive elements', () => {
      const div = document.createElement('div');
      expect(div).toBeAccessible();
    });

    it('fails for button without accessible name', () => {
      const button = document.createElement('button');
      expect(() => expect(button).toBeAccessible()).toThrow();
    });

    it('fails for image without alt text', () => {
      const img = document.createElement('img');
      expect(() => expect(img).toBeAccessible()).toThrow();
    });

    it('fails for non-HTMLElement input', () => {
      expect(() => expect('not-an-element').toBeAccessible()).toThrow();
    });
  });

  describe('toBeValidISODate', () => {
    it('passes for valid ISO 8601 date strings', () => {
      expect(new Date().toISOString()).toBeValidISODate();
      expect('2025-12-23T12:00:00.000Z').toBeValidISODate();
    });

    it('fails for invalid date strings', () => {
      expect(() => expect('not-a-date').toBeValidISODate()).toThrow();
      expect(() => expect('2025-13-45').toBeValidISODate()).toThrow();
      expect(() => expect('12/23/2025').toBeValidISODate()).toThrow();
    });

    it('fails for non-string input', () => {
      expect(() => expect(123).toBeValidISODate()).toThrow();
      expect(() => expect(new Date()).toBeValidISODate()).toThrow();
    });
  });

  describe('toBeValidPaginatedResponse', () => {
    it('passes for valid paginated response', () => {
      const validResponse = {
        events: [
          { id: 1, camera_id: 'front_door' },
          { id: 2, camera_id: 'back_door' },
        ],
        count: 2,
        limit: 50,
        offset: 0,
      };

      expect(validResponse).toBeValidPaginatedResponse('events');
    });

    it('passes for empty collection', () => {
      const validResponse = {
        events: [],
        count: 0,
        limit: 50,
        offset: 0,
      };

      expect(validResponse).toBeValidPaginatedResponse('events');
    });

    it('fails for response missing collection key', () => {
      const invalidResponse = {
        count: 0,
        limit: 50,
        offset: 0,
      };

      expect(() => expect(invalidResponse).toBeValidPaginatedResponse('events')).toThrow();
    });

    it('fails for non-array collection', () => {
      const invalidResponse = {
        events: 'not-an-array',
        count: 0,
        limit: 50,
        offset: 0,
      };

      expect(() => expect(invalidResponse).toBeValidPaginatedResponse('events')).toThrow();
    });

    it('fails for missing count field', () => {
      const invalidResponse = {
        events: [],
        limit: 50,
        offset: 0,
      };

      expect(() => expect(invalidResponse).toBeValidPaginatedResponse('events')).toThrow();
    });

    it('fails for negative count', () => {
      const invalidResponse = {
        events: [],
        count: -1,
        limit: 50,
        offset: 0,
      };

      expect(() => expect(invalidResponse).toBeValidPaginatedResponse('events')).toThrow();
    });

    it('fails for non-positive limit', () => {
      const invalidResponse = {
        events: [],
        count: 0,
        limit: 0,
        offset: 0,
      };

      expect(() => expect(invalidResponse).toBeValidPaginatedResponse('events')).toThrow();
    });

    it('fails for negative offset', () => {
      const invalidResponse = {
        events: [],
        count: 0,
        limit: 50,
        offset: -10,
      };

      expect(() => expect(invalidResponse).toBeValidPaginatedResponse('events')).toThrow();
    });

    it('fails for non-object input', () => {
      expect(() => expect('not-an-object').toBeValidPaginatedResponse('events')).toThrow();
    });
  });

  describe('Matcher error messages', () => {
    it('provides clear error message for invalid camera', () => {
      const invalidCamera = {
        id: 'front_door',
        name: '',
        folder_path: '/export/foscam/front_door',
        status: 'invalid-status',
        created_at: 'not-a-date',
      };

      try {
        expect(invalidCamera).toBeValidCamera();
        throw new Error('Should have thrown');
      } catch (error) {
        expect((error as Error).message).toContain('non-empty');
        expect((error as Error).message).toContain('status must be one of');
      }
    });

    it('provides clear error message for invalid event', () => {
      const invalidEvent = {
        id: -1,
        camera_id: '',
        started_at: 'invalid-date',
        risk_score: 150,
      };

      try {
        expect(invalidEvent).toBeValidEvent();
        throw new Error('Should have thrown');
      } catch (error) {
        expect((error as Error).message).toContain('positive integer');
        expect((error as Error).message).toContain('non-empty');
      }
    });
  });
});
