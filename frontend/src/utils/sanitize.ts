import DOMPurify from 'dompurify';

/**
 * Extracts a safe text message from various error formats.
 * Handles Error objects, strings, and null/undefined values.
 */
export function extractErrorMessage(message: string | Error | null | undefined): string {
  if (message === null || message === undefined) {
    return '';
  }

  if (message instanceof Error) {
    return message.message;
  }

  if (typeof message === 'string') {
    return message;
  }

  // Fallback for unexpected types
  return String(message);
}

/**
 * Sanitizes a message string to prevent XSS attacks.
 * Uses DOMPurify to remove any potentially dangerous HTML/script content.
 *
 * @param message - The raw message to sanitize
 * @returns Sanitized plain text message
 */
export function sanitizeErrorMessage(message: string): string {
  // Use DOMPurify to sanitize, allowing NO tags (text only)
  // This removes all HTML tags and decodes entities
  const sanitized = DOMPurify.sanitize(message, {
    ALLOWED_TAGS: [], // No HTML tags allowed
    ALLOWED_ATTR: [], // No attributes allowed
    KEEP_CONTENT: true, // Keep text content from tags
  });

  // Additional safety: trim whitespace and normalize
  return sanitized.trim();
}
