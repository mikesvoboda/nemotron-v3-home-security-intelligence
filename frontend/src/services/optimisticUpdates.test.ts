/**
 * Tests for optimistic updates utilities (NEM-3361)
 */

import { QueryClient } from '@tanstack/react-query';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import {
  optimisticAddToList,
  optimisticUpdateInList,
  optimisticRemoveFromList,
  replaceOptimisticItem,
  optimisticUpdateSingle,
  rollbackList,
  rollbackSingle,
  cancelOutgoingQueries,
  invalidateQueries,
  createOptimisticAddConfig,
  createOptimisticUpdateConfig,
  createOptimisticDeleteConfig,
} from './optimisticUpdates';

describe('optimisticUpdates', () => {
  let queryClient: QueryClient;
  const testQueryKey = ['test', 'list'];

  interface TestItem {
    id: string;
    name: string;
    status: string;
    [key: string]: unknown;
  }

  const mockItems: TestItem[] = [
    { id: '1', name: 'Item 1', status: 'active' },
    { id: '2', name: 'Item 2', status: 'active' },
    { id: '3', name: 'Item 3', status: 'inactive' },
  ];

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });
    // Pre-populate the cache
    queryClient.setQueryData(testQueryKey, mockItems);
  });

  afterEach(() => {
    queryClient.clear();
  });

  // ============================================================================
  // List Operation Helpers
  // ============================================================================

  describe('optimisticAddToList', () => {
    it('should add item to end of list by default', () => {
      const newItem: TestItem = { id: '4', name: 'Item 4', status: 'active' };
      const previousData = optimisticAddToList(queryClient, testQueryKey, newItem);

      const currentData = queryClient.getQueryData<TestItem[]>(testQueryKey);

      expect(previousData).toEqual(mockItems);
      expect(currentData).toHaveLength(4);
      expect(currentData?.[3]).toEqual(newItem);
    });

    it('should add item to start of list when position is start', () => {
      const newItem: TestItem = { id: '4', name: 'Item 4', status: 'active' };
      optimisticAddToList(queryClient, testQueryKey, newItem, 'start');

      const currentData = queryClient.getQueryData<TestItem[]>(testQueryKey);

      expect(currentData?.[0]).toEqual(newItem);
      expect(currentData).toHaveLength(4);
    });

    it('should handle empty list', () => {
      const emptyQueryKey = ['test', 'empty'];
      const newItem: TestItem = { id: '1', name: 'Item 1', status: 'active' };

      optimisticAddToList(queryClient, emptyQueryKey, newItem);

      const currentData = queryClient.getQueryData<TestItem[]>(emptyQueryKey);

      expect(currentData).toEqual([newItem]);
    });

    it('should return undefined for non-existent query', () => {
      const nonExistentKey = ['non', 'existent'];
      const newItem: TestItem = { id: '1', name: 'Item 1', status: 'active' };

      const previousData = optimisticAddToList(queryClient, nonExistentKey, newItem);

      expect(previousData).toBeUndefined();
    });
  });

  describe('optimisticUpdateInList', () => {
    it('should update item in list by id', () => {
      const previousData = optimisticUpdateInList<TestItem>(queryClient, testQueryKey, '2', {
        name: 'Updated Item 2',
        status: 'updated',
      });

      const currentData = queryClient.getQueryData<TestItem[]>(testQueryKey);

      expect(previousData).toEqual(mockItems);
      expect(currentData?.[1]).toEqual({
        id: '2',
        name: 'Updated Item 2',
        status: 'updated',
      });
    });

    it('should not modify other items', () => {
      optimisticUpdateInList<TestItem>(queryClient, testQueryKey, '2', { name: 'Updated' });

      const currentData = queryClient.getQueryData<TestItem[]>(testQueryKey);

      expect(currentData?.[0]).toEqual(mockItems[0]);
      expect(currentData?.[2]).toEqual(mockItems[2]);
    });

    it('should handle non-existent item id gracefully', () => {
      optimisticUpdateInList<TestItem>(queryClient, testQueryKey, 'non-existent', {
        name: 'Updated',
      });

      const currentData = queryClient.getQueryData<TestItem[]>(testQueryKey);

      expect(currentData).toEqual(mockItems);
    });
  });

  describe('optimisticRemoveFromList', () => {
    it('should remove item from list by id', () => {
      const previousData = optimisticRemoveFromList<TestItem>(queryClient, testQueryKey, '2');

      const currentData = queryClient.getQueryData<TestItem[]>(testQueryKey);

      expect(previousData).toEqual(mockItems);
      expect(currentData).toHaveLength(2);
      expect(currentData?.find((item) => item.id === '2')).toBeUndefined();
    });

    it('should handle non-existent item id gracefully', () => {
      optimisticRemoveFromList<TestItem>(queryClient, testQueryKey, 'non-existent');

      const currentData = queryClient.getQueryData<TestItem[]>(testQueryKey);

      expect(currentData).toHaveLength(3);
    });
  });

  describe('replaceOptimisticItem', () => {
    it('should replace optimistic item with real item', () => {
      const optimisticId = 'temp-123';
      const optimisticItem: TestItem = { id: optimisticId, name: 'Optimistic', status: 'pending' };
      const realItem: TestItem = { id: 'real-456', name: 'Real', status: 'active' };

      // Add optimistic item
      optimisticAddToList(queryClient, testQueryKey, optimisticItem);

      // Replace with real item
      replaceOptimisticItem(queryClient, testQueryKey, optimisticId, realItem);

      const currentData = queryClient.getQueryData<TestItem[]>(testQueryKey);

      expect(currentData?.find((item) => item.id === optimisticId)).toBeUndefined();
      expect(currentData?.find((item) => item.id === 'real-456')).toEqual(realItem);
    });

    it('should add item to empty list', () => {
      const emptyQueryKey = ['test', 'empty'];
      const realItem: TestItem = { id: 'real-456', name: 'Real', status: 'active' };

      replaceOptimisticItem(queryClient, emptyQueryKey, 'any-id', realItem);

      const currentData = queryClient.getQueryData<TestItem[]>(emptyQueryKey);

      expect(currentData).toEqual([realItem]);
    });
  });

  // ============================================================================
  // Single Item Operation Helpers
  // ============================================================================

  describe('optimisticUpdateSingle', () => {
    const singleQueryKey = ['test', 'single'];
    const mockSingleItem = { id: '1', name: 'Single Item', status: 'active' };

    beforeEach(() => {
      queryClient.setQueryData(singleQueryKey, mockSingleItem);
    });

    it('should update single cached item', () => {
      const previousData = optimisticUpdateSingle<typeof mockSingleItem>(
        queryClient,
        singleQueryKey,
        { status: 'updated' }
      );

      const currentData = queryClient.getQueryData(singleQueryKey);

      expect(previousData).toEqual(mockSingleItem);
      expect(currentData).toEqual({ ...mockSingleItem, status: 'updated' });
    });

    it('should preserve unmodified properties', () => {
      optimisticUpdateSingle(queryClient, singleQueryKey, { status: 'updated' });

      const currentData = queryClient.getQueryData<typeof mockSingleItem>(singleQueryKey);

      expect(currentData?.name).toBe('Single Item');
      expect(currentData?.id).toBe('1');
    });
  });

  // ============================================================================
  // Rollback Helpers
  // ============================================================================

  describe('rollbackList', () => {
    it('should restore list to previous state', () => {
      const previousData = [...mockItems];

      // Modify the list
      optimisticRemoveFromList<TestItem>(queryClient, testQueryKey, '1');

      // Rollback
      rollbackList(queryClient, testQueryKey, previousData);

      const currentData = queryClient.getQueryData<TestItem[]>(testQueryKey);

      expect(currentData).toEqual(previousData);
    });

    it('should do nothing if previous data is undefined', () => {
      rollbackList(queryClient, testQueryKey, undefined);

      const currentData = queryClient.getQueryData<TestItem[]>(testQueryKey);

      expect(currentData).toEqual(mockItems);
    });
  });

  describe('rollbackSingle', () => {
    const singleQueryKey = ['test', 'single'];
    const mockSingleItem = { id: '1', name: 'Single', status: 'active' };

    beforeEach(() => {
      queryClient.setQueryData(singleQueryKey, mockSingleItem);
    });

    it('should restore single item to previous state', () => {
      const previousData = { ...mockSingleItem };

      // Modify the item
      optimisticUpdateSingle(queryClient, singleQueryKey, { status: 'modified' });

      // Rollback
      rollbackSingle(queryClient, singleQueryKey, previousData);

      const currentData = queryClient.getQueryData(singleQueryKey);

      expect(currentData).toEqual(previousData);
    });
  });

  // ============================================================================
  // Mutation Lifecycle Helpers
  // ============================================================================

  describe('cancelOutgoingQueries', () => {
    it('should cancel queries for the given key', async () => {
      const cancelQueriesSpy = vi.spyOn(queryClient, 'cancelQueries');

      await cancelOutgoingQueries(queryClient, testQueryKey);

      expect(cancelQueriesSpy).toHaveBeenCalledWith({ queryKey: testQueryKey });
    });
  });

  describe('invalidateQueries', () => {
    it('should invalidate all provided query keys', () => {
      const invalidateQueriesSpy = vi.spyOn(queryClient, 'invalidateQueries');
      const queryKeys = [['key1'], ['key2'], ['key3']];

      invalidateQueries(queryClient, queryKeys);

      expect(invalidateQueriesSpy).toHaveBeenCalledTimes(3);
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({ queryKey: ['key1'] });
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({ queryKey: ['key2'] });
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({ queryKey: ['key3'] });
    });
  });

  // ============================================================================
  // Typed Mutation Config Factories
  // ============================================================================

  describe('createOptimisticAddConfig', () => {
    interface CreateVariables {
      name: string;
      status: string;
    }

    it('should create valid mutation config', () => {
      const config = createOptimisticAddConfig<TestItem, CreateVariables>(
        queryClient,
        testQueryKey,
        (vars) => ({
          id: `temp-${Date.now()}`,
          name: vars.name,
          status: vars.status,
        })
      );

      expect(config).toHaveProperty('onMutate');
      expect(config).toHaveProperty('onError');
      expect(config).toHaveProperty('onSuccess');
      expect(config).toHaveProperty('onSettled');
    });

    it('should optimistically add item in onMutate', async () => {
      const config = createOptimisticAddConfig<TestItem, CreateVariables>(
        queryClient,
        testQueryKey,
        (vars) => ({
          id: 'temp-123',
          name: vars.name,
          status: vars.status,
        })
      );

      const context = await config.onMutate({ name: 'New Item', status: 'pending' });

      const currentData = queryClient.getQueryData<TestItem[]>(testQueryKey);

      expect(context?.previousData).toEqual(mockItems);
      expect(context?.optimisticId).toBe('temp-123');
      expect(currentData).toHaveLength(4);
    });

    it('should rollback on error', async () => {
      const config = createOptimisticAddConfig<TestItem, CreateVariables>(
        queryClient,
        testQueryKey,
        (vars) => ({
          id: 'temp-123',
          name: vars.name,
          status: vars.status,
        })
      );

      const context = await config.onMutate({ name: 'New Item', status: 'pending' });
      config.onError(new Error('Test error'), { name: 'New Item', status: 'pending' }, context);

      const currentData = queryClient.getQueryData<TestItem[]>(testQueryKey);

      expect(currentData).toEqual(mockItems);
    });
  });

  describe('createOptimisticUpdateConfig', () => {
    interface UpdateVariables {
      id: string;
      name: string;
    }

    it('should create valid mutation config', () => {
      const config = createOptimisticUpdateConfig<TestItem, UpdateVariables>(
        queryClient,
        testQueryKey,
        (vars) => vars.id,
        (vars) => ({ name: vars.name })
      );

      expect(config).toHaveProperty('onMutate');
      expect(config).toHaveProperty('onError');
      expect(config).toHaveProperty('onSettled');
    });

    it('should optimistically update item in onMutate', async () => {
      const config = createOptimisticUpdateConfig<TestItem, UpdateVariables>(
        queryClient,
        testQueryKey,
        (vars) => vars.id,
        (vars) => ({ name: vars.name })
      );

      await config.onMutate({ id: '2', name: 'Updated Name' });

      const currentData = queryClient.getQueryData<TestItem[]>(testQueryKey);

      expect(currentData?.[1].name).toBe('Updated Name');
    });
  });

  describe('createOptimisticDeleteConfig', () => {
    interface DeleteVariables {
      id: string;
    }

    it('should create valid mutation config', () => {
      const config = createOptimisticDeleteConfig<TestItem, DeleteVariables>(
        queryClient,
        testQueryKey,
        (vars) => vars.id
      );

      expect(config).toHaveProperty('onMutate');
      expect(config).toHaveProperty('onError');
      expect(config).toHaveProperty('onSettled');
    });

    it('should optimistically remove item in onMutate', async () => {
      const config = createOptimisticDeleteConfig<TestItem, DeleteVariables>(
        queryClient,
        testQueryKey,
        (vars) => vars.id
      );

      await config.onMutate({ id: '2' });

      const currentData = queryClient.getQueryData<TestItem[]>(testQueryKey);

      expect(currentData).toHaveLength(2);
      expect(currentData?.find((item) => item.id === '2')).toBeUndefined();
    });

    it('should remove detail query on settled when getDetailQueryKey provided', () => {
      const removeQueriesSpy = vi.spyOn(queryClient, 'removeQueries');
      const getDetailQueryKey = (id: string | number) => ['test', 'detail', id] as const;

      const config = createOptimisticDeleteConfig<TestItem, DeleteVariables>(
        queryClient,
        testQueryKey,
        (vars) => vars.id,
        getDetailQueryKey
      );

      config.onSettled(undefined, null, { id: '2' });

      expect(removeQueriesSpy).toHaveBeenCalledWith({ queryKey: ['test', 'detail', '2'] });
    });
  });
});
