/**
 * WebSocket Event Sequence Validator
 *
 * Provides sequence tracking, out-of-order buffering, gap detection,
 * and duplicate filtering for WebSocket messages.
 *
 * NEM-2019: Implement WebSocket event sequence validation
 *
 * Features:
 * - Per-channel sequence tracking
 * - Out-of-order event buffering and automatic reordering
 * - Large gap detection with resync request triggering
 * - Duplicate event filtering
 * - Statistics tracking for monitoring
 */

import { logger } from '../services/logger';

/**
 * A WebSocket message with sequence information.
 */
export interface SequencedMessage {
  /** Message type identifier */
  type: string;
  /** Monotonically increasing sequence number (1+) */
  sequence?: number;
  /** Message payload */
  data?: unknown;
  /** Whether this is a replayed message from buffer */
  replay?: boolean;
  /** Whether the client should acknowledge receipt */
  requires_ack?: boolean;
  /** ISO 8601 timestamp */
  timestamp?: string;
}

/**
 * Result of handling a sequenced message.
 */
export interface HandleMessageResult {
  /** Messages that were processed in order */
  processed: SequencedMessage[];
  /** Messages that were buffered for later processing */
  buffered: SequencedMessage[];
  /** Messages that were identified as duplicates */
  duplicates: SequencedMessage[];
  /** Whether a resync was triggered */
  resyncTriggered: boolean;
}

/**
 * State for a single channel's sequence tracking.
 */
export interface SequenceState {
  /** Last successfully processed sequence number */
  lastSequence: number;
  /** Buffer of out-of-order messages awaiting gap fill */
  buffer: Map<number, SequencedMessage>;
  /** Whether this is the first message received */
  isFirstMessage: boolean;
}

/**
 * Statistics for monitoring sequence validation.
 */
export interface SequenceStatistics {
  /** Total messages processed successfully */
  processedCount: number;
  /** Total duplicate messages ignored */
  duplicateCount: number;
  /** Total resync requests triggered */
  resyncCount: number;
  /** Total out-of-order messages buffered */
  outOfOrderCount: number;
  /** Current buffer size */
  currentBufferSize: number;
}

/**
 * Callback type for resync requests.
 */
export type ResyncCallback = (channel: string, lastSequence: number) => void;

/**
 * Configuration for the sequence validator.
 */
export interface SequenceConfig {
  /** Maximum number of messages to buffer before dropping oldest */
  maxBufferSize: number;
  /** Gap threshold that triggers a resync request */
  gapThreshold: number;
  /** Timeout in ms before buffered messages are processed anyway */
  bufferTimeout: number;
}

/**
 * Default configuration values.
 *
 * NEM-3905: Increased gapThreshold from 10 to 50 to reduce frequent resyncs.
 * The previous threshold of 10 was too sensitive for normal operation where
 * events may be filtered, batched, or connections briefly interrupted.
 * A threshold of 50 provides better tolerance while still detecting
 * genuine connection issues that require resync.
 */
export const DEFAULT_SEQUENCE_CONFIG: SequenceConfig = {
  maxBufferSize: 100,
  gapThreshold: 50,
  bufferTimeout: 5000,
};

/**
 * Internal state for a channel including statistics.
 */
interface ChannelState extends SequenceState {
  statistics: SequenceStatistics;
}

/**
 * WebSocket Event Sequence Validator
 *
 * Handles sequence validation, out-of-order buffering, gap detection,
 * and duplicate filtering for WebSocket messages.
 *
 * @example
 * ```ts
 * const validator = new SequenceValidator((channel, lastSeq) => {
 *   // Send resync request to backend
 *   ws.send({ type: 'resync', channel, last_sequence: lastSeq });
 * });
 *
 * // Handle incoming message
 * const result = validator.handleMessage('events', message);
 * result.processed.forEach(msg => {
 *   // Process in-order messages
 * });
 * ```
 */
export class SequenceValidator {
  private channels: Map<string, ChannelState> = new Map();
  private config: SequenceConfig;
  private resyncCallback: ResyncCallback;

  constructor(resyncCallback: ResyncCallback, config: Partial<SequenceConfig> = {}) {
    this.resyncCallback = resyncCallback;
    this.config = { ...DEFAULT_SEQUENCE_CONFIG, ...config };
  }

  /**
   * Get or create state for a channel.
   */
  private getOrCreateChannelState(channel: string): ChannelState {
    let state = this.channels.get(channel);
    if (!state) {
      state = {
        lastSequence: 0,
        buffer: new Map(),
        isFirstMessage: true,
        statistics: {
          processedCount: 0,
          duplicateCount: 0,
          resyncCount: 0,
          outOfOrderCount: 0,
          currentBufferSize: 0,
        },
      };
      this.channels.set(channel, state);
    }
    return state;
  }

  /**
   * Handle an incoming sequenced message.
   *
   * @param channel - The channel the message came from
   * @param message - The message to handle
   * @returns Result containing processed, buffered, and duplicate messages
   */
  handleMessage(channel: string, message: SequencedMessage): HandleMessageResult {
    const state = this.getOrCreateChannelState(channel);
    const result: HandleMessageResult = {
      processed: [],
      buffered: [],
      duplicates: [],
      resyncTriggered: false,
    };

    // Messages without sequence are passed through immediately
    if (message.sequence === undefined || message.sequence === null) {
      result.processed.push(message);
      return result;
    }

    const sequence = message.sequence;

    // First message for this channel - accept regardless of sequence
    if (state.isFirstMessage) {
      state.isFirstMessage = false;
      state.lastSequence = sequence;
      result.processed.push(message);
      state.statistics.processedCount++;
      return result;
    }

    // Check for duplicate (already processed or in buffer)
    if (sequence <= state.lastSequence || state.buffer.has(sequence)) {
      result.duplicates.push(message);
      state.statistics.duplicateCount++;
      logger.debug('Duplicate message ignored', {
        component: 'SequenceValidator',
        channel,
        sequence,
        lastSequence: state.lastSequence,
      });
      return result;
    }

    // Check if this is the next expected sequence
    const expectedSequence = state.lastSequence + 1;

    if (sequence === expectedSequence) {
      // In order - process immediately
      this.processMessage(state, message, result);
      // Then process any buffered messages that are now in order
      this.drainBuffer(state, result);
    } else {
      // Out of order
      const gap = sequence - state.lastSequence - 1;

      // Check for large gap that requires resync
      // NEM-3905: Only trigger resync when gap exceeds threshold (default: 50)
      if (gap >= this.config.gapThreshold) {
        result.resyncTriggered = true;
        state.statistics.resyncCount++;
        logger.warn('Large sequence gap detected, triggering resync', {
          component: 'SequenceValidator',
          channel,
          lastSequence: state.lastSequence,
          receivedSequence: sequence,
          gap,
          gapThreshold: this.config.gapThreshold,
        });
        this.resyncCallback(channel, state.lastSequence);
      }

      // Buffer the message for later processing
      this.bufferMessage(state, message, result);
    }

    return result;
  }

  /**
   * Process a message (update state and add to processed list).
   * Only called when message.sequence is known to be defined.
   */
  private processMessage(
    state: ChannelState,
    message: SequencedMessage,
    result: HandleMessageResult
  ): void {
    // Safe assertion: only called when sequence is known to be defined
    const sequence = message.sequence ?? state.lastSequence;
    state.lastSequence = sequence;
    result.processed.push(message);
    state.statistics.processedCount++;
  }

  /**
   * Buffer a message for later processing.
   * Only called when message.sequence is known to be defined.
   */
  private bufferMessage(
    state: ChannelState,
    message: SequencedMessage,
    result: HandleMessageResult
  ): void {
    // Safe assertion: only called when sequence is known to be defined
    const sequence = message.sequence ?? 0;

    // Enforce buffer size limit by dropping oldest
    if (state.buffer.size >= this.config.maxBufferSize) {
      const sequences = Array.from(state.buffer.keys()).sort((a, b) => a - b);
      const oldest = sequences[0];
      state.buffer.delete(oldest);
      logger.warn('Buffer full, dropping oldest message', {
        component: 'SequenceValidator',
        droppedSequence: oldest,
        bufferSize: state.buffer.size,
      });
    }

    state.buffer.set(sequence, message);
    result.buffered.push(message);
    state.statistics.outOfOrderCount++;
    state.statistics.currentBufferSize = state.buffer.size;
  }

  /**
   * Process buffered messages that are now in order.
   */
  private drainBuffer(state: ChannelState, result: HandleMessageResult): void {
    let nextSequence = state.lastSequence + 1;
    let bufferedMessage = state.buffer.get(nextSequence);

    while (bufferedMessage) {
      state.buffer.delete(nextSequence);
      this.processMessage(state, bufferedMessage, result);
      nextSequence = state.lastSequence + 1;
      bufferedMessage = state.buffer.get(nextSequence);
    }

    state.statistics.currentBufferSize = state.buffer.size;
  }

  /**
   * Get the current state for a channel.
   */
  getState(channel: string): SequenceState {
    const state = this.getOrCreateChannelState(channel);
    return {
      lastSequence: state.lastSequence,
      buffer: new Map(state.buffer),
      isFirstMessage: state.isFirstMessage,
    };
  }

  /**
   * Get statistics for a channel.
   */
  getStatistics(channel: string): SequenceStatistics {
    const state = this.getOrCreateChannelState(channel);
    return { ...state.statistics };
  }

  /**
   * Reset state for a channel.
   */
  reset(channel: string): void {
    this.channels.delete(channel);
    logger.info('Sequence validator reset for channel', {
      component: 'SequenceValidator',
      channel,
    });
  }

  /**
   * Reset to a specific sequence (used after resync).
   */
  resetToSequence(channel: string, sequence: number): void {
    const state = this.getOrCreateChannelState(channel);
    state.lastSequence = sequence;
    state.buffer.clear();
    state.isFirstMessage = sequence === 0;
    state.statistics.currentBufferSize = 0;
    logger.info('Sequence validator reset to sequence', {
      component: 'SequenceValidator',
      channel,
      sequence,
    });
  }

  /**
   * Reset all channel states.
   */
  resetAll(): void {
    this.channels.clear();
    logger.info('Sequence validator reset for all channels', {
      component: 'SequenceValidator',
    });
  }
}
