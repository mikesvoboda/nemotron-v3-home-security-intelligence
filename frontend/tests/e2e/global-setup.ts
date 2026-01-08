/**
 * Global Setup for E2E Tests
 *
 * Runs once before all tests. Used for:
 * - Setting up shared state
 * - Disabling UI elements that interfere with tests (like product tour)
 *
 * @see https://playwright.dev/docs/test-global-setup-teardown
 */

import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function globalSetup() {
  // Create the storage state file directly without needing a browser
  // This is more reliable than trying to navigate to the app during setup
  const storageState = {
    cookies: [],
    origins: [
      {
        origin: 'http://localhost:5173',
        localStorage: [
          {
            name: 'nemotron-tour-completed',
            value: 'true',
          },
          {
            name: 'nemotron-tour-skipped',
            value: 'true',
          },
        ],
      },
    ],
  };

  // Ensure the directory exists
  const authDir = path.join(__dirname, '.auth');
  if (!fs.existsSync(authDir)) {
    fs.mkdirSync(authDir, { recursive: true });
  }

  // Write the storage state file
  const storagePath = path.join(authDir, 'storage-state.json');
  fs.writeFileSync(storagePath, JSON.stringify(storageState, null, 2));

  console.log('Global setup: Product tour disabled via storage state');
}

export default globalSetup;
