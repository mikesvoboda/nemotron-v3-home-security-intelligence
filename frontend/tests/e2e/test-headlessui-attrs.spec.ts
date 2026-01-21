import { test, expect } from '@playwright/test';

test('inspect HeadlessUI tab attributes', async ({ page }) => {
  await page.goto('http://localhost:5173/settings');

  // Wait for page to load
  await page.waitForTimeout(2000);

  // Get the first tab (Cameras)
  const camerasTab = page.getByRole('tab', { name: /CAMERAS/i });

  // Get all attributes
  const dataSelected = await camerasTab.getAttribute('data-selected');
  const ariaSelected = await camerasTab.getAttribute('aria-selected');
  const dataHover = await camerasTab.getAttribute('data-hover');

  console.log('Cameras tab attributes:');
  console.log('  data-selected:', JSON.stringify(dataSelected));
  console.log('  aria-selected:', JSON.stringify(ariaSelected));
  console.log('  data-hover:', JSON.stringify(dataHover));

  // Click the Processing tab
  const processingTab = page.getByRole('tab', { name: /PROCESSING/i });
  await processingTab.click();
  await page.waitForTimeout(500);

  // Check Processing tab attributes
  const dataSelectedProcessing = await processingTab.getAttribute('data-selected');
  const ariaSelectedProcessing = await processingTab.getAttribute('aria-selected');

  console.log('Processing tab attributes after click:');
  console.log('  data-selected:', JSON.stringify(dataSelectedProcessing));
  console.log('  aria-selected:', JSON.stringify(ariaSelectedProcessing));

  // Check Cameras tab attributes after switching
  const dataSelectedCamerasAfter = await camerasTab.getAttribute('data-selected');
  const ariaSelectedCamerasAfter = await camerasTab.getAttribute('aria-selected');

  console.log('Cameras tab attributes after switching:');
  console.log('  data-selected:', JSON.stringify(dataSelectedCamerasAfter));
  console.log('  aria-selected:', JSON.stringify(ariaSelectedCamerasAfter));
});
