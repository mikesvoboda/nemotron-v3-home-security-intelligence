/**
 * A/B Test Execution Service for Prompt Playground
 *
 * Provides functionality to run A/B tests comparing original and modified prompts
 * against events. Supports both single-event tests and batch random tests.
 *
 * @module abTestService
 */

import { fetchEvents, ApiError } from './api';

// ============================================================================
// Types
// ============================================================================

/**
 * Configuration for the AI model used in testing
 */
export interface ModelConfig {
  /** Model name (e.g., 'nemotron') */
  model: string;
  /** LLM temperature setting (0.0 - 2.0) */
  temperature: number;
  /** Maximum tokens in response */
  maxTokens: number;
}

/**
 * Summary of an event for A/B test selection
 */
export interface EventSummary {
  /** Unique event identifier */
  id: number;
  /** Event timestamp */
  timestamp: string;
  /** Name of the camera that captured the event */
  cameraName: string;
  /** Number of detections in the event */
  detectionCount: number;
}

/**
 * Response from the test-prompt API endpoint
 */
export interface TestPromptResponse {
  /** Computed risk score (0-100) */
  riskScore: number;
  /** Risk level: low, medium, high, or critical */
  riskLevel: string;
  /** LLM reasoning for the risk assessment */
  reasoning: string;
  /** Brief summary of the analysis */
  summary: string;
  /** Processing time in milliseconds */
  processingTimeMs: number;
  /** Estimated tokens used */
  tokensUsed: number;
}

/**
 * Result of an A/B test comparing two prompts
 */
export interface ABTestResult {
  /** Event ID used for the test */
  eventId: number;
  /** Result from the original prompt */
  originalResult: TestPromptResponse;
  /** Result from the modified prompt */
  modifiedResult: TestPromptResponse;
  /** Difference in risk scores (modified - original) */
  scoreDelta: number;
  /** Error message if the test failed partially or completely */
  error?: string;
}

/**
 * Interface for A/B test execution service
 */
export interface ABTestService {
  /**
   * Run a single A/B test comparing two prompts against an event.
   *
   * @param eventId - Event ID to test against
   * @param originalPrompt - The original/baseline prompt text
   * @param modifiedPrompt - The modified prompt text to compare
   * @param modelConfig - Model configuration settings
   * @returns A/B test result with both analyses and score delta
   */
  runTest(
    eventId: number,
    originalPrompt: string,
    modifiedPrompt: string,
    modelConfig: ModelConfig
  ): Promise<ABTestResult>;

  /**
   * Run A/B tests on multiple random events.
   *
   * @param count - Number of events to test
   * @param originalPrompt - The original/baseline prompt text
   * @param modifiedPrompt - The modified prompt text to compare
   * @param modelConfig - Model configuration settings
   * @returns Array of A/B test results (partial failures don't break the batch)
   */
  runRandomTests(
    count: number,
    originalPrompt: string,
    modifiedPrompt: string,
    modelConfig: ModelConfig
  ): Promise<ABTestResult[]>;

  /**
   * Get available events for A/B testing.
   *
   * @param limit - Maximum number of events to return (default 50)
   * @returns Array of event summaries
   */
  getAvailableEvents(limit?: number): Promise<EventSummary[]>;
}

// ============================================================================
// Configuration
// ============================================================================

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) || '';
const API_KEY = import.meta.env.VITE_API_KEY as string | undefined;

/** Timeout for A/B test API calls (30 seconds) */
const TEST_TIMEOUT_MS = 30000;

// ============================================================================
// Internal API Functions
// ============================================================================

/**
 * Call the test-prompt API endpoint
 *
 * @param eventId - Event ID to test against
 * @param customPrompt - Custom prompt text to test
 * @param config - Model configuration
 * @returns Test prompt response
 */
async function testPromptApi(
  eventId: number,
  customPrompt: string,
  config: ModelConfig
): Promise<TestPromptResponse> {
  const url = `${BASE_URL}/api/prompts/test-prompt`;

  // Build headers with optional API key
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
  };
  if (API_KEY) {
    headers['X-API-Key'] = API_KEY;
  }

  // Create abort controller for timeout
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), TEST_TIMEOUT_MS);

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        event_id: eventId,
        custom_prompt: customPrompt,
        temperature: config.temperature,
        max_tokens: config.maxTokens,
        model: config.model,
      }),
      signal: controller.signal,
    });

    if (!response.ok) {
      let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
      try {
        const errorBody: unknown = await response.json();
        if (typeof errorBody === 'object' && errorBody !== null && 'detail' in errorBody) {
          errorMessage = String((errorBody as { detail: unknown }).detail);
        }
      } catch {
        // If response body is not JSON, use status text
      }
      throw new ApiError(response.status, errorMessage);
    }

    const data = (await response.json()) as {
      risk_score: number;
      risk_level: string;
      reasoning: string;
      summary: string;
      processing_time_ms: number;
      tokens_used: number;
    };

    return {
      riskScore: data.risk_score,
      riskLevel: data.risk_level,
      reasoning: data.reasoning,
      summary: data.summary,
      processingTimeMs: data.processing_time_ms,
      tokensUsed: data.tokens_used,
    };
  } finally {
    clearTimeout(timeoutId);
  }
}

// ============================================================================
// Service Implementation
// ============================================================================

/**
 * A/B Test Execution Service Implementation
 */
export const abTestService: ABTestService = {
  async runTest(
    eventId: number,
    originalPrompt: string,
    modifiedPrompt: string,
    modelConfig: ModelConfig
  ): Promise<ABTestResult> {
    // Type for error result
    type ErrorResult = { error: unknown };
    type SettledResult = TestPromptResponse | ErrorResult;

    // Run both prompts in parallel using Promise.all
    const [originalPromise, modifiedPromise] = [
      testPromptApi(eventId, originalPrompt, modelConfig).catch(
        (err: unknown): ErrorResult => ({
          error: err,
        })
      ),
      testPromptApi(eventId, modifiedPrompt, modelConfig).catch(
        (err: unknown): ErrorResult => ({
          error: err,
        })
      ),
    ];

    const [originalSettled, modifiedSettled]: [SettledResult, SettledResult] = await Promise.all([
      originalPromise,
      modifiedPromise,
    ]);

    // Check for errors
    const originalError = 'error' in originalSettled ? originalSettled.error : null;
    const modifiedError = 'error' in modifiedSettled ? modifiedSettled.error : null;

    if (originalError || modifiedError) {
      // Create partial result with error information
      const errorMessages: string[] = [];
      if (originalError) {
        const errMsg =
          originalError instanceof Error ? originalError.message : 'Original prompt test failed';
        errorMessages.push(`Original: ${errMsg}`);
      }
      if (modifiedError) {
        const errMsg =
          modifiedError instanceof Error ? modifiedError.message : 'Modified prompt test failed';
        errorMessages.push(`Modified: ${errMsg}`);
      }

      // Return partial result with defaults for failed parts
      const defaultResult: TestPromptResponse = {
        riskScore: 0,
        riskLevel: 'unknown',
        reasoning: '',
        summary: '',
        processingTimeMs: 0,
        tokensUsed: 0,
      };

      const originalResult = originalError
        ? defaultResult
        : (originalSettled as TestPromptResponse);
      const modifiedResult = modifiedError
        ? defaultResult
        : (modifiedSettled as TestPromptResponse);

      return {
        eventId,
        originalResult,
        modifiedResult,
        scoreDelta: modifiedResult.riskScore - originalResult.riskScore,
        error: errorMessages.join('; '),
      };
    }

    // Both succeeded - calculate delta and return
    const originalResult = originalSettled as TestPromptResponse;
    const modifiedResult = modifiedSettled as TestPromptResponse;

    return {
      eventId,
      originalResult,
      modifiedResult,
      scoreDelta: modifiedResult.riskScore - originalResult.riskScore,
    };
  },

  async runRandomTests(
    count: number,
    originalPrompt: string,
    modifiedPrompt: string,
    modelConfig: ModelConfig
  ): Promise<ABTestResult[]> {
    // First, fetch available events
    const events = await this.getAvailableEvents(count);

    if (events.length === 0) {
      return [];
    }

    // Run tests for each event using Promise.allSettled to handle partial failures
    const testPromises = events.map((event) =>
      this.runTest(event.id, originalPrompt, modifiedPrompt, modelConfig)
    );

    const results = await Promise.allSettled(testPromises);

    // Filter and return successful results
    const successfulResults: ABTestResult[] = [];
    for (const result of results) {
      if (result.status === 'fulfilled') {
        successfulResults.push(result.value);
      }
    }

    return successfulResults;
  },

  async getAvailableEvents(limit: number = 50): Promise<EventSummary[]> {
    // Use existing events API
    const response = await fetchEvents({ limit });

    // Transform to EventSummary format
    // Note: Event type only has camera_id, not camera_name
    return response.items.map((event) => ({
      id: event.id,
      timestamp: event.started_at,
      cameraName: event.camera_id,
      detectionCount: event.detection_count,
    }));
  },
};

// Export the service as default as well
export default abTestService;
