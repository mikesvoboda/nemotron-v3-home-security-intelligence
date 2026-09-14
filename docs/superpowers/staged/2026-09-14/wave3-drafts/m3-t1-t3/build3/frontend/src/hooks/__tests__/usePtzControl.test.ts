/**
 * Tests for usePtzControl Hook (NEM-4885)
 *
 * Comprehensive tests for PTZ camera control operations using TanStack Query mutations.
 * Tests cover command execution, stop movement, direction mapping, and pending states.
 *
 * @see frontend/src/hooks/usePtzControl.ts
 */

import { QueryClient } from '@tanstack/react-query';
import { renderHook, waitFor, act } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, it, expect, beforeEach } from 'vitest';

import { server } from '../../mocks/server';
import { createQueryWrapper } from '../../test-utils/renderWithProviders';
import { usePtzControl } from '../usePtzControl';

import type { PTZCommandRequest, PTZCommandResponse, PTZDirection } from '../../types/ptz';

// Base URL for camera API
const BASE_URL = '/api/cameras';
const TEST_CAMERA_ID = 'camera-1';

// ============================================================================
// Mock Data
// ============================================================================

const mockSuccessResponse: PTZCommandResponse = {
  success: true,
  message: 'Command executed successfully',
};

const mockErrorResponse = {
  detail: 'PTZ command failed',
};

// ============================================================================
// Tests - executeCommand
// ============================================================================

describe('usePtzControl - executeCommand', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0, staleTime: 0 },
        mutations: { retry: false },
      },
    });
  });

  it('executes pan command with correct parameters', async () => {
    let capturedRequest: PTZCommandRequest | null = null;

    server.use(
      http.post(`${BASE_URL}/${TEST_CAMERA_ID}/onvif/ptz`, async ({ request }) => {
        capturedRequest = (await request.json()) as PTZCommandRequest;
        return HttpResponse.json(mockSuccessResponse);
      })
    );

    const { result } = renderHook(() => usePtzControl(TEST_CAMERA_ID), {
      wrapper: createQueryWrapper(queryClient),
    });

    const panCommand: PTZCommandRequest = {
      command: 'pan',
      value: 1.0,
      speed: 0.5,
    };

    await act(async () => {
      await result.current.executeCommand.mutateAsync(panCommand);
    });

    expect(capturedRequest).toEqual(panCommand);

    await waitFor(() => {
      expect(result.current.executeCommand.isSuccess).toBe(true);
    });
  });

  it('executes tilt command with correct parameters', async () => {
    let capturedRequest: PTZCommandRequest | null = null;

    server.use(
      http.post(`${BASE_URL}/${TEST_CAMERA_ID}/onvif/ptz`, async ({ request }) => {
        capturedRequest = (await request.json()) as PTZCommandRequest;
        return HttpResponse.json(mockSuccessResponse);
      })
    );

    const { result } = renderHook(() => usePtzControl(TEST_CAMERA_ID), {
      wrapper: createQueryWrapper(queryClient),
    });

    const tiltCommand: PTZCommandRequest = {
      command: 'tilt',
      value: -0.5,
    };

    await act(async () => {
      await result.current.executeCommand.mutateAsync(tiltCommand);
    });

    expect(capturedRequest).toEqual(tiltCommand);
  });

  it('executes zoom command with correct parameters', async () => {
    let capturedRequest: PTZCommandRequest | null = null;

    server.use(
      http.post(`${BASE_URL}/${TEST_CAMERA_ID}/onvif/ptz`, async ({ request }) => {
        capturedRequest = (await request.json()) as PTZCommandRequest;
        return HttpResponse.json(mockSuccessResponse);
      })
    );

    const { result } = renderHook(() => usePtzControl(TEST_CAMERA_ID), {
      wrapper: createQueryWrapper(queryClient),
    });

    const zoomCommand: PTZCommandRequest = {
      command: 'zoom',
      value: 0.8,
    };

    await act(async () => {
      await result.current.executeCommand.mutateAsync(zoomCommand);
    });

    expect(capturedRequest).toEqual(zoomCommand);
  });

  it('handles command execution error', async () => {
    server.use(
      http.post(`${BASE_URL}/${TEST_CAMERA_ID}/onvif/ptz`, () => {
        return HttpResponse.json(mockErrorResponse, { status: 500 });
      })
    );

    const { result } = renderHook(() => usePtzControl(TEST_CAMERA_ID), {
      wrapper: createQueryWrapper(queryClient),
    });

    const command: PTZCommandRequest = {
      command: 'pan',
      value: 1.0,
    };

    await act(async () => {
      try {
        await result.current.executeCommand.mutateAsync(command);
      } catch (error) {
        expect(error).toBeDefined();
      }
    });

    await waitFor(() => {
      expect(result.current.executeCommand.isError).toBe(true);
    });
    expect(result.current.executeCommand.error?.message).toContain('PTZ command failed');
  });

  it('tracks pending state during command execution', async () => {
    server.use(
      http.post(`${BASE_URL}/${TEST_CAMERA_ID}/onvif/ptz`, async () => {
        await new Promise((resolve) => setTimeout(resolve, 100));
        return HttpResponse.json(mockSuccessResponse);
      })
    );

    const { result } = renderHook(() => usePtzControl(TEST_CAMERA_ID), {
      wrapper: createQueryWrapper(queryClient),
    });

    const command: PTZCommandRequest = {
      command: 'pan',
      value: 1.0,
    };

    let mutationPromise: Promise<PTZCommandResponse>;
    act(() => {
      mutationPromise = result.current.executeCommand.mutateAsync(command);
    });

    // Should be pending immediately after calling mutate
    await waitFor(() => {
      expect(result.current.executeCommand.isPending).toBe(true);
    });

    // Wait for mutation to complete
    await act(async () => {
      await mutationPromise;
    });

    await waitFor(() => {
      expect(result.current.executeCommand.isPending).toBe(false);
    });
  });
});

// ============================================================================
// Tests - stopMovement
// ============================================================================

describe('usePtzControl - stopMovement', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0, staleTime: 0 },
        mutations: { retry: false },
      },
    });
  });

  it('sends stop command with value 0', async () => {
    let capturedRequest: PTZCommandRequest | null = null;

    server.use(
      http.post(`${BASE_URL}/${TEST_CAMERA_ID}/onvif/ptz`, async ({ request }) => {
        capturedRequest = (await request.json()) as PTZCommandRequest;
        return HttpResponse.json(mockSuccessResponse);
      })
    );

    const { result } = renderHook(() => usePtzControl(TEST_CAMERA_ID), {
      wrapper: createQueryWrapper(queryClient),
    });

    await act(async () => {
      await result.current.stopMovement.mutateAsync();
    });

    expect(capturedRequest).toEqual({
      command: 'stop',
      value: 0,
    });

    await waitFor(() => {
      expect(result.current.stopMovement.isSuccess).toBe(true);
    });
  });

  it('handles stop command error', async () => {
    server.use(
      http.post(`${BASE_URL}/${TEST_CAMERA_ID}/onvif/ptz`, () => {
        return HttpResponse.json(mockErrorResponse, { status: 500 });
      })
    );

    const { result } = renderHook(() => usePtzControl(TEST_CAMERA_ID), {
      wrapper: createQueryWrapper(queryClient),
    });

    await act(async () => {
      try {
        await result.current.stopMovement.mutateAsync();
      } catch (error) {
        expect(error).toBeDefined();
      }
    });

    await waitFor(() => {
      expect(result.current.stopMovement.isError).toBe(true);
    });
  });
});

// ============================================================================
// Tests - moveDirection
// ============================================================================

describe('usePtzControl - moveDirection', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0, staleTime: 0 },
        mutations: { retry: false },
      },
    });
  });

  it.each([
    ['up' as PTZDirection, { command: 'tilt', value: 1.0 }],
    ['down' as PTZDirection, { command: 'tilt', value: -1.0 }],
    ['left' as PTZDirection, { command: 'pan', value: -1.0 }],
    ['right' as PTZDirection, { command: 'pan', value: 1.0 }],
    ['zoom-in' as PTZDirection, { command: 'zoom', value: 1.0 }],
    ['zoom-out' as PTZDirection, { command: 'zoom', value: -1.0 }],
  ])('maps direction "%s" to correct command', async (direction, expectedCommand) => {
    let capturedRequest: PTZCommandRequest | null = null;

    server.use(
      http.post(`${BASE_URL}/${TEST_CAMERA_ID}/onvif/ptz`, async ({ request }) => {
        capturedRequest = (await request.json()) as PTZCommandRequest;
        return HttpResponse.json(mockSuccessResponse);
      })
    );

    const { result } = renderHook(() => usePtzControl(TEST_CAMERA_ID), {
      wrapper: createQueryWrapper(queryClient),
    });

    await act(async () => {
      await result.current.moveDirection.mutateAsync(direction);
    });

    expect(capturedRequest).toEqual(expectedCommand);

    await waitFor(() => {
      expect(result.current.moveDirection.isSuccess).toBe(true);
    });
  });

  it('handles movement error', async () => {
    server.use(
      http.post(`${BASE_URL}/${TEST_CAMERA_ID}/onvif/ptz`, () => {
        return HttpResponse.json(mockErrorResponse, { status: 500 });
      })
    );

    const { result } = renderHook(() => usePtzControl(TEST_CAMERA_ID), {
      wrapper: createQueryWrapper(queryClient),
    });

    await act(async () => {
      try {
        await result.current.moveDirection.mutateAsync('up');
      } catch (error) {
        expect(error).toBeDefined();
      }
    });

    await waitFor(() => {
      expect(result.current.moveDirection.isError).toBe(true);
    });
  });
});

// ============================================================================
// Tests - isMoving State
// ============================================================================

describe('usePtzControl - isMoving', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0, staleTime: 0 },
        mutations: { retry: false },
      },
    });

    server.use(
      http.post(`${BASE_URL}/${TEST_CAMERA_ID}/onvif/ptz`, async () => {
        await new Promise((resolve) => setTimeout(resolve, 100));
        return HttpResponse.json(mockSuccessResponse);
      })
    );
  });

  it('reflects pending state when executeCommand is running', async () => {
    const { result } = renderHook(() => usePtzControl(TEST_CAMERA_ID), {
      wrapper: createQueryWrapper(queryClient),
    });

    expect(result.current.isMoving).toBe(false);

    let mutationPromise: Promise<PTZCommandResponse>;
    act(() => {
      mutationPromise = result.current.executeCommand.mutateAsync({
        command: 'pan',
        value: 1.0,
      });
    });

    await waitFor(() => {
      expect(result.current.isMoving).toBe(true);
    });

    await act(async () => {
      await mutationPromise;
    });

    await waitFor(() => {
      expect(result.current.isMoving).toBe(false);
    });
  });

  it('reflects pending state when moveDirection is running', async () => {
    const { result } = renderHook(() => usePtzControl(TEST_CAMERA_ID), {
      wrapper: createQueryWrapper(queryClient),
    });

    expect(result.current.isMoving).toBe(false);

    let mutationPromise: Promise<PTZCommandResponse>;
    act(() => {
      mutationPromise = result.current.moveDirection.mutateAsync('up');
    });

    await waitFor(() => {
      expect(result.current.isMoving).toBe(true);
    });

    await act(async () => {
      await mutationPromise;
    });

    await waitFor(() => {
      expect(result.current.isMoving).toBe(false);
    });
  });

  it('isMoving is false when stopMovement is running', () => {
    const { result } = renderHook(() => usePtzControl(TEST_CAMERA_ID), {
      wrapper: createQueryWrapper(queryClient),
    });

    // stopMovement pending state doesn't affect isMoving
    act(() => {
      result.current.stopMovement.mutate();
    });

    // isMoving should remain false during stop command
    expect(result.current.isMoving).toBe(false);
  });
});

// ============================================================================
// Tests - Multiple Camera Support
// ============================================================================

describe('usePtzControl - multiple cameras', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0, staleTime: 0 },
        mutations: { retry: false },
      },
    });
  });

  it('sends commands to correct camera', async () => {
    const camera1Id = 'camera-1';
    const camera2Id = 'camera-2';
    let camera1Requests = 0;
    let camera2Requests = 0;

    server.use(
      http.post(`${BASE_URL}/${camera1Id}/onvif/ptz`, () => {
        camera1Requests++;
        return HttpResponse.json(mockSuccessResponse);
      }),
      http.post(`${BASE_URL}/${camera2Id}/onvif/ptz`, () => {
        camera2Requests++;
        return HttpResponse.json(mockSuccessResponse);
      })
    );

    const { result: result1 } = renderHook(() => usePtzControl(camera1Id), {
      wrapper: createQueryWrapper(queryClient),
    });

    const { result: result2 } = renderHook(() => usePtzControl(camera2Id), {
      wrapper: createQueryWrapper(queryClient),
    });

    await act(async () => {
      await result1.current.executeCommand.mutateAsync({ command: 'pan', value: 1.0 });
      await result2.current.executeCommand.mutateAsync({ command: 'tilt', value: 1.0 });
    });

    expect(camera1Requests).toBe(1);
    expect(camera2Requests).toBe(1);
  });
});
