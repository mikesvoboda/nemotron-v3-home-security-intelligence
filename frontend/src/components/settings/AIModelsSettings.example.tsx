/**
 * Example usage of AIModelsSettings component
 *
 * This file demonstrates different use cases for the AIModelsSettings component.
 * It is not imported anywhere and serves as documentation.
 */

import AIModelsSettings from './AIModelsSettings';

// Example 1: Default placeholder display (no real data)
export function ExampleDefault() {
  return <AIModelsSettings />;
}

// Example 2: With real GPU stats from API
export function ExampleWithGPUStats() {
  // Typically you'd fetch this from /api/system/gpu
  return (
    <AIModelsSettings
      rtdetrModel={{
        name: 'RT-DETRv2',
        status: 'loaded',
        memoryUsed: 4096, // 4GB in MB
        inferenceFps: 30,
        description: 'Real-time object detection model',
      }}
      nemotronModel={{
        name: 'Nemotron-3',
        status: 'loaded',
        memoryUsed: 8192, // 8GB in MB
        inferenceFps: 15,
        description: 'Risk analysis and reasoning model',
      }}
      totalMemory={24576} // 24GB RTX A5500
    />
  );
}

// Example 3: One model loaded, one unloaded
export function ExampleMixedStates() {
  return (
    <AIModelsSettings
      rtdetrModel={{
        name: 'RT-DETRv2',
        status: 'loaded',
        memoryUsed: 4096,
        inferenceFps: 30,
        description: 'Real-time object detection model',
      }}
      nemotronModel={{
        name: 'Nemotron-3',
        status: 'unloaded',
        memoryUsed: null,
        inferenceFps: null,
        description: 'Risk analysis and reasoning model',
      }}
      totalMemory={24576}
    />
  );
}

// Example 4: Error state
export function ExampleWithError() {
  return (
    <AIModelsSettings
      rtdetrModel={{
        name: 'RT-DETRv2',
        status: 'error',
        memoryUsed: null,
        inferenceFps: null,
        description: 'Real-time object detection model',
      }}
      nemotronModel={{
        name: 'Nemotron-3',
        status: 'loaded',
        memoryUsed: 8192,
        inferenceFps: 15,
        description: 'Risk analysis and reasoning model',
      }}
      totalMemory={24576}
    />
  );
}

// Example 5: Integration with useSystemStatus hook
export function ExampleWithHook() {
  // This is how you'd use it with real-time data
  // import { useSystemStatus } from '@/hooks';
  //
  // const { gpuStats } = useSystemStatus();
  //
  // return (
  //   <AIModelsSettings
  //     rtdetrModel={{
  //       name: 'RT-DETRv2',
  //       status: 'loaded',
  //       memoryUsed: gpuStats?.memory_used ? gpuStats.memory_used * 0.3 : null,
  //       inferenceFps: gpuStats?.inference_fps ?? null,
  //       description: 'Real-time object detection model',
  //     }}
  //     nemotronModel={{
  //       name: 'Nemotron-3',
  //       status: 'loaded',
  //       memoryUsed: gpuStats?.memory_used ? gpuStats.memory_used * 0.7 : null,
  //       inferenceFps: null,
  //       description: 'Risk analysis and reasoning model',
  //     }}
  //     totalMemory={gpuStats?.memory_total ?? null}
  //   />
  // );

  return <AIModelsSettings />;
}
