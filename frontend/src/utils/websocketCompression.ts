/**
 * WebSocket Message Compression Utilities (NEM-3154)
 *
 * Handles decompression of WebSocket messages that were compressed on the backend.
 * The compression protocol uses:
 * - A magic byte prefix (0x00) to identify compressed messages
 * - zlib/deflate compression for the message payload
 *
 * Binary messages starting with the magic byte are decompressed using pako.
 * Text messages and binary messages without the magic byte are passed through as-is.
 */

import pako from 'pako';

// Magic byte prefix for compressed messages (must match backend)
// 0x00 is used because it's not valid JSON/UTF-8 start
export const COMPRESSION_MAGIC_BYTE = 0x00;

/**
 * Check if a message is compressed (binary with magic byte prefix).
 *
 * @param data - The message data from WebSocket
 * @returns True if the message is compressed
 */
export function isCompressedMessage(data: unknown): data is ArrayBuffer | Blob {
  if (data instanceof ArrayBuffer) {
    const view = new Uint8Array(data);
    return view.length > 0 && view[0] === COMPRESSION_MAGIC_BYTE;
  }
  if (data instanceof Blob) {
    // Blob needs to be read async, so we can't check synchronously
    // We'll handle this case in decompressMessage
    return true; // Assume blob might be compressed, check in decompress
  }
  return false;
}

/**
 * Decompress a WebSocket message.
 *
 * Handles both ArrayBuffer and Blob inputs. If the message doesn't start
 * with the compression magic byte, it's returned as-is (decoded as UTF-8).
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

  if (bytes[0] !== COMPRESSION_MAGIC_BYTE) {
    // Not compressed, decode as UTF-8
    const decoder = new TextDecoder('utf-8');
    return decoder.decode(bytes);
  }

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

/**
 * Parse a WebSocket message, handling both compressed and uncompressed formats.
 *
 * This is the main entry point for processing WebSocket messages. It:
 * 1. Checks if the message is binary (potentially compressed)
 * 2. Decompresses if necessary
 * 3. Parses the JSON payload
 *
 * @param event - The WebSocket MessageEvent
 * @returns Promise resolving to the parsed message data
 */
export async function parseWebSocketMessage(event: MessageEvent): Promise<unknown> {
  const data: unknown = event.data;

  // Handle string messages (uncompressed)
  if (typeof data === 'string') {
    return JSON.parse(data);
  }

  // Handle binary messages (potentially compressed)
  if (data instanceof ArrayBuffer || data instanceof Blob) {
    const decompressed = await decompressMessage(data);
    return JSON.parse(decompressed);
  }

  // Unknown format, return as-is
  return data;
}
