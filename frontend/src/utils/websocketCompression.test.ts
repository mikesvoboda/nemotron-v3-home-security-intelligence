/**
 * Tests for WebSocket message compression utilities (NEM-3154)
 */

import pako from 'pako';
import { describe, it, expect } from 'vitest';

import {
  COMPRESSION_MAGIC_BYTE,
  isCompressedMessage,
  decompressMessage,
  parseWebSocketMessage,
} from './websocketCompression';

describe('WebSocket Compression Utilities', () => {
  describe('COMPRESSION_MAGIC_BYTE', () => {
    it('should be 0x00', () => {
      expect(COMPRESSION_MAGIC_BYTE).toBe(0x00);
    });
  });

  describe('isCompressedMessage', () => {
    it('should return true for ArrayBuffer with magic byte prefix', () => {
      const data = new Uint8Array([0x00, 1, 2, 3]).buffer;
      expect(isCompressedMessage(data)).toBe(true);
    });

    it('should return false for ArrayBuffer without magic byte prefix', () => {
      const data = new Uint8Array([0x7b, 0x22, 0x74]).buffer; // {"t in UTF-8
      expect(isCompressedMessage(data)).toBe(false);
    });

    it('should return false for empty ArrayBuffer', () => {
      const data = new ArrayBuffer(0);
      expect(isCompressedMessage(data)).toBe(false);
    });

    it('should return false for string data', () => {
      expect(isCompressedMessage('{"type": "event"}')).toBe(false);
    });

    it('should return true for Blob (assumes might be compressed)', () => {
      const blob = new Blob([new Uint8Array([0x00, 1, 2, 3])]);
      expect(isCompressedMessage(blob)).toBe(true);
    });
  });

  describe('decompressMessage', () => {
    it('should decompress ArrayBuffer with magic byte prefix', async () => {
      const original = '{"type": "event"}';
      const compressed = pako.deflate(new TextEncoder().encode(original));
      const withMagic = new Uint8Array([COMPRESSION_MAGIC_BYTE, ...compressed]);

      const result = await decompressMessage(withMagic.buffer);
      expect(result).toBe(original);
    });

    it('should return uncompressed ArrayBuffer as UTF-8 string', async () => {
      const original = '{"type": "event"}';
      const data = new TextEncoder().encode(original).buffer;

      const result = await decompressMessage(data);
      expect(result).toBe(original);
    });

    // Note: Blob.arrayBuffer() is not available in jsdom, so we test ArrayBuffer directly
    // In browser environments, Blob handling works correctly
    it('should handle ArrayBuffer from decompressed Blob (simulated)', async () => {
      const original = '{"type": "event"}';
      const compressed = pako.deflate(new TextEncoder().encode(original));
      const withMagic = new Uint8Array([COMPRESSION_MAGIC_BYTE, ...compressed]);

      // Simulate what happens after Blob.arrayBuffer() is called
      const result = await decompressMessage(withMagic.buffer);
      expect(result).toBe(original);
    });

    it('should return empty string for empty input', async () => {
      const data = new ArrayBuffer(0);
      const result = await decompressMessage(data);
      expect(result).toBe('');
    });

    it('should throw error for invalid compressed data', async () => {
      const invalid = new Uint8Array([0x00, 0xff, 0xff, 0xff]).buffer;
      await expect(decompressMessage(invalid)).rejects.toThrow(
        'Failed to decompress WebSocket message'
      );
    });
  });

  describe('parseWebSocketMessage', () => {
    it('should parse text JSON message', async () => {
      const data = '{"type": "event", "data": {"id": 1}}';
      const event = { data } as MessageEvent;

      const result = await parseWebSocketMessage(event);
      expect(result).toEqual({ type: 'event', data: { id: 1 } });
    });

    it('should parse compressed binary message', async () => {
      const original = { type: 'event', data: { id: 123 } };
      const json = JSON.stringify(original);
      const compressed = pako.deflate(new TextEncoder().encode(json));
      const withMagic = new Uint8Array([COMPRESSION_MAGIC_BYTE, ...compressed]);

      const event = { data: withMagic.buffer } as MessageEvent;

      const result = await parseWebSocketMessage(event);
      expect(result).toEqual(original);
    });

    it('should parse uncompressed binary message (as UTF-8 JSON)', async () => {
      const original = { type: 'event', data: { id: 456 } };
      const json = JSON.stringify(original);
      const encoded = new TextEncoder().encode(json);
      // Create a new ArrayBuffer and copy the data to ensure proper backing
      const data = new ArrayBuffer(encoded.byteLength);
      new Uint8Array(data).set(encoded);

      const event = { data } as MessageEvent;

      const result = await parseWebSocketMessage(event);
      expect(result).toEqual(original);
    });

    it('should handle unicode in compressed messages', async () => {
      const original = { type: 'event', message: 'Hello, world!' };
      const json = JSON.stringify(original);
      const compressed = pako.deflate(new TextEncoder().encode(json));
      const withMagic = new Uint8Array([COMPRESSION_MAGIC_BYTE, ...compressed]);

      const event = { data: withMagic.buffer } as MessageEvent;

      const result = await parseWebSocketMessage(event);
      expect(result).toEqual(original);
    });

    it('should return unknown data types as-is', async () => {
      const event = { data: 12345 } as MessageEvent;

      const result = await parseWebSocketMessage(event);
      expect(result).toBe(12345);
    });
  });

  describe('Round-trip compression', () => {
    it('should round-trip a complex message', async () => {
      const original = {
        type: 'detection.batch',
        data: {
          batch_id: 'batch_abc123',
          camera_id: 'front_door',
          detection_ids: [1, 2, 3, 4, 5],
          detection_count: 5,
          started_at: '2026-01-20T12:00:00Z',
          closed_at: '2026-01-20T12:02:00Z',
          close_reason: 'timeout',
        },
      };

      // Simulate backend compression
      const json = JSON.stringify(original);
      const compressed = pako.deflate(new TextEncoder().encode(json));
      const withMagic = new Uint8Array([COMPRESSION_MAGIC_BYTE, ...compressed]);

      // Simulate frontend decompression
      const result = await decompressMessage(withMagic.buffer);
      expect(JSON.parse(result)).toEqual(original);
    });

    it('should achieve compression for large messages', () => {
      // Create a message with repetitive data (like base64 image placeholder)
      const largeData = {
        type: 'detection.new',
        data: {
          image_base64: 'A'.repeat(10000), // Simulated base64 data
          metadata: { key: 'value' },
        },
      };

      const json = JSON.stringify(largeData);
      const originalSize = new TextEncoder().encode(json).byteLength;
      const compressed = pako.deflate(new TextEncoder().encode(json));

      // Compression should reduce size significantly for repetitive data
      expect(compressed.byteLength).toBeLessThan(originalSize * 0.5);
    });
  });
});
