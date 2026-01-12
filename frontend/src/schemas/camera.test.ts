/**
 * Unit tests for Camera Zod validation schemas.
 *
 * These tests verify that the frontend validation rules match the backend
 * Pydantic schemas in backend/api/schemas/camera.py
 */

import { describe, expect, it } from 'vitest';

import {
  cameraCreateSchema,
  cameraFormSchema,
  cameraFolderPathSchema,
  cameraNameSchema,
  cameraStatusSchema,
  cameraUpdateSchema,
  CAMERA_FOLDER_PATH_CONSTRAINTS,
  CAMERA_NAME_CONSTRAINTS,
  CAMERA_STATUS_VALUES,
} from './camera';

describe('Camera Zod Schemas', () => {
  describe('cameraStatusSchema', () => {
    it('should accept all valid status values', () => {
      for (const status of CAMERA_STATUS_VALUES) {
        const result = cameraStatusSchema.safeParse(status);
        expect(result.success).toBe(true);
        if (result.success) {
          expect(result.data).toBe(status);
        }
      }
    });

    it('should reject invalid status values', () => {
      const result = cameraStatusSchema.safeParse('invalid');
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.issues[0].message).toBe(
          'Invalid camera status. Must be: online, offline, error, or unknown'
        );
      }
    });

    it('should include "unknown" status (NEM-2296 fix)', () => {
      expect(CAMERA_STATUS_VALUES).toContain('unknown');
      const result = cameraStatusSchema.safeParse('unknown');
      expect(result.success).toBe(true);
    });
  });

  describe('cameraNameSchema', () => {
    it('should accept valid names', () => {
      const result = cameraNameSchema.safeParse('Front Door');
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data).toBe('Front Door');
      }
    });

    it('should trim whitespace', () => {
      const result = cameraNameSchema.safeParse('  Front Door  ');
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data).toBe('Front Door');
      }
    });

    it('should accept single character names (min_length=1)', () => {
      const result = cameraNameSchema.safeParse('A');
      expect(result.success).toBe(true);
    });

    it('should reject empty names', () => {
      const result = cameraNameSchema.safeParse('');
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.issues[0].message).toBe('Name is required');
      }
    });

    it('should reject names exceeding max length', () => {
      const longName = 'a'.repeat(CAMERA_NAME_CONSTRAINTS.maxLength + 1);
      const result = cameraNameSchema.safeParse(longName);
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.issues[0].message).toBe(
          `Name must be at most ${CAMERA_NAME_CONSTRAINTS.maxLength} characters`
        );
      }
    });
  });

  describe('cameraFolderPathSchema', () => {
    it('should accept valid folder paths', () => {
      const result = cameraFolderPathSchema.safeParse('/export/foscam/front_door');
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data).toBe('/export/foscam/front_door');
      }
    });

    it('should trim whitespace', () => {
      const result = cameraFolderPathSchema.safeParse('  /export/foscam/test  ');
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data).toBe('/export/foscam/test');
      }
    });

    it('should reject empty paths', () => {
      const result = cameraFolderPathSchema.safeParse('');
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.issues[0].message).toBe('Folder path is required');
      }
    });

    it('should reject path traversal attempts', () => {
      const result = cameraFolderPathSchema.safeParse('/export/../etc/passwd');
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.issues[0].message).toBe(
          'Path traversal (..) is not allowed in folder path'
        );
      }
    });

    it('should reject forbidden characters (<>:"|?*)', () => {
      const forbiddenChars = ['<', '>', ':', '"', '|', '?', '*'];
      for (const char of forbiddenChars) {
        const result = cameraFolderPathSchema.safeParse(`/export/test${char}folder`);
        expect(result.success).toBe(false);
        if (!result.success) {
          expect(result.error.issues[0].message).toBe(
            'Folder path contains forbidden characters (< > : " | ? * or control characters)'
          );
        }
      }
    });

    it('should reject control characters', () => {
      const result = cameraFolderPathSchema.safeParse('/export/test\x00folder');
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.issues[0].message).toBe(
          'Folder path contains forbidden characters (< > : " | ? * or control characters)'
        );
      }
    });

    it('should reject paths exceeding max length', () => {
      const longPath = '/export/' + 'a'.repeat(CAMERA_FOLDER_PATH_CONSTRAINTS.maxLength);
      const result = cameraFolderPathSchema.safeParse(longPath);
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.issues[0].message).toBe(
          `Folder path must be at most ${CAMERA_FOLDER_PATH_CONSTRAINTS.maxLength} characters`
        );
      }
    });
  });

  describe('cameraCreateSchema', () => {
    it('should validate a complete camera create payload', () => {
      const result = cameraCreateSchema.safeParse({
        name: 'Front Door',
        folder_path: '/export/foscam/front_door',
        status: 'online',
      });
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.name).toBe('Front Door');
        expect(result.data.folder_path).toBe('/export/foscam/front_door');
        expect(result.data.status).toBe('online');
      }
    });

    it('should default status to "online"', () => {
      const result = cameraCreateSchema.safeParse({
        name: 'Front Door',
        folder_path: '/export/foscam/front_door',
      });
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.status).toBe('online');
      }
    });
  });

  describe('cameraUpdateSchema', () => {
    it('should allow partial updates', () => {
      const result = cameraUpdateSchema.safeParse({ name: 'Updated Name' });
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.name).toBe('Updated Name');
        expect(result.data.folder_path).toBeUndefined();
        expect(result.data.status).toBeUndefined();
      }
    });

    it('should allow empty updates', () => {
      const result = cameraUpdateSchema.safeParse({});
      expect(result.success).toBe(true);
    });
  });

  describe('cameraFormSchema', () => {
    it('should require all fields', () => {
      const result = cameraFormSchema.safeParse({
        name: 'Front Door',
        folder_path: '/export/foscam/front_door',
        status: 'online',
      });
      expect(result.success).toBe(true);
    });

    it('should fail if name is missing', () => {
      const result = cameraFormSchema.safeParse({
        folder_path: '/export/foscam/front_door',
        status: 'online',
      });
      expect(result.success).toBe(false);
    });

    it('should fail if folder_path is missing', () => {
      const result = cameraFormSchema.safeParse({
        name: 'Front Door',
        status: 'online',
      });
      expect(result.success).toBe(false);
    });
  });

  describe('Constants alignment with backend', () => {
    it('should have correct name constraints (backend min_length=1, max_length=255)', () => {
      expect(CAMERA_NAME_CONSTRAINTS.minLength).toBe(1);
      expect(CAMERA_NAME_CONSTRAINTS.maxLength).toBe(255);
    });

    it('should have correct folder path constraints (backend min_length=1, max_length=500)', () => {
      expect(CAMERA_FOLDER_PATH_CONSTRAINTS.minLength).toBe(1);
      expect(CAMERA_FOLDER_PATH_CONSTRAINTS.maxLength).toBe(500);
    });

    it('should have all 4 status values matching backend CameraStatus enum', () => {
      expect(CAMERA_STATUS_VALUES).toEqual(['online', 'offline', 'error', 'unknown']);
    });
  });
});
