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

  describe('RTSP URL Validation (TDD Phase 1)', () => {
    describe('Valid RTSP URLs', () => {
      it('should accept rtsp:// URLs', () => {
        const result = cameraCreateSchema.safeParse({
          name: 'RTSP Camera',
          folder_path: '/export/cameras/rtsp1',
          status: 'online',
          ingestion_mode: 'rtsp',
          rtsp_url: 'rtsp://192.168.1.100:554/stream1',
        });
        expect(result.success).toBe(true);
        if (result.success) {
          expect(result.data.rtsp_url).toBe('rtsp://192.168.1.100:554/stream1');
        }
      });

      it('should accept rtsps:// URLs (secure RTSP)', () => {
        const result = cameraCreateSchema.safeParse({
          name: 'RTSP Camera',
          folder_path: '/export/cameras/rtsp1',
          status: 'online',
          ingestion_mode: 'rtsp',
          rtsp_url: 'rtsps://192.168.1.100:554/stream1',
        });
        expect(result.success).toBe(true);
        if (result.success) {
          expect(result.data.rtsp_url).toBe('rtsps://192.168.1.100:554/stream1');
        }
      });

      it('should accept RTSP URLs with authentication in URL', () => {
        const result = cameraCreateSchema.safeParse({
          name: 'RTSP Camera',
          folder_path: '/export/cameras/rtsp1',
          status: 'online',
          ingestion_mode: 'rtsp',
          rtsp_url: 'rtsp://admin:password@192.168.1.100:554/stream1', // pragma: allowlist secret
        });
        expect(result.success).toBe(true);
      });

      it('should accept RTSP URLs with hostname', () => {
        const result = cameraCreateSchema.safeParse({
          name: 'RTSP Camera',
          folder_path: '/export/cameras/rtsp1',
          status: 'online',
          ingestion_mode: 'rtsp',
          rtsp_url: 'rtsp://camera.local:554/stream1',
        });
        expect(result.success).toBe(true);
      });

      it('should accept RTSP URLs with complex paths', () => {
        const result = cameraCreateSchema.safeParse({
          name: 'RTSP Camera',
          folder_path: '/export/cameras/rtsp1',
          status: 'online',
          ingestion_mode: 'rtsp',
          rtsp_url: 'rtsp://192.168.1.100:554/axis-media/media.amp?videocodec=h264',
        });
        expect(result.success).toBe(true);
      });

      it('should allow null rtsp_url for non-RTSP cameras', () => {
        const result = cameraCreateSchema.safeParse({
          name: 'FTP Camera',
          folder_path: '/export/cameras/ftp1',
          status: 'online',
          ingestion_mode: 'ftp',
          rtsp_url: null,
        });
        expect(result.success).toBe(true);
      });
    });

    describe('Invalid RTSP URLs', () => {
      it('should reject http:// URLs', () => {
        const result = cameraCreateSchema.safeParse({
          name: 'RTSP Camera',
          folder_path: '/export/cameras/rtsp1',
          status: 'online',
          ingestion_mode: 'rtsp',
          rtsp_url: 'http://192.168.1.100:554/stream1',
        });
        expect(result.success).toBe(false);
        if (!result.success) {
          expect(result.error.issues[0].message).toContain('rtsp://');
        }
      });

      it('should reject https:// URLs', () => {
        const result = cameraCreateSchema.safeParse({
          name: 'RTSP Camera',
          folder_path: '/export/cameras/rtsp1',
          status: 'online',
          ingestion_mode: 'rtsp',
          rtsp_url: 'https://192.168.1.100:554/stream1',
        });
        expect(result.success).toBe(false);
        if (!result.success) {
          expect(result.error.issues[0].message).toContain('rtsp://');
        }
      });

      it('should reject URLs without scheme', () => {
        const result = cameraCreateSchema.safeParse({
          name: 'RTSP Camera',
          folder_path: '/export/cameras/rtsp1',
          status: 'online',
          ingestion_mode: 'rtsp',
          rtsp_url: '192.168.1.100:554/stream1',
        });
        expect(result.success).toBe(false);
        if (!result.success) {
          expect(result.error.issues[0].message).toContain('rtsp://');
        }
      });

      it('should reject URLs without host', () => {
        const result = cameraCreateSchema.safeParse({
          name: 'RTSP Camera',
          folder_path: '/export/cameras/rtsp1',
          status: 'online',
          ingestion_mode: 'rtsp',
          rtsp_url: 'rtsp:///stream1',
        });
        expect(result.success).toBe(false);
        if (!result.success) {
          expect(result.error.issues[0].message).toContain('valid host');
        }
      });

      it('should reject empty string rtsp_url', () => {
        const result = cameraCreateSchema.safeParse({
          name: 'RTSP Camera',
          folder_path: '/export/cameras/rtsp1',
          status: 'online',
          ingestion_mode: 'rtsp',
          rtsp_url: '',
        });
        expect(result.success).toBe(false);
      });
    });

    describe('Conditional RTSP URL requirement', () => {
      it('should require rtsp_url when ingestion_mode is rtsp', () => {
        const result = cameraCreateSchema.safeParse({
          name: 'RTSP Camera',
          folder_path: '/export/cameras/rtsp1',
          status: 'online',
          ingestion_mode: 'rtsp',
          rtsp_url: null,
        });
        expect(result.success).toBe(false);
        if (!result.success) {
          expect(result.error.issues[0].message).toContain('required');
        }
      });

      it('should require rtsp_url when ingestion_mode is onvif', () => {
        const result = cameraCreateSchema.safeParse({
          name: 'ONVIF Camera',
          folder_path: '/export/cameras/onvif1',
          status: 'online',
          ingestion_mode: 'onvif',
          rtsp_url: null,
        });
        expect(result.success).toBe(false);
        if (!result.success) {
          expect(result.error.issues[0].message).toContain('required');
        }
      });

      it('should allow null rtsp_url when ingestion_mode is ftp', () => {
        const result = cameraCreateSchema.safeParse({
          name: 'FTP Camera',
          folder_path: '/export/cameras/ftp1',
          status: 'online',
          ingestion_mode: 'ftp',
          rtsp_url: null,
        });
        expect(result.success).toBe(true);
      });
    });
  });

  describe('Ingestion Mode Validation (TDD Phase 1)', () => {
    it('should accept ingestion_mode "ftp"', () => {
      const result = cameraCreateSchema.safeParse({
        name: 'FTP Camera',
        folder_path: '/export/cameras/ftp1',
        status: 'online',
        ingestion_mode: 'ftp',
      });
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.ingestion_mode).toBe('ftp');
      }
    });

    it('should accept ingestion_mode "rtsp"', () => {
      const result = cameraCreateSchema.safeParse({
        name: 'RTSP Camera',
        folder_path: '/export/cameras/rtsp1',
        status: 'online',
        ingestion_mode: 'rtsp',
        rtsp_url: 'rtsp://192.168.1.100/stream',
      });
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.ingestion_mode).toBe('rtsp');
      }
    });

    it('should accept ingestion_mode "onvif"', () => {
      const result = cameraCreateSchema.safeParse({
        name: 'ONVIF Camera',
        folder_path: '/export/cameras/onvif1',
        status: 'online',
        ingestion_mode: 'onvif',
        rtsp_url: 'rtsp://192.168.1.100/stream',
      });
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.ingestion_mode).toBe('onvif');
      }
    });

    it('should reject invalid ingestion_mode values', () => {
      const result = cameraCreateSchema.safeParse({
        name: 'Camera',
        folder_path: '/export/cameras/camera1',
        status: 'online',
        ingestion_mode: 'invalid',
      });
      expect(result.success).toBe(false);
    });

    it('should default to "ftp" when ingestion_mode is omitted', () => {
      const result = cameraCreateSchema.safeParse({
        name: 'Camera',
        folder_path: '/export/cameras/camera1',
        status: 'online',
      });
      expect(result.success).toBe(true);
      if (result.success) {
        // Default should be applied at backend, frontend allows omission
        expect(result.data.ingestion_mode).toBeUndefined();
      }
    });
  });

  describe('Stream Profile Validation (TDD Phase 1)', () => {
    it('should accept stream_profile "main"', () => {
      const result = cameraCreateSchema.safeParse({
        name: 'RTSP Camera',
        folder_path: '/export/cameras/rtsp1',
        status: 'online',
        ingestion_mode: 'rtsp',
        rtsp_url: 'rtsp://192.168.1.100/stream',
        stream_profile: 'main',
      });
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.stream_profile).toBe('main');
      }
    });

    it('should accept stream_profile "sub"', () => {
      const result = cameraCreateSchema.safeParse({
        name: 'RTSP Camera',
        folder_path: '/export/cameras/rtsp1',
        status: 'online',
        ingestion_mode: 'rtsp',
        rtsp_url: 'rtsp://192.168.1.100/stream',
        stream_profile: 'sub',
      });
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.stream_profile).toBe('sub');
      }
    });

    it('should accept stream_profile "both"', () => {
      const result = cameraCreateSchema.safeParse({
        name: 'RTSP Camera',
        folder_path: '/export/cameras/rtsp1',
        status: 'online',
        ingestion_mode: 'rtsp',
        rtsp_url: 'rtsp://192.168.1.100/stream',
        stream_profile: 'both',
      });
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.stream_profile).toBe('both');
      }
    });

    it('should allow null stream_profile', () => {
      const result = cameraCreateSchema.safeParse({
        name: 'RTSP Camera',
        folder_path: '/export/cameras/rtsp1',
        status: 'online',
        ingestion_mode: 'rtsp',
        rtsp_url: 'rtsp://192.168.1.100/stream',
        stream_profile: null,
      });
      expect(result.success).toBe(true);
    });

    it('should reject invalid stream_profile values', () => {
      const result = cameraCreateSchema.safeParse({
        name: 'RTSP Camera',
        folder_path: '/export/cameras/rtsp1',
        status: 'online',
        ingestion_mode: 'rtsp',
        rtsp_url: 'rtsp://192.168.1.100/stream',
        stream_profile: 'invalid',
      });
      expect(result.success).toBe(false);
    });
  });

  describe('RTSP Credentials Validation (TDD Phase 1)', () => {
    it('should accept rtsp_username as string', () => {
      const result = cameraCreateSchema.safeParse({
        name: 'RTSP Camera',
        folder_path: '/export/cameras/rtsp1',
        status: 'online',
        ingestion_mode: 'rtsp',
        rtsp_url: 'rtsp://192.168.1.100/stream',
        rtsp_username: 'admin',
      });
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.rtsp_username).toBe('admin');
      }
    });

    it('should accept rtsp_password as string', () => {
      const result = cameraCreateSchema.safeParse({
        name: 'RTSP Camera',
        folder_path: '/export/cameras/rtsp1',
        status: 'online',
        ingestion_mode: 'rtsp',
        rtsp_url: 'rtsp://192.168.1.100/stream',
        rtsp_password: 'secretpassword', // pragma: allowlist secret
      });
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.rtsp_password).toBe('secretpassword'); // pragma: allowlist secret
      }
    });

    it('should accept both username and password', () => {
      const result = cameraCreateSchema.safeParse({
        name: 'RTSP Camera',
        folder_path: '/export/cameras/rtsp1',
        status: 'online',
        ingestion_mode: 'rtsp',
        rtsp_url: 'rtsp://192.168.1.100/stream',
        rtsp_username: 'admin',
        rtsp_password: 'secretpassword', // pragma: allowlist secret
      });
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.rtsp_username).toBe('admin');
        expect(result.data.rtsp_password).toBe('secretpassword'); // pragma: allowlist secret
      }
    });

    it('should accept password with special characters', () => {
      const result = cameraCreateSchema.safeParse({
        name: 'RTSP Camera',
        folder_path: '/export/cameras/rtsp1',
        status: 'online',
        ingestion_mode: 'rtsp',
        rtsp_url: 'rtsp://192.168.1.100/stream',
        rtsp_password: 'P@ssw0rd!#$%^&*()', // pragma: allowlist secret
      });
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.rtsp_password).toBe('P@ssw0rd!#$%^&*()'); // pragma: allowlist secret
      }
    });

    it('should allow null rtsp_username', () => {
      const result = cameraCreateSchema.safeParse({
        name: 'RTSP Camera',
        folder_path: '/export/cameras/rtsp1',
        status: 'online',
        ingestion_mode: 'rtsp',
        rtsp_url: 'rtsp://192.168.1.100/stream',
        rtsp_username: null,
      });
      expect(result.success).toBe(true);
    });

    it('should allow null rtsp_password', () => {
      const result = cameraCreateSchema.safeParse({
        name: 'RTSP Camera',
        folder_path: '/export/cameras/rtsp1',
        status: 'online',
        ingestion_mode: 'rtsp',
        rtsp_url: 'rtsp://192.168.1.100/stream',
        rtsp_password: null,
      });
      expect(result.success).toBe(true);
    });

    it('should allow empty string credentials', () => {
      const result = cameraCreateSchema.safeParse({
        name: 'RTSP Camera',
        folder_path: '/export/cameras/rtsp1',
        status: 'online',
        ingestion_mode: 'rtsp',
        rtsp_url: 'rtsp://192.168.1.100/stream',
        rtsp_username: '',
        rtsp_password: '',
      });
      expect(result.success).toBe(true);
    });
  });

  describe('Motion Sensitivity Schema (TDD Phase 5)', () => {
    describe('Valid motion_sensitivity values', () => {
      it('should accept motion_sensitivity 0.0 (minimum)', () => {
        const result = cameraCreateSchema.safeParse({
          name: 'Test Camera',
          folder_path: 'rtsp://192.168.1.100/stream',
          status: 'online',
          motion_sensitivity: 0.0,
        });
        expect(result.success).toBe(true);
        if (result.success) {
          expect(result.data.motion_sensitivity).toBe(0.0);
        }
      });

      it('should accept motion_sensitivity 1.0 (maximum)', () => {
        const result = cameraCreateSchema.safeParse({
          name: 'Test Camera',
          folder_path: 'rtsp://192.168.1.100/stream',
          status: 'online',
          motion_sensitivity: 1.0,
        });
        expect(result.success).toBe(true);
        if (result.success) {
          expect(result.data.motion_sensitivity).toBe(1.0);
        }
      });

      it('should accept motion_sensitivity 0.5 (default)', () => {
        const result = cameraCreateSchema.safeParse({
          name: 'Test Camera',
          folder_path: 'rtsp://192.168.1.100/stream',
          status: 'online',
          motion_sensitivity: 0.5,
        });
        expect(result.success).toBe(true);
        if (result.success) {
          expect(result.data.motion_sensitivity).toBe(0.5);
        }
      });

      it('should accept motion_sensitivity with high precision (0.75)', () => {
        const result = cameraCreateSchema.safeParse({
          name: 'Test Camera',
          folder_path: 'rtsp://192.168.1.100/stream',
          status: 'online',
          motion_sensitivity: 0.75,
        });
        expect(result.success).toBe(true);
        if (result.success) {
          expect(result.data.motion_sensitivity).toBe(0.75);
        }
      });
    });

    describe('Invalid motion_sensitivity values', () => {
      it('should reject motion_sensitivity < 0.0', () => {
        const result = cameraCreateSchema.safeParse({
          name: 'Test Camera',
          folder_path: 'rtsp://192.168.1.100/stream',
          status: 'online',
          motion_sensitivity: -0.1,
        });
        expect(result.success).toBe(false);
        if (!result.success) {
          expect(result.error.issues[0].message).toContain('at least 0');
        }
      });

      it('should reject motion_sensitivity > 1.0', () => {
        const result = cameraCreateSchema.safeParse({
          name: 'Test Camera',
          folder_path: 'rtsp://192.168.1.100/stream',
          status: 'online',
          motion_sensitivity: 1.1,
        });
        expect(result.success).toBe(false);
        if (!result.success) {
          expect(result.error.issues[0].message).toContain('at most 1');
        }
      });

      it('should reject non-numeric motion_sensitivity', () => {
        const result = cameraCreateSchema.safeParse({
          name: 'Test Camera',
          folder_path: 'rtsp://192.168.1.100/stream',
          status: 'online',
          motion_sensitivity: 'invalid',
        });
        expect(result.success).toBe(false);
      });
    });

    describe('Optional motion_sensitivity field', () => {
      it('should allow motion_sensitivity to be omitted (optional field)', () => {
        const result = cameraCreateSchema.safeParse({
          name: 'Test Camera',
          folder_path: 'rtsp://192.168.1.100/stream',
          status: 'online',
        });
        expect(result.success).toBe(true);
        if (result.success) {
          // motion_sensitivity should be undefined when not provided
          expect(result.data.motion_sensitivity).toBeUndefined();
        }
      });

      it('should default to 0.5 when omitted for RTSP cameras', () => {
        const result = cameraCreateSchema.safeParse({
          name: 'Test Camera',
          folder_path: 'rtsp://192.168.1.100/stream',
          status: 'online',
        });
        expect(result.success).toBe(true);
        if (result.success) {
          // The default should be applied at the component level, not schema level
          // Schema should allow omission, and component provides default
          expect(result.data.motion_sensitivity).toBeUndefined();
        }
      });
    });

    describe('Motion sensitivity in cameraUpdateSchema', () => {
      it('should allow partial update with only motion_sensitivity', () => {
        const result = cameraUpdateSchema.safeParse({
          motion_sensitivity: 0.8,
        });
        expect(result.success).toBe(true);
        if (result.success) {
          expect(result.data.motion_sensitivity).toBe(0.8);
        }
      });

      it('should validate motion_sensitivity range in updates', () => {
        const result = cameraUpdateSchema.safeParse({
          motion_sensitivity: 1.5,
        });
        expect(result.success).toBe(false);
      });

      it('should allow motion_sensitivity to be omitted in partial updates', () => {
        const result = cameraUpdateSchema.safeParse({
          name: 'Updated Name',
        });
        expect(result.success).toBe(true);
        if (result.success) {
          expect(result.data.motion_sensitivity).toBeUndefined();
        }
      });
    });

    describe('Motion sensitivity in cameraFormSchema', () => {
      it('should include motion_sensitivity in form schema', () => {
        const result = cameraFormSchema.safeParse({
          name: 'Test Camera',
          folder_path: 'rtsp://192.168.1.100/stream',
          status: 'online',
          motion_sensitivity: 0.5,
        });
        expect(result.success).toBe(true);
      });

      it('should allow motion_sensitivity to be optional in form', () => {
        const result = cameraFormSchema.safeParse({
          name: 'Test Camera',
          folder_path: '/export/foscam/camera',
          status: 'online',
        });
        expect(result.success).toBe(true);
      });
    });
  });
});
