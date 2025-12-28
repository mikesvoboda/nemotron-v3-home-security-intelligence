/**
 * Example usage of ProcessingSettings component
 * This file is not tested and is for demonstration purposes only.
 */

import ProcessingSettings from './ProcessingSettings';

export default function ProcessingSettingsExample() {
  return (
    <div className="min-h-screen bg-background p-8">
      <div className="mx-auto max-w-2xl space-y-6">
        <div>
          <h1 className="mb-2 text-3xl font-bold text-white">Processing Settings Example</h1>
          <p className="text-gray-400">Display and view event processing configuration settings.</p>
        </div>

        <ProcessingSettings />
      </div>
    </div>
  );
}
