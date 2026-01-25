/* eslint-disable @typescript-eslint/unbound-method */
import { renderHook, act } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import { useInteractionTracking } from './useInteractionTracking';

import { logger } from '@/services/logger';

// Mock the logger
vi.mock('@/services/logger', () => ({
  logger: {
    interaction: vi.fn(),
    formSubmit: vi.fn(),
  },
}));

describe('useInteractionTracking', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('trackClick', () => {
    it('logs click interactions with component prefix', () => {
      const { result } = renderHook(() => useInteractionTracking('TestComponent'));

      act(() => {
        result.current.trackClick('save_button');
      });

      expect(logger.interaction).toHaveBeenCalledWith(
        'click',
        'TestComponent.save_button',
        undefined
      );
    });

    it('includes extra data when provided', () => {
      const { result } = renderHook(() => useInteractionTracking('AlertForm'));

      act(() => {
        result.current.trackClick('severity_button', { value: 'high' });
      });

      expect(logger.interaction).toHaveBeenCalledWith('click', 'AlertForm.severity_button', {
        value: 'high',
      });
    });

    it('is memoized based on component name', () => {
      const { result, rerender } = renderHook(({ name }) => useInteractionTracking(name), {
        initialProps: { name: 'Component1' },
      });

      const firstTrackClick = result.current.trackClick;

      // Rerender with same name
      rerender({ name: 'Component1' });
      expect(result.current.trackClick).toBe(firstTrackClick);

      // Rerender with different name
      rerender({ name: 'Component2' });
      expect(result.current.trackClick).not.toBe(firstTrackClick);
    });
  });

  describe('trackChange', () => {
    it('logs change interactions with component prefix', () => {
      const { result } = renderHook(() => useInteractionTracking('SettingsForm'));

      act(() => {
        result.current.trackChange('theme_select');
      });

      expect(logger.interaction).toHaveBeenCalledWith(
        'change',
        'SettingsForm.theme_select',
        undefined
      );
    });

    it('includes extra data when provided', () => {
      const { result } = renderHook(() => useInteractionTracking('FilterPanel'));

      act(() => {
        result.current.trackChange('date_range', { from: '2024-01-01', to: '2024-01-31' });
      });

      expect(logger.interaction).toHaveBeenCalledWith('change', 'FilterPanel.date_range', {
        from: '2024-01-01',
        to: '2024-01-31',
      });
    });
  });

  describe('trackSubmit', () => {
    it('logs successful form submissions', () => {
      const { result } = renderHook(() => useInteractionTracking('AlertForm'));

      act(() => {
        result.current.trackSubmit(true, { alert_type: 'intrusion' });
      });

      expect(logger.formSubmit).toHaveBeenCalledWith('AlertForm', true, {
        alert_type: 'intrusion',
      });
    });

    it('logs failed form submissions', () => {
      const { result } = renderHook(() => useInteractionTracking('AlertForm'));

      act(() => {
        result.current.trackSubmit(false, { validation_errors: ['name'] });
      });

      expect(logger.formSubmit).toHaveBeenCalledWith('AlertForm', false, {
        validation_errors: ['name'],
      });
    });

    it('works without extra data', () => {
      const { result } = renderHook(() => useInteractionTracking('ContactForm'));

      act(() => {
        result.current.trackSubmit(true);
      });

      expect(logger.formSubmit).toHaveBeenCalledWith('ContactForm', true, undefined);
    });
  });

  describe('trackOpen', () => {
    it('logs modal open interactions', () => {
      const { result } = renderHook(() => useInteractionTracking('AlertsPage'));

      act(() => {
        result.current.trackOpen('create_alert_modal');
      });

      expect(logger.interaction).toHaveBeenCalledWith(
        'open',
        'AlertsPage.create_alert_modal',
        undefined
      );
    });

    it('includes extra data when provided', () => {
      const { result } = renderHook(() => useInteractionTracking('EventTimeline'));

      act(() => {
        result.current.trackOpen('event_details', { event_id: '123' });
      });

      expect(logger.interaction).toHaveBeenCalledWith('open', 'EventTimeline.event_details', {
        event_id: '123',
      });
    });
  });

  describe('trackClose', () => {
    it('logs modal close interactions', () => {
      const { result } = renderHook(() => useInteractionTracking('AlertsPage'));

      act(() => {
        result.current.trackClose('create_alert_modal');
      });

      expect(logger.interaction).toHaveBeenCalledWith(
        'close',
        'AlertsPage.create_alert_modal',
        undefined
      );
    });

    it('includes extra data when provided', () => {
      const { result } = renderHook(() => useInteractionTracking('SettingsPage'));

      act(() => {
        result.current.trackClose('confirm_dialog', { confirmed: false });
      });

      expect(logger.interaction).toHaveBeenCalledWith('close', 'SettingsPage.confirm_dialog', {
        confirmed: false,
      });
    });
  });

  describe('trackToggle', () => {
    it('logs toggle interactions with enabled state', () => {
      const { result } = renderHook(() => useInteractionTracking('AlertForm'));

      act(() => {
        result.current.trackToggle('enabled', true);
      });

      expect(logger.interaction).toHaveBeenCalledWith('toggle', 'AlertForm.enabled', {
        enabled: true,
      });
    });

    it('logs toggle interactions when disabled', () => {
      const { result } = renderHook(() => useInteractionTracking('AlertForm'));

      act(() => {
        result.current.trackToggle('schedule_enabled', false);
      });

      expect(logger.interaction).toHaveBeenCalledWith('toggle', 'AlertForm.schedule_enabled', {
        enabled: false,
      });
    });

    it('includes extra data when provided', () => {
      const { result } = renderHook(() => useInteractionTracking('NotificationSettings'));

      act(() => {
        result.current.trackToggle('email_notifications', true, { channel: 'email' });
      });

      expect(logger.interaction).toHaveBeenCalledWith(
        'toggle',
        'NotificationSettings.email_notifications',
        {
          enabled: true,
          channel: 'email',
        }
      );
    });
  });

  describe('hook stability', () => {
    it('returns stable references when component name is unchanged', () => {
      const { result, rerender } = renderHook(() => useInteractionTracking('StableComponent'));

      const {
        trackClick: click1,
        trackChange: change1,
        trackSubmit: submit1,
        trackOpen: open1,
        trackClose: close1,
        trackToggle: toggle1,
      } = result.current;

      // Rerender without changing props
      rerender();

      expect(result.current.trackClick).toBe(click1);
      expect(result.current.trackChange).toBe(change1);
      expect(result.current.trackSubmit).toBe(submit1);
      expect(result.current.trackOpen).toBe(open1);
      expect(result.current.trackClose).toBe(close1);
      expect(result.current.trackToggle).toBe(toggle1);
    });
  });
});
