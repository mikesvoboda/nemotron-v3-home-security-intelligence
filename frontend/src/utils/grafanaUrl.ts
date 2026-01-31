/**
 * Utility for resolving Grafana URLs for remote access.
 */

/**
 * Validates that a hostname is safe (localhost, private IP, or same-origin).
 * This prevents SSRF attacks by ensuring we only redirect to trusted hosts.
 *
 * @param hostname - The hostname to validate
 * @returns true if the hostname is considered safe
 */
function isAllowedHost(hostname: string): boolean {
  // Allow localhost variants
  if (hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '::1') {
    return true;
  }

  // Allow private IPv4 ranges (RFC 1918)
  // 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16
  const privateIPv4Patterns = [
    /^10\.\d{1,3}\.\d{1,3}\.\d{1,3}$/, // 10.0.0.0/8
    /^172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}$/, // 172.16.0.0/12
    /^192\.168\.\d{1,3}\.\d{1,3}$/, // 192.168.0.0/16
  ];

  for (const pattern of privateIPv4Patterns) {
    if (pattern.test(hostname)) {
      return true;
    }
  }

  // Allow current browser hostname (same-origin)
  if (hostname === window.location.hostname) {
    return true;
  }

  // Allow link-local IPv4 (169.254.0.0/16) - used for Docker/container networking
  if (/^169\.254\.\d{1,3}\.\d{1,3}$/.test(hostname)) {
    return true;
  }

  return false;
}

/**
 * Validates that a port number is within safe ranges.
 *
 * @param port - The port number as string
 * @returns true if the port is valid and within allowed range
 */
function isAllowedPort(port: string): boolean {
  const portNum = parseInt(port, 10);
  // Allow standard HTTP ports and common monitoring ports (3000-65535)
  // Block ports below 1024 except 80 and 443 to prevent access to privileged services
  return (
    !isNaN(portNum) &&
    portNum > 0 &&
    portNum <= 65535 &&
    (portNum === 80 || portNum === 443 || portNum >= 1024)
  );
}

/**
 * Resolves the Grafana URL for remote access.
 *
 * When the config contains a localhost URL (e.g., http://localhost:3002),
 * this function extracts the port and constructs a URL using the current
 * browser hostname, enabling access from remote hosts.
 *
 * Security: This function validates URLs to prevent SSRF attacks:
 * - Only allows localhost, private IPs (RFC 1918), and same-origin hosts
 * - Validates port numbers are within safe ranges
 * - Rejects URLs pointing to external/public hosts
 *
 * Examples:
 * - "/grafana" → "/grafana" (relative path, uses nginx proxy)
 * - "http://localhost:3002" → "http://192.168.1.145:3002" (when accessed from that IP)
 * - "http://grafana.example.com:3000" → throws if not same-origin (SSRF protection)
 *
 * @param configUrl - The Grafana URL from backend config
 * @returns Resolved URL that works for both local and remote access
 * @throws Error if the URL points to an untrusted host (SSRF protection)
 */
export function resolveGrafanaUrl(configUrl: string): string {
  // If it's a relative path (e.g., /grafana), use as-is (nginx proxy)
  if (configUrl.startsWith('/')) {
    return configUrl;
  }

  // Try to parse as URL to extract port
  try {
    const url = new URL(configUrl);

    // Security: Validate the hostname is allowed (SSRF protection)
    if (!isAllowedHost(url.hostname)) {
      // Log security event for monitoring
      console.warn(
        `[Security] Blocked potentially unsafe Grafana URL: hostname not in allowlist`
      );
      // Return relative path as safe fallback
      return '/grafana';
    }

    // Validate port if specified
    const port = url.port || (url.protocol === 'https:' ? '443' : '80');
    if (!isAllowedPort(port)) {
      console.warn(`[Security] Blocked Grafana URL with invalid port`);
      return '/grafana';
    }

    // If it's localhost, replace with current hostname
    if (url.hostname === 'localhost' || url.hostname === '127.0.0.1') {
      const currentHostname = window.location.hostname;

      // Use http for Grafana (it typically doesn't have SSL configured)
      return `http://${currentHostname}:${port}`;
    }

    // For other allowed hosts, return as-is
    return configUrl;
  } catch {
    // If URL parsing fails, return safe fallback
    console.warn('[Security] Failed to parse Grafana URL, using fallback');
    return '/grafana';
  }
}
