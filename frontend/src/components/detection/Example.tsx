/**
 * Example usage of BoundingBoxOverlay and DetectionImage components
 * This file demonstrates various use cases and configurations
 */

import { useState } from 'react';

import { DetectionImage, BoundingBox } from './index';

// Sample detection data
const sampleBoxes: BoundingBox[] = [
  {
    x: 150,
    y: 200,
    width: 180,
    height: 350,
    label: 'person',
    confidence: 0.95,
  },
  {
    x: 500,
    y: 300,
    width: 220,
    height: 150,
    label: 'car',
    confidence: 0.87,
  },
  {
    x: 800,
    y: 400,
    width: 120,
    height: 120,
    label: 'package',
    confidence: 0.72,
  },
  {
    x: 50,
    y: 100,
    width: 80,
    height: 60,
    label: 'cat',
    confidence: 0.68,
  },
];

export function BasicExample() {
  return (
    <div className="p-4">
      <h2 className="mb-4 text-xl font-bold text-white">Basic Usage</h2>
      <DetectionImage
        src="https://placehold.co/1920x1080/1a1a1a/76b900?text=Camera+Feed"
        alt="Front door camera"
        boxes={sampleBoxes}
        className="rounded-lg shadow-dark-lg"
      />
    </div>
  );
}

export function FilteredExample() {
  const [minConfidence, setMinConfidence] = useState(0.5);

  return (
    <div className="p-4">
      <h2 className="mb-4 text-xl font-bold text-white">Confidence Filtering</h2>
      <div className="mb-4">
        <label className="mb-2 block text-white">
          Min Confidence: {(minConfidence * 100).toFixed(0)}%
        </label>
        <input
          type="range"
          min="0"
          max="1"
          step="0.05"
          value={minConfidence}
          onChange={(e) => setMinConfidence(parseFloat(e.target.value))}
          className="w-full"
        />
      </div>
      <DetectionImage
        src="https://placehold.co/1920x1080/1a1a1a/76b900?text=Camera+Feed"
        alt="Filtered detections"
        boxes={sampleBoxes}
        minConfidence={minConfidence}
        className="rounded-lg shadow-dark-lg"
      />
    </div>
  );
}

export function InteractiveExample() {
  const [selectedBox, setSelectedBox] = useState<BoundingBox | null>(null);

  return (
    <div className="p-4">
      <h2 className="mb-4 text-xl font-bold text-white">Interactive Detections</h2>
      {selectedBox && (
        <div className="mb-4 rounded-lg border border-gray-800 bg-panel p-4">
          <p className="font-semibold text-white">Selected Detection:</p>
          <p className="text-gray-400">
            Label: <span className="text-primary">{selectedBox.label}</span>
          </p>
          <p className="text-gray-400">
            Confidence:{' '}
            <span className="text-primary">{(selectedBox.confidence * 100).toFixed(1)}%</span>
          </p>
          <p className="text-gray-400">
            Position: x={selectedBox.x}, y={selectedBox.y}
          </p>
          <p className="text-gray-400">
            Size: {selectedBox.width}x{selectedBox.height}
          </p>
        </div>
      )}
      <DetectionImage
        src="https://placehold.co/1920x1080/1a1a1a/76b900?text=Click+Detections"
        alt="Interactive camera"
        boxes={sampleBoxes}
        onClick={setSelectedBox}
        className="cursor-pointer rounded-lg shadow-dark-lg"
      />
    </div>
  );
}

export function CustomizationExample() {
  const [showLabels, setShowLabels] = useState(true);
  const [showConfidence, setShowConfidence] = useState(true);

  return (
    <div className="p-4">
      <h2 className="mb-4 text-xl font-bold text-white">Customization Options</h2>
      <div className="mb-4 flex gap-4">
        <label className="flex items-center text-white">
          <input
            type="checkbox"
            checked={showLabels}
            onChange={(e) => setShowLabels(e.target.checked)}
            className="mr-2"
          />
          Show Labels
        </label>
        <label className="flex items-center text-white">
          <input
            type="checkbox"
            checked={showConfidence}
            onChange={(e) => setShowConfidence(e.target.checked)}
            className="mr-2"
          />
          Show Confidence
        </label>
      </div>
      <DetectionImage
        src="https://placehold.co/1920x1080/1a1a1a/76b900?text=Camera+Feed"
        alt="Customizable display"
        boxes={sampleBoxes}
        showLabels={showLabels}
        showConfidence={showConfidence}
        className="rounded-lg shadow-dark-lg"
      />
    </div>
  );
}

export function CameraGridExample() {
  const cameras = [
    {
      id: 1,
      name: 'Front Door',
      detections: sampleBoxes.slice(0, 2),
    },
    {
      id: 2,
      name: 'Backyard',
      detections: sampleBoxes.slice(1, 3),
    },
    {
      id: 3,
      name: 'Garage',
      detections: sampleBoxes.slice(2, 4),
    },
    {
      id: 4,
      name: 'Side Entrance',
      detections: [sampleBoxes[0]],
    },
  ];

  return (
    <div className="p-4">
      <h2 className="mb-4 text-xl font-bold text-white">Camera Grid</h2>
      <div className="grid grid-cols-2 gap-4">
        {cameras.map((camera) => (
          <div key={camera.id} className="rounded-lg bg-panel p-3">
            <h3 className="mb-2 font-semibold text-white">{camera.name}</h3>
            <DetectionImage
              src={`https://placehold.co/800x600/1a1a1a/76b900?text=${camera.name.replace(' ', '+')}`}
              alt={camera.name}
              boxes={camera.detections}
              minConfidence={0.7}
              className="rounded-lg"
            />
            <p className="mt-2 text-sm text-gray-400">
              {camera.detections.length} detection
              {camera.detections.length !== 1 ? 's' : ''}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

// Main example component that shows all use cases
export default function DetectionExamples() {
  const [activeExample, setActiveExample] = useState<string>('basic');

  const examples = [
    { id: 'basic', label: 'Basic', component: BasicExample },
    { id: 'filtered', label: 'Filtered', component: FilteredExample },
    { id: 'interactive', label: 'Interactive', component: InteractiveExample },
    { id: 'custom', label: 'Customization', component: CustomizationExample },
    { id: 'grid', label: 'Camera Grid', component: CameraGridExample },
  ];

  const ActiveComponent = examples.find((ex) => ex.id === activeExample)?.component || BasicExample;

  return (
    <div className="min-h-screen bg-background p-8">
      <div className="mx-auto max-w-7xl">
        <h1 className="mb-6 text-3xl font-bold text-white">Detection Component Examples</h1>

        {/* Tab Navigation */}
        <div className="mb-8 flex gap-2 border-b border-gray-800">
          {examples.map((example) => (
            <button
              key={example.id}
              onClick={() => setActiveExample(example.id)}
              className={`px-4 py-2 font-medium transition-colors ${
                activeExample === example.id
                  ? 'border-b-2 border-primary text-primary'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              {example.label}
            </button>
          ))}
        </div>

        {/* Active Example */}
        <div className="rounded-lg bg-panel shadow-dark-lg">
          <ActiveComponent />
        </div>

        {/* Legend */}
        <div className="mt-8 rounded-lg bg-panel p-4">
          <h3 className="mb-3 font-semibold text-white">Color Legend</h3>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
            <div className="flex items-center gap-2">
              <div className="h-4 w-4 rounded" style={{ backgroundColor: '#ef4444' }} />
              <span className="text-gray-300">Person</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="h-4 w-4 rounded" style={{ backgroundColor: '#3b82f6' }} />
              <span className="text-gray-300">Car</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="h-4 w-4 rounded" style={{ backgroundColor: '#f59e0b' }} />
              <span className="text-gray-300">Dog</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="h-4 w-4 rounded" style={{ backgroundColor: '#8b5cf6' }} />
              <span className="text-gray-300">Cat</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="h-4 w-4 rounded" style={{ backgroundColor: '#10b981' }} />
              <span className="text-gray-300">Package</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="h-4 w-4 rounded" style={{ backgroundColor: '#6b7280' }} />
              <span className="text-gray-300">Other</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
