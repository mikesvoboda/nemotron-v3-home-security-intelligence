/**
 * Tests for WebSocket event sequence validation.
 *
 * NEM-2019: Implement WebSocket event sequence validation
 *
 * Acceptance Criteria:
 * - Events include sequence numbers
 * - Frontend tracks sequence per channel
 * - Out-of-order events buffered and reordered
 * - Large gaps trigger resync request
 * - Duplicate events ignored
 */

import { describe, it, expect, beforeEach, vi, type Mock } from 'vitest';

import {
  SequenceValidator,
  type SequencedMessage,
  DEFAULT_SEQUENCE_CONFIG,
} from './sequenceValidator';

describe('SequenceValidator', () => {
  let validator: SequenceValidator;
  let resyncCallback: Mock;

  beforeEach(() => {
    resyncCallback = vi.fn();
    validator = new SequenceValidator(resyncCallback);
  });

  describe('initialization', () => {
    it('should initialize with default state for a new channel', () => {
      const state = validator.getState('events');
      expect(state.lastSequence).toBe(0);
      expect(state.buffer.size).toBe(0);
    });

    it('should track multiple channels independently', () => {
      validator.handleMessage('events', {
        type: 'event',
        sequence: 1,
        data: {},
      } as SequencedMessage);
      validator.handleMessage('system', {
        type: 'system_status',
        sequence: 1,
        data: {},
      } as SequencedMessage);

      expect(validator.getState('events').lastSequence).toBe(1);
      expect(validator.getState('system').lastSequence).toBe(1);
    });

    it('should accept custom configuration', () => {
      const customValidator = new SequenceValidator(resyncCallback, {
        maxBufferSize: 50,
        gapThreshold: 20,
        bufferTimeout: 10000,
      });
      expect(customValidator).toBeDefined();
    });
  });

  describe('in-order message processing', () => {
    it('should accept first message with sequence 1', () => {
      const message: SequencedMessage = { type: 'event', sequence: 1, data: { id: 1 } };
      const result = validator.handleMessage('events', message);

      expect(result.processed).toEqual([message]);
      expect(result.buffered).toEqual([]);
      expect(result.duplicates).toEqual([]);
      expect(validator.getState('events').lastSequence).toBe(1);
    });

    it('should accept consecutive in-order messages', () => {
      const msg1: SequencedMessage = { type: 'event', sequence: 1, data: { id: 1 } };
      const msg2: SequencedMessage = { type: 'event', sequence: 2, data: { id: 2 } };
      const msg3: SequencedMessage = { type: 'event', sequence: 3, data: { id: 3 } };

      validator.handleMessage('events', msg1);
      validator.handleMessage('events', msg2);
      const result = validator.handleMessage('events', msg3);

      expect(result.processed).toEqual([msg3]);
      expect(validator.getState('events').lastSequence).toBe(3);
    });

    it('should update lastSequence correctly for each processed message', () => {
      for (let i = 1; i <= 10; i++) {
        validator.handleMessage('events', {
          type: 'event',
          sequence: i,
          data: {},
        } as SequencedMessage);
        expect(validator.getState('events').lastSequence).toBe(i);
      }
    });
  });

  describe('out-of-order event buffering', () => {
    it('should buffer a future event when gap is within threshold', () => {
      const msg1: SequencedMessage = { type: 'event', sequence: 1, data: { id: 1 } };
      const msg3: SequencedMessage = { type: 'event', sequence: 3, data: { id: 3 } };

      validator.handleMessage('events', msg1);
      const result = validator.handleMessage('events', msg3);

      expect(result.processed).toEqual([]);
      expect(result.buffered).toEqual([msg3]);
      expect(validator.getState('events').buffer.size).toBe(1);
    });

    it('should process buffered events when gap is filled', () => {
      const msg1: SequencedMessage = { type: 'event', sequence: 1, data: { id: 1 } };
      const msg3: SequencedMessage = { type: 'event', sequence: 3, data: { id: 3 } };
      const msg2: SequencedMessage = { type: 'event', sequence: 2, data: { id: 2 } };

      validator.handleMessage('events', msg1);
      validator.handleMessage('events', msg3);
      const result = validator.handleMessage('events', msg2);

      // Should process msg2 (the gap filler) and then msg3 (from buffer)
      expect(result.processed).toEqual([msg2, msg3]);
      expect(validator.getState('events').lastSequence).toBe(3);
      expect(validator.getState('events').buffer.size).toBe(0);
    });

    it('should process multiple buffered events in order', () => {
      const msg1: SequencedMessage = { type: 'event', sequence: 1, data: { id: 1 } };
      const msg4: SequencedMessage = { type: 'event', sequence: 4, data: { id: 4 } };
      const msg5: SequencedMessage = { type: 'event', sequence: 5, data: { id: 5 } };
      const msg3: SequencedMessage = { type: 'event', sequence: 3, data: { id: 3 } };
      const msg2: SequencedMessage = { type: 'event', sequence: 2, data: { id: 2 } };

      validator.handleMessage('events', msg1);
      validator.handleMessage('events', msg4);
      validator.handleMessage('events', msg5);
      validator.handleMessage('events', msg3);
      const result = validator.handleMessage('events', msg2);

      // Should process in order: msg2, msg3, msg4, msg5
      expect(result.processed).toEqual([msg2, msg3, msg4, msg5]);
      expect(validator.getState('events').lastSequence).toBe(5);
    });

    it('should maintain buffer sorted by sequence', () => {
      const msg1: SequencedMessage = { type: 'event', sequence: 1, data: { id: 1 } };
      validator.handleMessage('events', msg1);

      // Add out-of-order to buffer
      validator.handleMessage('events', {
        type: 'event',
        sequence: 5,
        data: {},
      } as SequencedMessage);
      validator.handleMessage('events', {
        type: 'event',
        sequence: 3,
        data: {},
      } as SequencedMessage);
      validator.handleMessage('events', {
        type: 'event',
        sequence: 4,
        data: {},
      } as SequencedMessage);

      const buffer = validator.getState('events').buffer;
      const sequences = Array.from(buffer.keys()).sort((a, b) => a - b);
      expect(sequences).toEqual([3, 4, 5]);
    });
  });

  describe('duplicate event filtering', () => {
    it('should ignore duplicate sequence numbers', () => {
      const msg1: SequencedMessage = { type: 'event', sequence: 1, data: { id: 1 } };
      const msg1Dup: SequencedMessage = {
        type: 'event',
        sequence: 1,
        data: { id: 1, extra: 'dup' },
      };

      validator.handleMessage('events', msg1);
      const result = validator.handleMessage('events', msg1Dup);

      expect(result.processed).toEqual([]);
      expect(result.duplicates).toEqual([msg1Dup]);
      expect(validator.getState('events').lastSequence).toBe(1);
    });

    it('should ignore older sequence numbers', () => {
      const msg1: SequencedMessage = { type: 'event', sequence: 1, data: { id: 1 } };
      const msg2: SequencedMessage = { type: 'event', sequence: 2, data: { id: 2 } };
      const msgOld: SequencedMessage = { type: 'event', sequence: 1, data: { id: 1 } };

      validator.handleMessage('events', msg1);
      validator.handleMessage('events', msg2);
      const result = validator.handleMessage('events', msgOld);

      expect(result.processed).toEqual([]);
      expect(result.duplicates).toEqual([msgOld]);
      expect(validator.getState('events').lastSequence).toBe(2);
    });

    it('should not add duplicate to buffer', () => {
      const msg1: SequencedMessage = { type: 'event', sequence: 1, data: { id: 1 } };
      const msg3: SequencedMessage = { type: 'event', sequence: 3, data: { id: 3 } };
      const msg3Dup: SequencedMessage = {
        type: 'event',
        sequence: 3,
        data: { id: 3, extra: 'dup' },
      };

      validator.handleMessage('events', msg1);
      validator.handleMessage('events', msg3);
      const result = validator.handleMessage('events', msg3Dup);

      expect(result.buffered).toEqual([]);
      expect(result.duplicates).toEqual([msg3Dup]);
      expect(validator.getState('events').buffer.size).toBe(1);
    });
  });

  describe('gap detection and resync', () => {
    it('should trigger resync when gap exceeds threshold', () => {
      // NEM-3905: Default gap threshold is now 50 (was 10)
      const msg1: SequencedMessage = { type: 'event', sequence: 1, data: { id: 1 } };
      // Gap of 59 (sequence 60 - 1 = 59) exceeds threshold of 50
      const msgGap: SequencedMessage = { type: 'event', sequence: 60, data: { id: 60 } };

      validator.handleMessage('events', msg1);
      validator.handleMessage('events', msgGap);

      expect(resyncCallback).toHaveBeenCalledWith('events', 1);
    });

    it('should not trigger resync for small gaps', () => {
      const msg1: SequencedMessage = { type: 'event', sequence: 1, data: { id: 1 } };
      const msg5: SequencedMessage = { type: 'event', sequence: 5, data: { id: 5 } };

      validator.handleMessage('events', msg1);
      validator.handleMessage('events', msg5);

      expect(resyncCallback).not.toHaveBeenCalled();
    });

    it('should not trigger resync for gaps below threshold (NEM-3905)', () => {
      // NEM-3905: Verify gaps of 30-40 (previously would trigger resync at threshold 10)
      // no longer trigger resync with the new threshold of 50
      const msg1: SequencedMessage = { type: 'event', sequence: 1, data: { id: 1 } };
      // Gap of 39 (sequence 40 - 1 = 39) is below threshold of 50
      const msg40: SequencedMessage = { type: 'event', sequence: 40, data: { id: 40 } };

      validator.handleMessage('events', msg1);
      validator.handleMessage('events', msg40);

      // Should NOT trigger resync because gap (39) < threshold (50)
      expect(resyncCallback).not.toHaveBeenCalled();
    });

    it('should use custom gap threshold when configured', () => {
      const customValidator = new SequenceValidator(resyncCallback, { gapThreshold: 3 });

      const msg1: SequencedMessage = { type: 'event', sequence: 1, data: { id: 1 } };
      const msg6: SequencedMessage = { type: 'event', sequence: 6, data: { id: 6 } };

      customValidator.handleMessage('events', msg1);
      customValidator.handleMessage('events', msg6);

      expect(resyncCallback).toHaveBeenCalledWith('events', 1);
    });

    it('should still buffer message when triggering resync', () => {
      const msg1: SequencedMessage = { type: 'event', sequence: 1, data: { id: 1 } };
      // NEM-3905: Use gap > 50 to trigger resync with new threshold
      const msgGap: SequencedMessage = { type: 'event', sequence: 60, data: { id: 60 } };

      validator.handleMessage('events', msg1);
      const result = validator.handleMessage('events', msgGap);

      expect(result.buffered).toEqual([msgGap]);
      expect(resyncCallback).toHaveBeenCalled();
    });
  });

  describe('buffer management', () => {
    it('should respect maxBufferSize and drop oldest', () => {
      const customValidator = new SequenceValidator(resyncCallback, {
        maxBufferSize: 3,
        gapThreshold: 100, // High threshold to avoid resync
      });

      const msg1: SequencedMessage = { type: 'event', sequence: 1, data: { id: 1 } };
      customValidator.handleMessage('events', msg1);

      // Add more than maxBufferSize to buffer
      customValidator.handleMessage('events', {
        type: 'event',
        sequence: 3,
        data: {},
      } as SequencedMessage);
      customValidator.handleMessage('events', {
        type: 'event',
        sequence: 4,
        data: {},
      } as SequencedMessage);
      customValidator.handleMessage('events', {
        type: 'event',
        sequence: 5,
        data: {},
      } as SequencedMessage);
      customValidator.handleMessage('events', {
        type: 'event',
        sequence: 6,
        data: {},
      } as SequencedMessage);

      const buffer = customValidator.getState('events').buffer;
      expect(buffer.size).toBeLessThanOrEqual(3);
      // Oldest (seq 3) should be dropped
      expect(buffer.has(3)).toBe(false);
      expect(buffer.has(6)).toBe(true);
    });

    it('should clear buffer on reset', () => {
      const msg1: SequencedMessage = { type: 'event', sequence: 1, data: { id: 1 } };
      const msg3: SequencedMessage = { type: 'event', sequence: 3, data: { id: 3 } };

      validator.handleMessage('events', msg1);
      validator.handleMessage('events', msg3);

      validator.reset('events');

      const state = validator.getState('events');
      expect(state.lastSequence).toBe(0);
      expect(state.buffer.size).toBe(0);
    });

    it('should clear all channels on resetAll', () => {
      validator.handleMessage('events', {
        type: 'event',
        sequence: 1,
        data: {},
      } as SequencedMessage);
      validator.handleMessage('system', {
        type: 'system_status',
        sequence: 1,
        data: {},
      } as SequencedMessage);

      validator.resetAll();

      expect(validator.getState('events').lastSequence).toBe(0);
      expect(validator.getState('system').lastSequence).toBe(0);
    });
  });

  describe('message without sequence', () => {
    it('should pass through messages without sequence number', () => {
      const message = { type: 'ping' } as unknown as SequencedMessage;
      const result = validator.handleMessage('events', message);

      // Messages without sequence should be processed immediately
      expect(result.processed).toEqual([message]);
      expect(result.buffered).toEqual([]);
      expect(validator.getState('events').lastSequence).toBe(0);
    });
  });

  describe('replay messages', () => {
    it('should process replay messages that fill gaps', () => {
      const msg1: SequencedMessage = { type: 'event', sequence: 1, data: { id: 1 } };
      const msg3: SequencedMessage = { type: 'event', sequence: 3, data: { id: 3 } };
      const msg2Replay: SequencedMessage = {
        type: 'event',
        sequence: 2,
        data: { id: 2 },
        replay: true,
      };

      validator.handleMessage('events', msg1);
      validator.handleMessage('events', msg3);
      const result = validator.handleMessage('events', msg2Replay);

      expect(result.processed).toEqual([msg2Replay, msg3]);
      expect(validator.getState('events').lastSequence).toBe(3);
    });

    it('should ignore replay messages for already processed sequences', () => {
      const msg1: SequencedMessage = { type: 'event', sequence: 1, data: { id: 1 } };
      const msg1Replay: SequencedMessage = {
        type: 'event',
        sequence: 1,
        data: { id: 1 },
        replay: true,
      };

      validator.handleMessage('events', msg1);
      const result = validator.handleMessage('events', msg1Replay);

      expect(result.processed).toEqual([]);
      expect(result.duplicates).toEqual([msg1Replay]);
    });
  });

  describe('resync handling', () => {
    it('should handle resync from specific sequence', () => {
      const msg1: SequencedMessage = { type: 'event', sequence: 1, data: { id: 1 } };
      const msg2: SequencedMessage = { type: 'event', sequence: 2, data: { id: 2 } };
      const msg3: SequencedMessage = { type: 'event', sequence: 3, data: { id: 3 } };

      validator.handleMessage('events', msg1);
      validator.handleMessage('events', msg2);
      validator.handleMessage('events', msg3);

      // Reset to sequence 1 (simulating resync)
      validator.resetToSequence('events', 1);

      expect(validator.getState('events').lastSequence).toBe(1);
      expect(validator.getState('events').buffer.size).toBe(0);
    });

    it('should accept new sequence after resync', () => {
      const msg1: SequencedMessage = { type: 'event', sequence: 1, data: { id: 1 } };
      validator.handleMessage('events', msg1);

      validator.resetToSequence('events', 0);

      const msg1Again: SequencedMessage = { type: 'event', sequence: 1, data: { id: 1 } };
      const result = validator.handleMessage('events', msg1Again);

      expect(result.processed).toEqual([msg1Again]);
      expect(validator.getState('events').lastSequence).toBe(1);
    });
  });

  describe('statistics', () => {
    it('should track processed message count', () => {
      for (let i = 1; i <= 5; i++) {
        validator.handleMessage('events', {
          type: 'event',
          sequence: i,
          data: {},
        } as SequencedMessage);
      }

      const stats = validator.getStatistics('events');
      expect(stats.processedCount).toBe(5);
    });

    it('should track duplicate count', () => {
      validator.handleMessage('events', {
        type: 'event',
        sequence: 1,
        data: {},
      } as SequencedMessage);
      validator.handleMessage('events', {
        type: 'event',
        sequence: 1,
        data: {},
      } as SequencedMessage);
      validator.handleMessage('events', {
        type: 'event',
        sequence: 1,
        data: {},
      } as SequencedMessage);

      const stats = validator.getStatistics('events');
      expect(stats.duplicateCount).toBe(2);
    });

    it('should track resync count', () => {
      // NEM-3905: Use gaps > 50 to trigger resyncs with new threshold
      validator.handleMessage('events', {
        type: 'event',
        sequence: 1,
        data: {},
      } as SequencedMessage);
      // Gap of 99 (sequence 100 - 1 = 99) exceeds threshold of 50
      validator.handleMessage('events', {
        type: 'event',
        sequence: 100,
        data: {},
      } as SequencedMessage);
      // Gap of 99 (sequence 200 - 100 - buffer = ~99) exceeds threshold of 50
      validator.handleMessage('events', {
        type: 'event',
        sequence: 200,
        data: {},
      } as SequencedMessage);

      const stats = validator.getStatistics('events');
      expect(stats.resyncCount).toBe(2);
    });

    it('should track out-of-order count', () => {
      validator.handleMessage('events', {
        type: 'event',
        sequence: 1,
        data: {},
      } as SequencedMessage);
      validator.handleMessage('events', {
        type: 'event',
        sequence: 3,
        data: {},
      } as SequencedMessage);
      validator.handleMessage('events', {
        type: 'event',
        sequence: 5,
        data: {},
      } as SequencedMessage);

      const stats = validator.getStatistics('events');
      expect(stats.outOfOrderCount).toBe(2);
    });
  });

  describe('edge cases', () => {
    it('should handle first message being out of sequence', () => {
      const msg5: SequencedMessage = { type: 'event', sequence: 5, data: { id: 5 } };
      const result = validator.handleMessage('events', msg5);

      // First message should be processed regardless of sequence
      expect(result.processed).toEqual([msg5]);
      expect(validator.getState('events').lastSequence).toBe(5);
    });

    it('should handle very large sequence numbers', () => {
      const msg: SequencedMessage = { type: 'event', sequence: 999999999, data: { id: 1 } };
      const result = validator.handleMessage('events', msg);

      expect(result.processed).toEqual([msg]);
      expect(validator.getState('events').lastSequence).toBe(999999999);
    });

    it('should handle rapid sequence of messages', () => {
      const messages: SequencedMessage[] = [];
      for (let i = 1; i <= 100; i++) {
        messages.push({ type: 'event', sequence: i, data: { id: i } });
      }

      messages.forEach((msg) => validator.handleMessage('events', msg));

      expect(validator.getState('events').lastSequence).toBe(100);
      expect(validator.getStatistics('events').processedCount).toBe(100);
    });
  });
});

describe('DEFAULT_SEQUENCE_CONFIG', () => {
  it('should have reasonable default values', () => {
    expect(DEFAULT_SEQUENCE_CONFIG.maxBufferSize).toBeGreaterThan(0);
    expect(DEFAULT_SEQUENCE_CONFIG.gapThreshold).toBeGreaterThan(0);
    expect(DEFAULT_SEQUENCE_CONFIG.bufferTimeout).toBeGreaterThan(0);
  });

  it('should have gap threshold of 50 to reduce frequent resyncs (NEM-3905)', () => {
    // NEM-3905: Verify the gap threshold is set to 50 (was 10)
    // This reduces resync frequency from every 10-15 seconds to less than once per minute
    expect(DEFAULT_SEQUENCE_CONFIG.gapThreshold).toBe(50);
  });
});
