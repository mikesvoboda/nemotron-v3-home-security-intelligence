# Frontend Config Directory

## Purpose

Environment variable validation and type-safe configuration access for the frontend application. Validates `VITE_*` environment variables at startup and provides convenient getters.

## Directory Contents

```
frontend/src/config/
├── AGENTS.md      # This documentation file
├── env.ts         # Environment validation and config getters
└── env.test.ts    # Tests for environment validation
```

## Key Files

| File         | Purpose                                                |
| ------------ | ------------------------------------------------------ |
| `env.ts`     | Environment variable validation with runtime checking  |
| `env.test.ts` | Comprehensive tests for validation logic               |

## Environment Variables (`env.ts`)

### Supported Variables

| Variable             | Required | Type   | Default             | Description                            |
| -------------------- | -------- | ------ | ------------------- | -------------------------------------- |
| `VITE_API_BASE_URL`  | No       | URL    | `''` (relative)     | Base URL for REST API calls            |
| `VITE_WS_BASE_URL`   | No       | WS URL | `undefined` (auto)  | Base URL for WebSocket connections     |
| `VITE_API_KEY`       | No       | string | `undefined`         | API key for authentication             |
| `MODE`               | Auto     | string | `'development'`     | Vite mode (development/production/test)|

### Configuration Interface

```typescript
export interface EnvConfig {
  apiBaseUrl: string;
  wsBaseUrl: string | undefined;
  apiKey: string | undefined;
  mode: string;
  isDevelopment: boolean;
  isProduction: boolean;
  isTest: boolean;
}
```

## Validation Functions

### `validateEnv(env: RawEnv): EnvConfig`

Validates environment variables and returns typed config. Throws `EnvValidationError` on failure.

**Validation Rules:**

- `VITE_API_BASE_URL`: If provided, must be valid HTTP/HTTPS URL
- `VITE_WS_BASE_URL`: If provided, must be valid WS/WSS URL
- Empty strings are allowed (use defaults/fallbacks)

**Throws:** `EnvValidationError` with detailed validation messages

**Example:**

```typescript
import { validateEnv, EnvValidationError } from './config/env';

try {
  const config = validateEnv(import.meta.env);
} catch (error) {
  if (error instanceof EnvValidationError) {
    console.error('Validation errors:', error.validationErrors);
  }
}
```

### `isValidUrl(url: string, required?: boolean): boolean`

Validates URL with allowed protocols: `http:`, `https:`, `ws:`, `wss:`.

**Parameters:**

- `url` - URL string to validate
- `required` - If `false`, empty strings are valid (default: `true`)

**Returns:** `true` if URL is valid

**Examples:**

```typescript
isValidUrl('https://api.example.com'); // true
isValidUrl('http://localhost:8000');   // true
isValidUrl('');                        // false (required by default)
isValidUrl('', false);                 // true (optional)
isValidUrl('ftp://invalid');           // false (wrong protocol)
```

## Convenience Getters

Cached configuration with simple getters:

```typescript
// Get complete config object
const config = getEnvConfig(); // EnvConfig

// Individual getters
const baseUrl = getBaseUrl();           // string
const wsBaseUrl = getWsBaseUrl();       // string | undefined
const apiKey = getApiKey();             // string | undefined
const isDev = isDevelopment();          // boolean
const isProd = isProduction();          // boolean
const isTestMode = isTest();            // boolean
```

**Caching:** Configuration is validated once and cached for subsequent calls.

**Testing:** Use `resetEnvCache()` to clear cache between tests.

## Error Handling

### `EnvValidationError`

Custom error class for validation failures:

```typescript
export class EnvValidationError extends Error {
  public readonly validationErrors: string[];

  constructor(message: string, errors: string[] = []) {
    // Formats errors as bulleted list
    super(message);
    this.name = 'EnvValidationError';
    this.validationErrors = errors;
  }
}
```

**Error Message Format:**

```
Environment validation failed:
  - VITE_API_BASE_URL must be a valid URL (http/https), got: "ftp://invalid"
  - VITE_WS_BASE_URL must use ws:// or wss:// protocol, got: "http://example.com"
```

## Usage Examples

### Basic Configuration Access

```typescript
import { getBaseUrl, getApiKey, isDevelopment } from '@/config/env';

// Use in API client
const apiUrl = `${getBaseUrl()}/api/cameras`;

// Add API key if configured
const headers: HeadersInit = {};
const apiKey = getApiKey();
if (apiKey) {
  headers['X-API-Key'] = apiKey;
}

// Development-only features
if (isDevelopment()) {
  console.log('Debug mode enabled');
}
```

### Full Config Object

```typescript
import { getEnvConfig } from '@/config/env';

function logConfig() {
  const config = getEnvConfig();
  console.log({
    api: config.apiBaseUrl || 'relative',
    ws: config.wsBaseUrl || 'auto-detect',
    auth: config.apiKey ? 'enabled' : 'disabled',
    mode: config.mode,
  });
}
```

### Error Handling

```typescript
import { getEnvConfig, EnvValidationError } from '@/config/env';

try {
  const config = getEnvConfig();
  // Use config...
} catch (error) {
  if (error instanceof EnvValidationError) {
    console.error('Configuration errors:');
    error.validationErrors.forEach((err) => console.error(`  - ${err}`));
    // Show user-friendly error UI
  }
}
```

## Testing Patterns

### Overriding Environment Variables

```typescript
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { validateEnv, resetEnvCache } from './env';

describe('Environment validation', () => {
  const originalEnv = { ...import.meta.env };

  beforeEach(() => {
    resetEnvCache(); // Clear cached config
  });

  afterEach(() => {
    // Restore original env
    Object.assign(import.meta.env, originalEnv);
  });

  it('validates API base URL', () => {
    import.meta.env.VITE_API_BASE_URL = 'invalid-url';

    expect(() => validateEnv(import.meta.env)).toThrow(EnvValidationError);
  });
});
```

### Test Coverage (`env.test.ts`)

Comprehensive tests covering:

- Valid HTTP/HTTPS URLs for API base URL
- Valid WS/WSS URLs for WebSocket base URL
- Empty string handling (optional URLs)
- Invalid URL formats (missing protocol, wrong protocol)
- Invalid WebSocket URLs (HTTP instead of WS)
- Default value handling
- Mode detection (development, production, test)
- Caching behavior
- Cache reset functionality

## Environment-Specific Behavior

### Development (`MODE=development`)

```
VITE_API_BASE_URL=''                    # Relative URLs (Vite proxy)
VITE_WS_BASE_URL=''                     # Auto-detect from window.location
VITE_API_KEY=''                         # No auth
```

### Production (`MODE=production`)

```
VITE_API_BASE_URL=https://api.example.com
VITE_WS_BASE_URL=wss://api.example.com
VITE_API_KEY=secret-key-123
```

### Testing (`MODE=test`)

```
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_BASE_URL=ws://localhost:8000
VITE_API_KEY=test-key
```

## Related Files

- `/frontend/.env` - Default environment variables
- `/frontend/.env.development` - Development overrides
- `/frontend/.env.production` - Production overrides
- `/frontend/src/services/api.ts` - Uses `getBaseUrl()` and `getApiKey()`
- `/frontend/vite.config.ts` - Vite loads `.env` files

## Notes for AI Agents

- Validation happens once at startup (cached)
- Use convenience getters (`getBaseUrl()`) instead of direct `import.meta.env` access
- Empty strings are valid for optional URLs (triggers fallback behavior)
- `resetEnvCache()` is for testing only - don't use in production code
- WebSocket URLs must use ws:// or wss:// protocol (not http://)
- Prototype chain is set for `instanceof` checks to work correctly

## Entry Points

1. **Start with convenience getters** - `getBaseUrl()`, `getApiKey()`, `isDevelopment()`
2. **Full config**: `getEnvConfig()` for complete configuration object
3. **Validation**: `validateEnv()` for custom validation (rarely needed)
4. **Error handling**: Check for `EnvValidationError` instances
