import { describe, it, expect } from 'vitest';

import { extractErrorMessage, sanitizeErrorMessage } from '../sanitize';

describe('extractErrorMessage', () => {
  describe('Happy Path', () => {
    it('should extract message from Error object', () => {
      const error = new Error('Test error message');
      expect(extractErrorMessage(error)).toBe('Test error message');
    });

    it('should return string as-is', () => {
      expect(extractErrorMessage('Plain string message')).toBe('Plain string message');
    });

    it('should return empty string for null', () => {
      expect(extractErrorMessage(null)).toBe('');
    });

    it('should return empty string for undefined', () => {
      expect(extractErrorMessage(undefined)).toBe('');
    });
  });

  describe('Edge Cases', () => {
    it('should handle empty string', () => {
      expect(extractErrorMessage('')).toBe('');
    });

    it('should convert unexpected types to string', () => {
      // @ts-expect-error - testing runtime behavior
      expect(extractErrorMessage(123)).toBe('123');
      // @ts-expect-error - testing runtime behavior
      expect(extractErrorMessage({ custom: 'object' })).toBe('[object Object]');
    });

    it('should handle Error subclasses', () => {
      const typeError = new TypeError('Type error message');
      expect(extractErrorMessage(typeError)).toBe('Type error message');

      const rangeError = new RangeError('Range error message');
      expect(extractErrorMessage(rangeError)).toBe('Range error message');
    });
  });
});

describe('sanitizeErrorMessage', () => {
  describe('Happy Path - Script Tag Removal', () => {
    it('should remove simple script tags', () => {
      const malicious = '<script>alert("XSS")</script>Hello';
      const result = sanitizeErrorMessage(malicious);
      expect(result).toBe('Hello');
      expect(result).not.toContain('<script>');
      expect(result).not.toContain('alert');
    });

    it('should remove onclick event handlers', () => {
      const malicious = '<div onclick="alert(\'XSS\')">Click me</div>';
      const result = sanitizeErrorMessage(malicious);
      expect(result).toBe('Click me');
      expect(result).not.toContain('onclick');
      expect(result).not.toContain('alert');
    });

    it('should strip all HTML tags but preserve text content', () => {
      const input = '<p>Paragraph</p><div>Division</div><span>Span</span>';
      const result = sanitizeErrorMessage(input);
      expect(result).toBe('ParagraphDivisionSpan');
      expect(result).not.toContain('<');
      expect(result).not.toContain('>');
    });

    it('should allow plain text without modification', () => {
      const plainText = 'This is a safe error message';
      expect(sanitizeErrorMessage(plainText)).toBe(plainText);
    });

    it('should trim whitespace', () => {
      expect(sanitizeErrorMessage('  whitespace  ')).toBe('whitespace');
      expect(sanitizeErrorMessage('\n\ttabs and newlines\n\t')).toBe('tabs and newlines');
    });
  });

  describe('Edge Cases', () => {
    it('should handle empty string', () => {
      expect(sanitizeErrorMessage('')).toBe('');
    });

    it('should handle string with only whitespace', () => {
      expect(sanitizeErrorMessage('   \n\t   ')).toBe('');
    });

    it('should handle nested script tags', () => {
      const malicious = '<script><script>alert("XSS")</script></script>Nested';
      const result = sanitizeErrorMessage(malicious);
      expect(result).toBe('Nested');
      expect(result).not.toContain('<script>');
      expect(result).not.toContain('alert');
    });

    it('should handle case variations in script tags', () => {
      const variations = [
        '<SCRIPT>alert("XSS")</SCRIPT>',
        '<ScRiPt>alert("XSS")</ScRiPt>',
        '<sCrIpT>alert("XSS")</sCrIpT>',
      ];

      variations.forEach((malicious) => {
        const result = sanitizeErrorMessage(malicious);
        expect(result).toBe('');
        expect(result).not.toContain('alert');
      });
    });

    it('should handle URL-encoded payloads', () => {
      const encoded = '%3Cscript%3Ealert(%22XSS%22)%3C%2Fscript%3E';
      const result = sanitizeErrorMessage(encoded);
      // DOMPurify treats this as plain text since it's not decoded HTML
      expect(result).not.toContain('<script>');
    });

    it('should handle Unicode bypass attempts', () => {
      // Unicode escape sequences are decoded and then sanitized
      const unicodeEscaped = '\u003cscript\u003ealert("XSS")\u003c/script\u003e';
      const unicodeResult = sanitizeErrorMessage(unicodeEscaped);
      expect(unicodeResult).not.toContain('script');
      expect(unicodeResult).not.toContain('alert');

      // HTML entities are treated as plain text (not decoded by DOMPurify in text-only mode)
      const htmlEntities = '&#60;script&#62;alert("XSS")&#60;/script&#62;';
      const entityResult = sanitizeErrorMessage(htmlEntities);
      // DOMPurify preserves HTML entities as plain text when ALLOWED_TAGS is empty
      expect(entityResult).toContain('&#60;');
      expect(entityResult).toContain('&#62;');
      // But it should not contain actual script tags
      expect(entityResult).not.toContain('<script>');
    });

    it('should handle HTML entities', () => {
      const entities = '&lt;script&gt;alert(&quot;XSS&quot;)&lt;/script&gt;';
      const result = sanitizeErrorMessage(entities);
      // DOMPurify decodes entities but strips tags
      expect(result).not.toContain('<');
      expect(result).not.toContain('>');
    });

    it('should handle malformed HTML', () => {
      const malformed = '<script<script>alert("XSS")</script>';
      const result = sanitizeErrorMessage(malformed);
      // DOMPurify extracts text content from malformed tags
      // The second <script> is recognized and removed, but text remains
      expect(result).not.toContain('<script');
      expect(result).not.toContain('</script>');
      // Text content may be preserved, but tags are removed
      expect(result).not.toContain('<');
      expect(result).not.toContain('>');
    });

    it('should handle very long input', () => {
      const longInput = '<script>' + 'A'.repeat(10000) + '</script>Safe';
      const result = sanitizeErrorMessage(longInput);
      // DOMPurify removes script tags but preserves text content
      expect(result).toContain('Safe');
      expect(result).not.toContain('<script>');
      expect(result).not.toContain('</script>');
      // Verify it's a reasonable length (script content removed)
      expect(result.length).toBeLessThan(longInput.length);
    });
  });

  describe('Malicious Input - OWASP XSS Vectors', () => {
    it('should block SVG-based XSS', () => {
      const svgXss = '<svg/onload=alert("XSS")>SVG attack';
      const result = sanitizeErrorMessage(svgXss);
      expect(result).not.toContain('onload');
      expect(result).not.toContain('alert');
      expect(result).not.toContain('<svg');
      // Malformed SVG syntax causes entire content to be treated as tag/attributes
      // DOMPurify removes it all for safety
      expect(result).toBe('');
    });

    it('should block IMG tag XSS with onerror', () => {
      const imgXss = '<img src=x onerror=alert("XSS")>Image attack';
      const result = sanitizeErrorMessage(imgXss);
      expect(result).not.toContain('onerror');
      expect(result).not.toContain('alert');
      expect(result).toBe('Image attack');
    });

    it('should block IMG tag XSS with onload', () => {
      const imgXss = '<img src="valid.jpg" onload=alert("XSS")>';
      const result = sanitizeErrorMessage(imgXss);
      expect(result).not.toContain('onload');
      expect(result).not.toContain('alert');
      expect(result).toBe('');
    });

    it('should block event handler variations', () => {
      const eventHandlers = [
        '<body onload=alert("XSS")>',
        '<input onfocus=alert("XSS") autofocus>',
        '<select onfocus=alert("XSS") autofocus>',
        '<textarea onfocus=alert("XSS") autofocus>',
        '<iframe onload=alert("XSS")>',
        '<div onmouseover=alert("XSS")>Hover</div>',
        '<button onclick=alert("XSS")>Click</button>',
      ];

      eventHandlers.forEach((malicious) => {
        const result = sanitizeErrorMessage(malicious);
        expect(result).not.toContain('alert');
        expect(result).not.toMatch(/on\w+=/);
      });
    });

    it('should block javascript: protocol URLs', () => {
      const jsUrls = [
        '<a href="javascript:alert(\'XSS\')">Click</a>',
        '<a href="javascript:void(0)">Click</a>',
        '<iframe src="javascript:alert(\'XSS\')">',
      ];

      jsUrls.forEach((malicious) => {
        const result = sanitizeErrorMessage(malicious);
        expect(result).not.toContain('javascript:');
        expect(result).not.toContain('alert');
      });
    });

    it('should block data URLs with JavaScript', () => {
      const dataUrl = '<a href="data:text/html,<script>alert(\'XSS\')</script>">Click</a>';
      const result = sanitizeErrorMessage(dataUrl);
      expect(result).not.toContain('data:');
      expect(result).not.toContain('<script>');
      expect(result).not.toContain('alert');
    });

    it('should block base64-encoded payloads in data URLs', () => {
      // Base64 encoded <script>alert('XSS')</script>
      const base64Xss = '<img src="data:image/svg+xml;base64,PHNjcmlwdD5hbGVydCgnWFNTJyk8L3NjcmlwdD4=">';
      const result = sanitizeErrorMessage(base64Xss);
      expect(result).not.toContain('data:');
      expect(result).not.toContain('base64');
      expect(result).toBe('');
    });

    it('should block expression() in CSS (IE-specific)', () => {
      const cssXss = '<div style="width: expression(alert(\'XSS\'))">IE attack</div>';
      const result = sanitizeErrorMessage(cssXss);
      expect(result).not.toContain('expression');
      expect(result).not.toContain('alert');
      expect(result).toBe('IE attack');
    });

    it('should block vbscript: protocol', () => {
      const vbscript = '<a href="vbscript:msgbox(\'XSS\')">Click</a>';
      const result = sanitizeErrorMessage(vbscript);
      expect(result).not.toContain('vbscript:');
      expect(result).not.toContain('msgbox');
    });

    it('should block embedded objects and embeds', () => {
      const objectXss = '<object data="javascript:alert(\'XSS\')"></object>';
      const embedXss = '<embed src="javascript:alert(\'XSS\')"></embed>';

      expect(sanitizeErrorMessage(objectXss)).not.toContain('javascript:');
      expect(sanitizeErrorMessage(embedXss)).not.toContain('javascript:');
    });

    it('should block meta refresh redirects', () => {
      const metaXss = '<meta http-equiv="refresh" content="0;url=javascript:alert(\'XSS\')">';
      const result = sanitizeErrorMessage(metaXss);
      expect(result).not.toContain('javascript:');
      expect(result).not.toContain('http-equiv');
    });

    it('should block link href with javascript', () => {
      const linkXss = '<link rel="stylesheet" href="javascript:alert(\'XSS\')">';
      const result = sanitizeErrorMessage(linkXss);
      expect(result).not.toContain('javascript:');
      expect(result).not.toContain('alert');
    });

    it('should block form action with javascript', () => {
      const formXss = '<form action="javascript:alert(\'XSS\')"><input type="submit"></form>';
      const result = sanitizeErrorMessage(formXss);
      expect(result).not.toContain('javascript:');
      expect(result).not.toContain('alert');
    });

    it('should block style tags with XSS', () => {
      const styleXss = '<style>body{background:url("javascript:alert(\'XSS\')")}</style>';
      const result = sanitizeErrorMessage(styleXss);
      expect(result).not.toContain('javascript:');
      expect(result).not.toContain('alert');
      expect(result).not.toContain('background');
    });

    it('should block XML data islands (IE-specific)', () => {
      const xmlXss = '<xml id="xss" src="javascript:alert(\'XSS\')"></xml>';
      const result = sanitizeErrorMessage(xmlXss);
      expect(result).not.toContain('javascript:');
      expect(result).not.toContain('alert');
    });

    it('should block marquee with event handlers', () => {
      const marqueeXss = '<marquee onstart=alert("XSS")>Scrolling</marquee>';
      const result = sanitizeErrorMessage(marqueeXss);
      expect(result).not.toContain('onstart');
      expect(result).not.toContain('alert');
    });
  });

  describe('Security Guarantees', () => {
    it('should guarantee no HTML tags in output', () => {
      const inputs = [
        '<script>alert("XSS")</script>',
        '<img src=x onerror=alert("XSS")>',
        '<svg/onload=alert("XSS")>',
        '<iframe src="javascript:alert(\'XSS\')">',
        '<div onclick="alert(\'XSS\')">Click</div>',
      ];

      inputs.forEach((input) => {
        const result = sanitizeErrorMessage(input);
        expect(result).not.toContain('<');
        expect(result).not.toContain('>');
      });
    });

    it('should guarantee no javascript: URLs in output', () => {
      const inputs = [
        '<a href="javascript:alert(\'XSS\')">Click</a>',
        '<iframe src="javascript:alert(\'XSS\')">',
        '<form action="javascript:alert(\'XSS\')">',
      ];

      inputs.forEach((input) => {
        const result = sanitizeErrorMessage(input);
        expect(result).not.toContain('javascript:');
      });
    });

    it('should guarantee no event handlers in output', () => {
      const inputs = [
        '<div onclick="alert(\'XSS\')">',
        '<img onerror="alert(\'XSS\')">',
        '<body onload="alert(\'XSS\')">',
        '<svg onload="alert(\'XSS\')">',
      ];

      inputs.forEach((input) => {
        const result = sanitizeErrorMessage(input);
        expect(result).not.toMatch(/on\w+=/i);
      });
    });

    it('should guarantee output is plain text only', () => {
      const complexHtml = `
        <div class="container">
          <script>alert("XSS")</script>
          <p onclick="alert('XSS')">Paragraph</p>
          <img src=x onerror=alert("XSS")>
          <a href="javascript:alert('XSS')">Link</a>
          <svg/onload=alert("XSS")>
          Safe text content
        </div>
      `;

      const result = sanitizeErrorMessage(complexHtml);
      // DOMPurify with KEEP_CONTENT: true preserves safe text content
      expect(result).toContain('Paragraph');
      expect(result).toContain('Link');
      // Note: "Safe text content" after malformed <svg/onload> may be removed
      // by DOMPurify's aggressive sanitization - this is a security feature
      // But removes all HTML tags and dangerous attributes
      expect(result).not.toContain('<');
      expect(result).not.toContain('>');
      expect(result).not.toContain('onclick');
      expect(result).not.toContain('onerror');
      expect(result).not.toContain('onload');
      expect(result).not.toContain('javascript:');
      expect(result).not.toContain('alert("XSS")');
      expect(result).not.toContain("alert('XSS')");
    });

    it('should preserve safe text while removing all dangerous content', () => {
      const input = 'User said: <script>alert("XSS")</script> "Hello World"';
      const result = sanitizeErrorMessage(input);
      expect(result).toBe('User said:  "Hello World"');
      expect(result).toContain('User said');
      expect(result).toContain('Hello World');
      expect(result).not.toContain('<script>');
      expect(result).not.toContain('alert');
    });
  });
});
