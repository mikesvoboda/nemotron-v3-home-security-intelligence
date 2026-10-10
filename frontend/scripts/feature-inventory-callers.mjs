#!/usr/bin/env node
// feature-inventory-callers.mjs — who calls a client function, up to the route
// that mounts it.
//
//   node scripts/feature-inventory-callers.mjs src/services/api.ts fetchEvents
//
// Used to decide whether a request belongs in a feature row of
// docs/reference/feature-inventory.md or in its §5, "Client requests no feature
// reaches". Prints the reference chain (TypeScript findReferences, production
// files only) and MOUNTED or NOT MOUNTED. MOUNTED means a mounted module
// references the function; check the last hop takes it (see `callerChain`).
// Run from frontend/.
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';

import { callerChain } from './feature-inventory-lib.mjs';

const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const [file, name] = process.argv.slice(2);
if (!file || !name) {
  console.error('usage: feature-inventory-callers.mjs <src/file.ts> <function>');
  process.exit(2);
}
const { mounted, lines } = callerChain({ root: FRONTEND, file, name });
console.log(lines.join('\n') || '(no production reference)');
console.log(mounted ? 'MOUNTED' : 'NOT MOUNTED');
