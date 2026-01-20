/**
 * Utility for resolving Grafana URLs for remote access.
 */

/**
 * Resolves the Grafana URL for remote access.
 *
 * When the config contains a localhost URL (e.g., http://localhost:3002),
 * this function extracts the port and constructs a URL using the current
 * browser hostname, enabling access from remote hosts.
 *
 * Examples:
 * - "/grafana" → "/grafana" (relative path, uses nginx proxy)
 * - "http://localhost:3002" → "http://192.168.1.145:3002" (when accessed from that IP)
 * - "http://grafana.example.com:3000" → "http://grafana.example.com:3000" (already remote-accessible)
 *
 * @param configUrl - The Grafana URL from backend config
 * @returns Resolved URL that works for both local and remote access
 */
export function resolveGrafanaUrl(configUrl: string): string {
  // If it's a relative path (e.g., /grafana), use as-is (nginx proxy)
  if (configUrl.startsWith('/')) {
    return configUrl;
  }

  // Try to parse as URL to extract port
  try {
    const url = new URL(configUrl);

    // If it's localhost, replace with current hostname
    if (url.hostname === 'localhost' || url.hostname === '127.0.0.1') {
      const currentHostname = window.location.hostname;
      const port = url.port || (url.protocol === 'https:' ? '443' : '80');

      // Use http for Grafana (it typically doesn't have SSL configured)
      return `http://${currentHostname}:${port}`;
    }

    // Otherwise return as-is
    return configUrl;
  } catch {
    // If URL parsing fails, return as-is
    return configUrl;
  }
}
