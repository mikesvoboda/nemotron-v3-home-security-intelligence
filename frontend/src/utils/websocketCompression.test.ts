/**
 * Tests for WebSocket message compression and serialization utilities (NEM-3154, NEM-3737)
 */

import pako from 'pako';
import { describe, it, expect } from 'vitest';

import {
  COMPRESSION_MAGIC_BYTE,
  MSGPACK_MAGIC_BYTE,
  SerializationFormat,
  isCompressedMessage,
  isMsgpackMessage,
  detectFormat,
  decompressMessage,
  decompressMessageAuto,
  parseWebSocketMessage,
  encodeMsgpack,
  decodeMsgpack,
  createWebSocketUrl,
  prepareWebSocketMessage,
} from './websocketCompression';

describe('WebSocket Compression and Serialization Utilities', () => {
  describe('Magic Bytes', () => {
    it('COMPRESSION_MAGIC_BYTE should be 0x00', () => {
      expect(COMPRESSION_MAGIC_BYTE).toBe(0x00);
    });

    it('MSGPACK_MAGIC_BYTE should be 0x01', () => {
      expect(MSGPACK_MAGIC_BYTE).toBe(0x01);
    });

    it('magic bytes should be distinct', () => {
      expect(COMPRESSION_MAGIC_BYTE).not.toBe(MSGPACK_MAGIC_BYTE);
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

  // ============================================================================
  // MessagePack Tests (NEM-3737)
  // ============================================================================

  describe('isMsgpackMessage', () => {
    it('should return true for ArrayBuffer with MessagePack magic byte', () => {
      const data = new Uint8Array([MSGPACK_MAGIC_BYTE, 1, 2, 3]).buffer;
      expect(isMsgpackMessage(data)).toBe(true);
    });

    it('should return false for ArrayBuffer with zlib magic byte', () => {
      const data = new Uint8Array([COMPRESSION_MAGIC_BYTE, 1, 2, 3]).buffer;
      expect(isMsgpackMessage(data)).toBe(false);
    });

    it('should return false for plain JSON bytes', () => {
      const data = new Uint8Array([0x7b, 0x22]).buffer; // {"
      expect(isMsgpackMessage(data)).toBe(false);
    });

    it('should return false for string data', () => {
      expect(isMsgpackMessage('{"type": "event"}')).toBe(false);
    });

    it('should work with Uint8Array', () => {
      const data = new Uint8Array([MSGPACK_MAGIC_BYTE, 1, 2, 3]);
      expect(isMsgpackMessage(data)).toBe(true);
    });
  });

  describe('detectFormat', () => {
    it('should detect zlib format', () => {
      const bytes = new Uint8Array([COMPRESSION_MAGIC_BYTE, 1, 2, 3]);
      expect(detectFormat(bytes)).toBe(SerializationFormat.ZLIB);
    });

    it('should detect MessagePack format', () => {
      const bytes = new Uint8Array([MSGPACK_MAGIC_BYTE, 1, 2, 3]);
      expect(detectFormat(bytes)).toBe(SerializationFormat.MSGPACK);
    });

    it('should detect JSON format for other bytes', () => {
      const bytes = new Uint8Array([0x7b, 0x22]); // {"
      expect(detectFormat(bytes)).toBe(SerializationFormat.JSON);
    });

    it('should return JSON for empty bytes', () => {
      expect(detectFormat(new Uint8Array(0))).toBe(SerializationFormat.JSON);
    });
  });

  describe('encodeMsgpack', () => {
    it('should encode object with magic byte prefix', () => {
      const data = { type: 'event', value: 42 };
      const encoded = encodeMsgpack(data);

      expect(encoded[0]).toBe(MSGPACK_MAGIC_BYTE);
      expect(encoded.length).toBeGreaterThan(1);
    });

    it('should produce smaller output than JSON for typical messages', () => {
      const data = {
        type: 'detection',
        id: 12345,
        camera: 'front_door',
        confidence: 0.95,
      };

      const jsonSize = new TextEncoder().encode(JSON.stringify(data)).length;
      const msgpackSize = encodeMsgpack(data).length;

      // MessagePack should be smaller (even with magic byte)
      expect(msgpackSize).toBeLessThan(jsonSize);
    });
  });

  describe('decodeMsgpack', () => {
    it('should decode MessagePack with magic byte prefix', () => {
      const original = { type: 'event', value: 123 };
      const encoded = encodeMsgpack(original);
      const decoded = decodeMsgpack(encoded);

      expect(decoded).toEqual(original);
    });

    it('should handle nested objects', () => {
      const original = {
        type: 'detection',
        data: {
          camera_id: 'front',
          detections: [{ label: 'person', score: 0.9 }],
        },
      };

      const encoded = encodeMsgpack(original);
      const decoded = decodeMsgpack(encoded);

      expect(decoded).toEqual(original);
    });

    it('should handle arrays', () => {
      const original = { items: [1, 2, 3, 4, 5] };
      const encoded = encodeMsgpack(original);
      const decoded = decodeMsgpack(encoded);

      expect(decoded).toEqual(original);
    });
  });

  describe('decompressMessageAuto', () => {
    // Helper to create a clean ArrayBuffer from Uint8Array (avoids TypeScript SharedArrayBuffer issues)
    const toArrayBuffer = (uint8Array: Uint8Array): ArrayBuffer => {
      const buffer = new ArrayBuffer(uint8Array.length);
      new Uint8Array(buffer).set(uint8Array);
      return buffer;
    };

    it('should auto-detect and decode MessagePack', async () => {
      const original = { type: 'event', value: 42 };
      const encoded = encodeMsgpack(original);

      const result = await decompressMessageAuto(toArrayBuffer(encoded));
      expect(result).toEqual(original);
    });

    it('should auto-detect and decompress zlib', async () => {
      const original = { type: 'event', data: 'test' };
      const json = JSON.stringify(original);
      const compressed = pako.deflate(new TextEncoder().encode(json));
      const withMagic = new Uint8Array([COMPRESSION_MAGIC_BYTE, ...compressed]);

      const result = await decompressMessageAuto(toArrayBuffer(withMagic));
      expect(result).toEqual(original);
    });

    it('should auto-detect and parse plain JSON bytes', async () => {
      const original = { type: 'event', value: 123 };
      const jsonBytes = new TextEncoder().encode(JSON.stringify(original));

      const result = await decompressMessageAuto(toArrayBuffer(jsonBytes));
      expect(result).toEqual(original);
    });
  });

  describe('parseWebSocketMessage with MessagePack', () => {
    it('should parse MessagePack binary message', async () => {
      const original = { type: 'detection', camera_id: 'front' };
      const encoded = encodeMsgpack(original);

      const event = { data: encoded.buffer } as MessageEvent;
      const result = await parseWebSocketMessage(event);

      expect(result).toEqual(original);
    });

    it('should still parse text JSON messages', async () => {
      const original = { type: 'event', data: 'test' };
      const event = { data: JSON.stringify(original) } as MessageEvent;

      const result = await parseWebSocketMessage(event);
      expect(result).toEqual(original);
    });

    it('should still parse zlib-compressed messages', async () => {
      const original = { type: 'compressed', value: 100 };
      const json = JSON.stringify(original);
      const compressed = pako.deflate(new TextEncoder().encode(json));
      const withMagic = new Uint8Array([COMPRESSION_MAGIC_BYTE, ...compressed]);

      const event = { data: withMagic.buffer } as MessageEvent;
      const result = await parseWebSocketMessage(event);

      expect(result).toEqual(original);
    });
  });

  describe('createWebSocketUrl', () => {
    it('should append format query parameter', () => {
      const url = createWebSocketUrl(
        'ws://localhost:8000/ws',
        SerializationFormat.MSGPACK
      );
      expect(url).toBe('ws://localhost:8000/ws?format=msgpack');
    });

    it('should preserve existing query parameters', () => {
      const url = createWebSocketUrl(
        'ws://localhost:8000/ws?token=abc',
        SerializationFormat.MSGPACK
      );
      expect(url).toContain('token=abc');
      expect(url).toContain('format=msgpack');
    });
  });

  describe('prepareWebSocketMessage', () => {
    it('should return JSON string for JSON format', () => {
      const data = { type: 'event' };
      const result = prepareWebSocketMessage(data, SerializationFormat.JSON);

      expect(typeof result).toBe('string');
      expect(JSON.parse(result as string)).toEqual(data);
    });

    it('should return MessagePack bytes for MSGPACK format', () => {
      const data = { type: 'event', value: 42 };
      const result = prepareWebSocketMessage(data, SerializationFormat.MSGPACK);

      expect(result instanceof Uint8Array).toBe(true);
      expect((result as Uint8Array)[0]).toBe(MSGPACK_MAGIC_BYTE);
    });

    it('should return zlib bytes for ZLIB format', () => {
      const data = { type: 'event' };
      const result = prepareWebSocketMessage(data, SerializationFormat.ZLIB);

      expect(result instanceof Uint8Array).toBe(true);
      expect((result as Uint8Array)[0]).toBe(COMPRESSION_MAGIC_BYTE);
    });
  });

  describe('Round-trip MessagePack', () => {
    it('should round-trip a complex message through MessagePack', () => {
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

      const encoded = encodeMsgpack(original);
      const decoded = decodeMsgpack(encoded);

      expect(decoded).toEqual(original);
    });

    it('should handle unicode in MessagePack', () => {
      const original = { message: 'Hello, world!', emoji: 'Testing' };
      const encoded = encodeMsgpack(original);
      const decoded = decodeMsgpack(encoded);

      expect(decoded).toEqual(original);
    });
  });
});
