/**
 * Example usage of ProcessingSettings component
 * This file is not tested and is for demonstration purposes only.
 */

import ProcessingSettings from './ProcessingSettings';

export default function ProcessingSettingsExample() {
  return (
    <div className="min-h-screen bg-background p-8">
      <div className="max-w-2xl mx-auto space-y-6">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">
            Processing Settings Example
          </h1>
          <p className="text-gray-400">
            Display and view event processing configuration settings.
          </p>
        </div>

        <ProcessingSettings />
      </div>
    </div>
  );
}
