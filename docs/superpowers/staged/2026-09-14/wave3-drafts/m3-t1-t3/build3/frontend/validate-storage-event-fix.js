#!/usr/bin/env node

/**
 * Validation script for StorageEvent constructor fix
 *
 * This script validates that StorageEvent can be constructed without
 * the storageArea property, which causes issues in jsdom environments.
 */

import { JSDOM } from 'jsdom';

const dom = new JSDOM('<!DOCTYPE html>', { url: 'http://localhost/' });
global.window = dom.window;
global.document = window.document;

console.log('Testing StorageEvent constructor without storageArea property...\n');

let passed = 0;
let failed = 0;

// Test 1: Create StorageEvent without storageArea (the fix)
try {
  const event = new window.StorageEvent('storage', {
    key: 'test_key',
    newValue: 'new_value',
    oldValue: 'old_value',
    url: window.location.href,
  });

  if (event.key === 'test_key' &&
      event.newValue === 'new_value' &&
      event.oldValue === 'old_value') {
    console.log('✓ Test 1 PASSED: StorageEvent without storageArea');
    passed++;
  } else {
    console.error('✗ Test 1 FAILED: Properties not set correctly');
    failed++;
  }
} catch (error) {
  console.error('✗ Test 1 FAILED:', error.message);
  failed++;
}

// Test 2: Create StorageEvent with null newValue (cleared key scenario)
try {
  const event = new window.StorageEvent('storage', {
    key: 'cleared_key',
    newValue: null,
    oldValue: 'some_value',
    url: window.location.href,
  });

  if (event.key === 'cleared_key' &&
      event.newValue === null &&
      event.oldValue === 'some_value') {
    console.log('✓ Test 2 PASSED: StorageEvent with null newValue');
    passed++;
  } else {
    console.error('✗ Test 2 FAILED: Properties not set correctly');
    failed++;
  }
} catch (error) {
  console.error('✗ Test 2 FAILED:', error.message);
  failed++;
}

// Test 3: Verify event can be dispatched
try {
  let eventFired = false;

  window.addEventListener('storage', (e) => {
    eventFired = true;
  });

  const event = new window.StorageEvent('storage', {
    key: 'dispatch_test',
    newValue: 'value',
    oldValue: null,
    url: window.location.href,
  });

  window.dispatchEvent(event);

  if (eventFired) {
    console.log('✓ Test 3 PASSED: StorageEvent can be dispatched');
    passed++;
  } else {
    console.error('✗ Test 3 FAILED: Event was not fired');
    failed++;
  }
} catch (error) {
  console.error('✗ Test 3 FAILED:', error.message);
  failed++;
}

// Test 4: Verify it fails WITH storageArea (showing the problem we fixed)
console.log('\n--- Testing that storageArea causes issues (expected to fail) ---');
try {
  const event = new window.StorageEvent('storage', {
    key: 'test_key',
    newValue: 'new_value',
    oldValue: 'old_value',
    storageArea: window.localStorage,
    url: window.location.href,
  });
  console.log('✗ Test 4: storageArea did NOT throw error (unexpected - jsdom may have changed)');
  console.log('  This is actually fine - jsdom might have fixed the issue');
} catch (error) {
  console.log('✓ Test 4: storageArea throws error as expected in jsdom');
  console.log('  Error:', error.message);
}

// Summary
console.log('\n' + '='.repeat(50));
console.log(`Tests passed: ${passed}/3`);
console.log(`Tests failed: ${failed}/3`);
console.log('='.repeat(50));

process.exit(failed > 0 ? 1 : 0);
