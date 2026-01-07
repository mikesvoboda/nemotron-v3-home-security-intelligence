/**
 * useToast - Hook tests for toast notification system
 *
 * TDD RED Phase: These tests define the expected API and behavior
 * before implementing the hook.
 */

import { renderHook, act } from '@testing-library/react';
import { toast as sonnerToast } from 'sonner';
import { describe, it, expect, vi, beforeEach, afterEach, type Mock } from 'vitest';

import { useToast, type ToastAction } from './useToast';

// Mock sonner
vi.mock('sonner', () => ({
  toast: Object.assign(vi.fn(), {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
    loading: vi.fn(),
    dismiss: vi.fn(),
    promise: vi.fn(),
  }),
}));

describe('useToast', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('basic toast methods', () => {
    it('should expose success, error, warning, info, loading, and dismiss methods', () => {
      const { result } = renderHook(() => useToast());

      expect(result.current.success).toBeInstanceOf(Function);
      expect(result.current.error).toBeInstanceOf(Function);
      expect(result.current.warning).toBeInstanceOf(Function);
      expect(result.current.info).toBeInstanceOf(Function);
      expect(result.current.loading).toBeInstanceOf(Function);
      expect(result.current.dismiss).toBeInstanceOf(Function);
      expect(result.current.promise).toBeInstanceOf(Function);
    });

    it('should call sonner toast.success with message', () => {
      const { result } = renderHook(() => useToast());

      act(() => {
        result.current.success('Operation completed');
      });

      expect(sonnerToast.success).toHaveBeenCalledWith('Operation completed', expect.any(Object));
    });

    it('should call sonner toast.error with message', () => {
      const { result } = renderHook(() => useToast());

      act(() => {
        result.current.error('Something went wrong');
      });

      expect(sonnerToast.error).toHaveBeenCalledWith('Something went wrong', expect.any(Object));
    });

    it('should call sonner toast.warning with message', () => {
      const { result } = renderHook(() => useToast());

      act(() => {
        result.current.warning('Please check your input');
      });

      expect(sonnerToast.warning).toHaveBeenCalledWith('Please check your input', expect.any(Object));
    });

    it('should call sonner toast.info with message', () => {
      const { result } = renderHook(() => useToast());

      act(() => {
        result.current.info('New update available');
      });

      expect(sonnerToast.info).toHaveBeenCalledWith('New update available', expect.any(Object));
    });

    it('should call sonner toast.loading with message', () => {
      const { result } = renderHook(() => useToast());

      act(() => {
        result.current.loading('Processing...');
      });

      expect(sonnerToast.loading).toHaveBeenCalledWith('Processing...', expect.any(Object));
    });

    it('should call sonner toast.dismiss with toast id', () => {
      const { result } = renderHook(() => useToast());

      act(() => {
        result.current.dismiss('toast-123');
      });

      expect(sonnerToast.dismiss).toHaveBeenCalledWith('toast-123');
    });

    it('should call sonner toast.dismiss without id to dismiss all', () => {
      const { result } = renderHook(() => useToast());

      act(() => {
        result.current.dismiss();
      });

      expect(sonnerToast.dismiss).toHaveBeenCalledWith(undefined);
    });
  });

  describe('toast options', () => {
    it('should pass description option to sonner', () => {
      const { result } = renderHook(() => useToast());

      act(() => {
        result.current.success('Settings saved', {
          description: 'Your preferences have been updated',
        });
      });

      expect(sonnerToast.success).toHaveBeenCalledWith(
        'Settings saved',
        expect.objectContaining({
          description: 'Your preferences have been updated',
        })
      );
    });

    it('should pass duration option to sonner', () => {
      const { result } = renderHook(() => useToast());

      act(() => {
        result.current.error('Connection lost', {
          duration: 10000,
        });
      });

      expect(sonnerToast.error).toHaveBeenCalledWith(
        'Connection lost',
        expect.objectContaining({
          duration: 10000,
        })
      );
    });

    it('should pass id option to sonner for deduplication', () => {
      const { result } = renderHook(() => useToast());

      act(() => {
        result.current.info('Sync in progress', {
          id: 'sync-toast',
        });
      });

      expect(sonnerToast.info).toHaveBeenCalledWith(
        'Sync in progress',
        expect.objectContaining({
          id: 'sync-toast',
        })
      );
    });

    it('should set Infinity duration when dismissible is false', () => {
      const { result } = renderHook(() => useToast());

      act(() => {
        result.current.warning('Critical alert', {
          dismissible: false,
        });
      });

      expect(sonnerToast.warning).toHaveBeenCalledWith(
        'Critical alert',
        expect.objectContaining({
          duration: Infinity,
        })
      );
    });

    it('should pass onDismiss callback to sonner', () => {
      const { result } = renderHook(() => useToast());
      const onDismiss = vi.fn();

      act(() => {
        result.current.success('Task completed', {
          onDismiss,
        });
      });

      expect(sonnerToast.success).toHaveBeenCalledWith(
        'Task completed',
        expect.objectContaining({
          onDismiss: expect.any(Function),
        })
      );
    });

    it('should pass onAutoClose callback to sonner', () => {
      const { result } = renderHook(() => useToast());
      const onAutoClose = vi.fn();

      act(() => {
        result.current.info('Info message', {
          onAutoClose,
        });
      });

      expect(sonnerToast.info).toHaveBeenCalledWith(
        'Info message',
        expect.objectContaining({
          onAutoClose: expect.any(Function),
        })
      );
    });
  });

  describe('toast with action buttons', () => {
    it('should pass single action to sonner', () => {
      const { result } = renderHook(() => useToast());
      const onAction = vi.fn();

      const action: ToastAction = {
        label: 'Undo',
        onClick: onAction,
      };

      act(() => {
        result.current.success('Item deleted', {
          action,
        });
      });

      expect(sonnerToast.success).toHaveBeenCalledWith(
        'Item deleted',
        expect.objectContaining({
          action: expect.any(Object),
        })
      );
    });

    it('should pass cancel action to sonner', () => {
      const { result } = renderHook(() => useToast());
      const onCancel = vi.fn();

      const cancel: ToastAction = {
        label: 'Cancel',
        onClick: onCancel,
      };

      act(() => {
        result.current.warning('About to delete', {
          cancel,
        });
      });

      expect(sonnerToast.warning).toHaveBeenCalledWith(
        'About to delete',
        expect.objectContaining({
          cancel: expect.any(Object),
        })
      );
    });

    it('should handle action with variant styling', () => {
      const { result } = renderHook(() => useToast());
      const onAction = vi.fn();

      const action: ToastAction = {
        label: 'Retry',
        onClick: onAction,
        variant: 'primary',
      };

      act(() => {
        result.current.error('Upload failed', {
          action,
        });
      });

      expect(sonnerToast.error).toHaveBeenCalledWith(
        'Upload failed',
        expect.objectContaining({
          action: expect.objectContaining({
            label: 'Retry',
          }),
        })
      );
    });
  });

  describe('promise toast', () => {
    it('should call sonner toast.promise with promise and messages', () => {
      const { result } = renderHook(() => useToast());
      const mockPromise = Promise.resolve({ data: 'test' });

      act(() => {
        void result.current.promise(mockPromise, {
          loading: 'Saving...',
          success: 'Saved!',
          error: 'Failed to save',
        });
      });

      expect(sonnerToast.promise).toHaveBeenCalledWith(
        mockPromise,
        expect.objectContaining({
          loading: 'Saving...',
          success: 'Saved!',
          error: 'Failed to save',
        })
      );
    });

    it('should support function messages for promise toast', () => {
      const { result } = renderHook(() => useToast());
      const mockPromise = Promise.resolve({ name: 'test-file.txt' });

      act(() => {
        void result.current.promise(mockPromise, {
          loading: 'Uploading file...',
          success: (data) => `Uploaded ${(data as { name: string }).name}`,
          error: (err) => `Failed: ${(err as Error).message}`,
        });
      });

      expect(sonnerToast.promise).toHaveBeenCalledWith(
        mockPromise,
        expect.objectContaining({
          loading: 'Uploading file...',
          success: expect.any(Function),
          error: expect.any(Function),
        })
      );
    });
  });

  describe('default configuration', () => {
    it('should use default duration of 4000ms for regular toasts', () => {
      const { result } = renderHook(() => useToast());

      act(() => {
        result.current.info('Default duration toast');
      });

      expect(sonnerToast.info).toHaveBeenCalledWith(
        'Default duration toast',
        expect.objectContaining({
          duration: 4000,
        })
      );
    });

    it('should use default duration of 8000ms for error toasts', () => {
      const { result } = renderHook(() => useToast());

      act(() => {
        result.current.error('Error toast with longer duration');
      });

      expect(sonnerToast.error).toHaveBeenCalledWith(
        'Error toast with longer duration',
        expect.objectContaining({
          duration: 8000,
        })
      );
    });

    it('should allow overriding default durations', () => {
      const { result } = renderHook(() => useToast());

      act(() => {
        result.current.error('Custom duration error', {
          duration: 3000,
        });
      });

      expect(sonnerToast.error).toHaveBeenCalledWith(
        'Custom duration error',
        expect.objectContaining({
          duration: 3000,
        })
      );
    });
  });

  describe('return toast id', () => {
    it('should return toast id from success', () => {
      (sonnerToast.success as Mock).mockReturnValue('toast-1');
      const { result } = renderHook(() => useToast());

      let toastId: string | number | undefined;
      act(() => {
        toastId = result.current.success('Test');
      });

      expect(toastId).toBe('toast-1');
    });

    it('should return toast id from error', () => {
      (sonnerToast.error as Mock).mockReturnValue('toast-2');
      const { result } = renderHook(() => useToast());

      let toastId: string | number | undefined;
      act(() => {
        toastId = result.current.error('Test error');
      });

      expect(toastId).toBe('toast-2');
    });

    it('should return toast id from loading', () => {
      (sonnerToast.loading as Mock).mockReturnValue('toast-3');
      const { result } = renderHook(() => useToast());

      let toastId: string | number | undefined;
      act(() => {
        toastId = result.current.loading('Loading...');
      });

      expect(toastId).toBe('toast-3');
    });
  });

  describe('hook stability', () => {
    it('should return stable function references', () => {
      const { result, rerender } = renderHook(() => useToast());

      const {
        success: success1,
        error: error1,
        warning: warning1,
        info: info1,
        loading: loading1,
        dismiss: dismiss1,
        promise: promise1,
      } = result.current;

      rerender();

      expect(result.current.success).toBe(success1);
      expect(result.current.error).toBe(error1);
      expect(result.current.warning).toBe(warning1);
      expect(result.current.info).toBe(info1);
      expect(result.current.loading).toBe(loading1);
      expect(result.current.dismiss).toBe(dismiss1);
      expect(result.current.promise).toBe(promise1);
    });
  });
});
