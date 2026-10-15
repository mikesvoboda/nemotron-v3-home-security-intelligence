/**
 * Tests for useLocalStorage hook
 */

import { renderHook, act } from '@testing-library/react';
import { describe, expect, it, beforeEach, vi } from 'vitest';

// Direct import to avoid barrel file memory issues
import { useLocalStorage } from './useLocalStorage';

describe('useLocalStorage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
  });

  it('returns initial value when localStorage is empty', () => {
    const { result } = renderHook(() => useLocalStorage('test-key', 'initial'));

    expect(result.current[0]).toBe('initial');
  });

  it('returns stored value from localStorage', () => {
    window.localStorage.setItem('test-key', JSON.stringify('stored-value'));

    const { result } = renderHook(() => useLocalStorage('test-key', 'initial'));

    expect(result.current[0]).toBe('stored-value');
  });

  it('updates state and localStorage when setValue is called', () => {
    const { result } = renderHook(() => useLocalStorage('test-key', 'initial'));

    act(() => {
      result.current[1]('new-value');
    });

    expect(result.current[0]).toBe('new-value');
    expect(window.localStorage.getItem('test-key')).toBe(JSON.stringify('new-value'));
  });

  it('supports functional updates', () => {
    const { result } = renderHook(() => useLocalStorage('counter', 0));

    act(() => {
      result.current[1]((prev) => prev + 1);
    });

    expect(result.current[0]).toBe(1);
  });

  it('handles boolean values for showTips preference', () => {
    const { result } = renderHook(() => useLocalStorage('promptPlayground.showTips', true));

    expect(result.current[0]).toBe(true);

    act(() => {
      result.current[1](false);
    });

    expect(result.current[0]).toBe(false);
    expect(window.localStorage.getItem('promptPlayground.showTips')).toBe(JSON.stringify(false));
  });

  // F-020: /settings/ambient and AmbientStatusProvider each called useSettings(),
  // so two instances shared the jar but not the value — the toggle flipped and the
  // tint never followed until a reload. These pin the shared hook itself, because
  // the golden spec (frontend/tests/golden/shell/ambient.spec.ts) can only show
  // the symptom 3 layers up and takes minutes; this is the contract.
  describe('instances that share a key (F-020)', () => {
    it('a sibling instance in the same tree follows a write with no remount', () => {
      const { result: writer, unmount: unA } = renderHook(() =>
        useLocalStorage('shared-key', { enabled: true })
      );
      const { result: reader, unmount: unB } = renderHook(() =>
        useLocalStorage('shared-key', { enabled: true })
      );

      act(() => {
        writer.current[1]({ enabled: false });
      });

      expect(writer.current[0]).toEqual({ enabled: false });
      // This is the assertion that used to fail: the reader had its own useState.
      expect(reader.current[0]).toEqual({ enabled: false });

      unA();
      unB();
    });

    it('a functional update reads the sibling value, not its own stale copy', () => {
      const { result: a, unmount: unA } = renderHook(() => useLocalStorage('counter-key', 0));
      const { result: b, unmount: unB } = renderHook(() => useLocalStorage('counter-key', 0));

      act(() => {
        a.current[1]((p) => p + 5);
      });
      // If b computed from its own mount-time copy this yields 1; from the shared
      // value it yields 6. Only the second is correct.
      act(() => {
        b.current[1]((p) => p + 1);
      });

      expect(b.current[0]).toBe(6);
      expect(a.current[0]).toBe(6);
      expect(JSON.parse(window.localStorage.getItem('counter-key') ?? 'null')).toBe(6);

      unA();
      unB();
    });

    it('does not cross keys', () => {
      const { result: k1, unmount: unA } = renderHook(() => useLocalStorage('key-one', 'a'));
      const { result: k2, unmount: unB } = renderHook(() => useLocalStorage('key-two', 'b'));

      act(() => {
        k1.current[1]('changed');
      });

      expect(k1.current[0]).toBe('changed');
      expect(k2.current[0]).toBe('b');

      unA();
      unB();
    });

    it('follows a write from ANOTHER document (storage event)', () => {
      const { result, unmount } = renderHook(() => useLocalStorage('other-doc-key', 'mine'));

      act(() => {
        // A real cross-document write has ALREADY landed in the shared jar by the
        // time its storage event is delivered (verified on the app origin: the
        // sibling document receives the event, the writer does not). The handler
        // re-reads the jar instead of trusting event.newValue, so the write is
        // part of the simulation — dispatchEvent alone stands in for the OTHER
        // document's notification, since jsdom has no second document and its
        // StorageEvent does not mutate storage.
        window.localStorage.setItem('other-doc-key', JSON.stringify('theirs'));
        window.dispatchEvent(
          new StorageEvent('storage', {
            key: 'other-doc-key',
            newValue: JSON.stringify('theirs'),
            storageArea: window.localStorage,
          })
        );
      });

      expect(result.current[0]).toBe('theirs');
      unmount();
    });

    it('ignores a storage event for an unrelated key', () => {
      const { result, unmount } = renderHook(() => useLocalStorage('my-key', 'keep'));

      act(() => {
        window.dispatchEvent(
          new StorageEvent('storage', {
            key: 'someone-elses-key',
            newValue: JSON.stringify('noise'),
            storageArea: window.localStorage,
          })
        );
      });

      expect(result.current[0]).toBe('keep');
      unmount();
    });
  });
});
