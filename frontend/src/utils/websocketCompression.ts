/**
 * WebSocket Message Compression and Serialization Utilities (NEM-3154, NEM-3737)
 *
 * Handles decompression and deserialization of WebSocket messages from the backend.
 * Supports multiple serialization formats:
 * - zlib-compressed JSON (magic byte 0x00) - NEM-3154
 * - MessagePack binary (magic byte 0x01) - NEM-3737
 * - Plain JSON text (no prefix)
 *
 * Binary messages are decoded based on their magic byte prefix.
 * Text messages are passed through as-is (plain JSON).
 */

import { decode as msgpackDecode, encode as msgpackEncode } from '@msgpack/msgpack';
import pako from 'pako';

// Magic byte prefix for zlib-compressed messages (must match backend)
// 0x00 is used because it's not valid JSON/UTF-8 start
export const COMPRESSION_MAGIC_BYTE = 0x00;

// Magic byte prefix for MessagePack messages (must match backend)
// 0x01 distinguishes MessagePack from zlib compression
export const MSGPACK_MAGIC_BYTE = 0x01;

/**
 * Serialization format enum (matches backend SerializationFormat).
 */
export enum SerializationFormat {
  JSON = 'json',
  ZLIB = 'zlib',
  MSGPACK = 'msgpack',
}

/**
 * Check if a message is zlib-compressed (binary with magic byte 0x00).
 *
 * @param data - The message data from WebSocket
 * @returns True if the message is zlib-compressed
 */
export function isCompressedMessage(data: unknown): data is ArrayBuffer | Blob {
  if (data instanceof ArrayBuffer) {
    const view = new Uint8Array(data);
    return view.length > 0 && view[0] === COMPRESSION_MAGIC_BYTE;
  }
  if (data instanceof Blob) {
    // Blob needs to be read async, so we can't check synchronously
    // We'll handle this case in decompressMessage
    return true; // Assume blob might be compressed/msgpack, check in decompress
  }
  return false;
}

/**
 * Check if a message is MessagePack encoded (binary with magic byte 0x01).
 *
 * @param data - The message data (Uint8Array or ArrayBuffer)
 * @returns True if the message is MessagePack encoded
 */
export function isMsgpackMessage(data: unknown): boolean {
  if (data instanceof ArrayBuffer) {
    const view = new Uint8Array(data);
    return view.length > 0 && view[0] === MSGPACK_MAGIC_BYTE;
  }
  if (data instanceof Uint8Array) {
    return data.length > 0 && data[0] === MSGPACK_MAGIC_BYTE;
  }
  return false;
}

/**
 * Detect the serialization format of a binary message.
 *
 * @param bytes - The message bytes
 * @returns Detected SerializationFormat
 */
export function detectFormat(bytes: Uint8Array): SerializationFormat {
  if (bytes.length === 0) {
    return SerializationFormat.JSON;
  }
  if (bytes[0] === COMPRESSION_MAGIC_BYTE) {
    return SerializationFormat.ZLIB;
  }
  if (bytes[0] === MSGPACK_MAGIC_BYTE) {
    return SerializationFormat.MSGPACK;
  }
  return SerializationFormat.JSON;
}

/**
 * Decode a MessagePack message (removes magic byte prefix if present).
 *
 * @param data - The MessagePack encoded data
 * @returns Decoded object
 */
export function decodeMsgpack(data: Uint8Array | ArrayBuffer): unknown {
  const bytes = data instanceof ArrayBuffer ? new Uint8Array(data) : data;

  // Remove magic byte if present
  const payload = bytes[0] === MSGPACK_MAGIC_BYTE ? bytes.slice(1) : bytes;

  return msgpackDecode(payload);
}

/**
 * Encode an object to MessagePack with magic byte prefix.
 *
 * @param data - The object to encode
 * @returns MessagePack encoded bytes with magic byte prefix
 */
export function encodeMsgpack(data: unknown): Uint8Array {
  const encoded = msgpackEncode(data);
  const withMagic = new Uint8Array(encoded.length + 1);
  withMagic[0] = MSGPACK_MAGIC_BYTE;
  withMagic.set(encoded, 1);
  return withMagic;
}

/**
 * Decompress a WebSocket message.
 *
 * Handles both ArrayBuffer and Blob inputs. If the message doesn't start
 * with a magic byte, it's returned as-is (decoded as UTF-8).
 *
 * Note: This function returns a JSON string for backwards compatibility.
 * For MessagePack messages, use decompressMessageAuto() for direct object output.
 *
 * @param data - The potentially compressed message data
 * @returns Promise resolving to the decompressed JSON string
 */
export async function decompressMessage(data: ArrayBuffer | Blob): Promise<string> {
  let bytes: Uint8Array;

  if (data instanceof Blob) {
    const arrayBuffer = await data.arrayBuffer();
    bytes = new Uint8Array(arrayBuffer);
  } else {
    bytes = new Uint8Array(data);
  }

  // Check for magic byte
  if (bytes.length === 0) {
    return '';
  }

  // Handle MessagePack (0x01)
  if (bytes[0] === MSGPACK_MAGIC_BYTE) {
    try {
      const decoded = decodeMsgpack(bytes);
      // Return as JSON string for backwards compatibility
      return JSON.stringify(decoded);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      throw new Error(`Failed to decode MessagePack message: ${errorMessage}`);
    }
  }

  // Handle zlib compression (0x00)
  if (bytes[0] === COMPRESSION_MAGIC_BYTE) {
    // Remove magic byte and decompress
    const compressedData = bytes.slice(1);

    try {
      const decompressed = pako.inflate(compressedData);
      const decoder = new TextDecoder('utf-8');
      return decoder.decode(decompressed);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      throw new Error(`Failed to decompress WebSocket message: ${errorMessage}`);
    }
  }

  // Not compressed/encoded, decode as UTF-8 JSON
  const decoder = new TextDecoder('utf-8');
  return decoder.decode(bytes);
}

/**
 * Decompress/decode a WebSocket message, auto-detecting format.
 *
 * Returns the decoded object directly (more efficient for MessagePack).
 *
 * @param data - The binary message data
 * @returns Promise resolving to the decoded object
 */
export async function decompressMessageAuto(data: ArrayBuffer | Blob): Promise<unknown> {
  let bytes: Uint8Array;

  if (data instanceof Blob) {
    const arrayBuffer = await data.arrayBuffer();
    bytes = new Uint8Array(arrayBuffer);
  } else {
    bytes = new Uint8Array(data);
  }

  if (bytes.length === 0) {
    return null;
  }

  const format = detectFormat(bytes);

  switch (format) {
    case SerializationFormat.MSGPACK:
      try {
        return decodeMsgpack(bytes);
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        throw new Error(`Failed to decode MessagePack message: ${errorMessage}`);
      }

    case SerializationFormat.ZLIB: {
      const compressedData = bytes.slice(1);
      try {
        const decompressed = pako.inflate(compressedData);
        const decoder = new TextDecoder('utf-8');
        return JSON.parse(decoder.decode(decompressed));
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        throw new Error(`Failed to decompress WebSocket message: ${errorMessage}`);
      }
    }

    default: {
      // Plain JSON
      const decoder = new TextDecoder('utf-8');
      return JSON.parse(decoder.decode(bytes));
    }
  }
}

/**
 * Parse a WebSocket message, handling all serialization formats.
 *
 * This is the main entry point for processing WebSocket messages. It:
 * 1. Checks if the message is binary (potentially MessagePack or zlib-compressed)
 * 2. Auto-detects format and decodes/decompresses as needed
 * 3. Returns the parsed message data
 *
 * Supported formats:
 * - Plain JSON text (string)
 * - zlib-compressed JSON (binary with 0x00 prefix)
 * - MessagePack binary (binary with 0x01 prefix)
 *
 * @param event - The WebSocket MessageEvent
 * @returns Promise resolving to the parsed message data
 */
export async function parseWebSocketMessage(event: MessageEvent): Promise<unknown> {
  const data: unknown = event.data;

  // Handle string messages (plain JSON)
  if (typeof data === 'string') {
    return JSON.parse(data);
  }

  // Handle binary messages (MessagePack, zlib, or plain JSON bytes)
  if (data instanceof ArrayBuffer || data instanceof Blob) {
    return decompressMessageAuto(data);
  }

  // Unknown format, return as-is
  return data;
}

/**
 * Create a WebSocket URL with format negotiation query parameter.
 *
 * @param baseUrl - The base WebSocket URL
 * @param format - The desired serialization format
 * @returns URL with format query parameter appended
 */
export function createWebSocketUrl(baseUrl: string, format: SerializationFormat): string {
  const url = new URL(baseUrl);
  url.searchParams.set('format', format);
  return url.toString();
}

/**
 * Prepare a message for sending via WebSocket with specified format.
 *
 * @param data - The data to send
 * @param format - The serialization format to use
 * @returns Encoded message (Uint8Array for binary, string for JSON)
 */
export function prepareWebSocketMessage(
  data: unknown,
  format: SerializationFormat
): Uint8Array | string {
  switch (format) {
    case SerializationFormat.MSGPACK:
      return encodeMsgpack(data);

    case SerializationFormat.ZLIB: {
      // Compress JSON with zlib
      const json = JSON.stringify(data);
      const jsonBytes = new TextEncoder().encode(json);
      const compressed = pako.deflate(jsonBytes);
      const withMagic = new Uint8Array(compressed.length + 1);
      withMagic[0] = COMPRESSION_MAGIC_BYTE;
      withMagic.set(compressed, 1);
      return withMagic;
    }

    default:
      // Plain JSON string
      return JSON.stringify(data);
  }
}
