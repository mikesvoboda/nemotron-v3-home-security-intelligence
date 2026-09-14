/**
 * Postinstall script to ensure minimatch 10.x CJS build is backward-compatible
 * with packages that expect `require('minimatch')` to return the minimatch function directly.
 *
 * Background: minimatch < 10.2.1 has a ReDoS vulnerability (GHSA-3ppc-4f35-3m26).
 * minimatch 10.x exports `minimatch` as a named export but NOT as module.exports.
 * Many eslint plugins (jsx-a11y, import, react) use `require('minimatch')` as a function.
 * This script patches the CJS entry point to restore backward compatibility.
 */
'use strict';

const fs = require('fs');
const path = require('path');

const PATCH_MARKER = '// PATCHED: backward-compat default export';

/**
 * Find all minimatch CJS index.js files in node_modules.
 * @param {string} baseDir - The node_modules directory to search.
 * @returns {string[]} Array of file paths.
 */
function findMinimatchFiles(baseDir) {
  const results = [];

  function walk(dir) {
    let entries;
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch {
      return;
    }
    for (const entry of entries) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        if (entry.name === 'minimatch') {
          // Check for dist/commonjs/index.js (minimatch 10.x structure)
          const cjsIndex = path.join(full, 'dist', 'commonjs', 'index.js');
          if (fs.existsSync(cjsIndex)) {
            results.push(cjsIndex);
          }
          // Also check nested node_modules
          const nested = path.join(full, 'node_modules');
          if (fs.existsSync(nested)) {
            walk(nested);
          }
        } else if (entry.name === 'node_modules') {
          walk(full);
        }
      }
    }
  }

  walk(baseDir);
  return results;
}

/**
 * Patch a minimatch CJS index.js to export the minimatch function as module.exports.
 * @param {string} filePath - Path to the CJS index.js file.
 * @returns {boolean} Whether the file was patched.
 */
function patchFile(filePath) {
  const content = fs.readFileSync(filePath, 'utf8');

  // Already patched
  if (content.includes(PATCH_MARKER)) {
    return false;
  }

  // Verify this is minimatch 10.x (has exports.minimatch but no module.exports = minimatch)
  if (!content.includes('exports.minimatch =') || content.includes('module.exports = minimatch')) {
    return false;
  }

  // Append backward-compat patch: make module.exports the minimatch function
  // while preserving all named exports as properties on the function
  const patch = `
${PATCH_MARKER}
const _origMinimatch = exports.minimatch;
const _wrappedMinimatch = function minimatch(p, pattern, options) {
  return _origMinimatch(p, pattern, options);
};
// Copy all named exports onto the function
Object.assign(_wrappedMinimatch, exports);
_wrappedMinimatch.default = _wrappedMinimatch;
module.exports = _wrappedMinimatch;
`;

  fs.writeFileSync(filePath, content + patch, 'utf8');
  return true;
}

// Main
const nodeModules = path.join(__dirname, '..', 'node_modules');
const files = findMinimatchFiles(nodeModules);

let patched = 0;
for (const file of files) {
  if (patchFile(file)) {
    patched++;
  }
}

if (patched > 0) {
  console.log(`[patch-minimatch-compat] Patched ${patched} minimatch CJS file(s) for backward compatibility.`);
} else if (files.length === 0) {
  console.log('[patch-minimatch-compat] No minimatch 10.x CJS files found (may be using older version).');
}
