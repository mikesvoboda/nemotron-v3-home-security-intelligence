/**
 * Types for Cost Analytics Dashboard
 *
 * Part of NEM-5024 Phase 2: Cost Analytics Dashboard
 */

/** Cost breakdown by model */
export interface ModelCostBreakdown {
  /** Model identifier (e.g., 'nemotron', 'yolo26') */
  model: string;
  /** Total cost in USD for this model */
  cost_usd: number;
  /** Total GPU time consumed in seconds */
  gpu_seconds: number;
  /** Number of inference requests */
  request_count: number;
}

/** Token usage metrics for LLM models */
export interface TokenUsageMetrics {
  /** Total input/prompt tokens */
  input_tokens: number;
  /** Total output/completion tokens */
  output_tokens: number;
  /** Total tokens (input + output) */
  total_tokens: number;
  /** Estimated cost for tokens in USD */
  token_cost_usd: number;
}

/** Cost data for a single day */
export interface DailyCostEntry {
  /** Date in YYYY-MM-DD format */
  date: string;
  /** Total estimated cost for the day */
  total_cost_usd: number;
  /** Token-related cost */
  token_cost_usd: number;
  /** GPU time cost */
  gpu_cost_usd: number;
  /** Number of security events analyzed */
  event_count: number;
  /** Number of detections processed */
  detection_count: number;
}

/** Budget utilization metrics */
export interface BudgetUtilization {
  /** Budget period: 'daily' or 'monthly' */
  period: string;
  /** Budget limit in USD */
  limit_usd: number;
  /** Amount used in USD */
  used_usd: number;
  /** Amount remaining in USD */
  remaining_usd: number;
  /** Utilization ratio (0.0 to 1.0+) */
  utilization_ratio: number;
  /** Whether budget has been exceeded */
  exceeded: boolean;
  /** Whether warning threshold reached */
  warning_reached: boolean;
}

/** Cost efficiency metrics */
export interface CostEfficiencyMetrics {
  /** Average cost per detection in USD */
  cost_per_detection_usd: number;
  /** Average cost per event in USD */
  cost_per_event_usd: number;
  /** Total detections processed */
  total_detections: number;
  /** Total security events analyzed */
  total_events: number;
}

/** Cloud equivalent pricing configuration */
export interface PricingConfig {
  /** Cost per 1000 input tokens in USD */
  input_cost_per_1k_tokens: number;
  /** Cost per 1000 output tokens in USD */
  output_cost_per_1k_tokens: number;
  /** GPU cost per second in USD */
  gpu_cost_per_second: number;
  /** Detection cost per image in USD */
  detection_cost_per_image: number;
  /** Enrichment cost per operation in USD */
  enrichment_cost_per_operation: number;
}

/** Full cost analytics response */
export interface CostAnalyticsResponse {
  /** Today's cost summary */
  today: DailyCostEntry;
  /** Daily budget utilization */
  daily_budget: BudgetUtilization;
  /** Monthly budget utilization */
  monthly_budget: BudgetUtilization;
  /** Token usage metrics */
  token_usage: TokenUsageMetrics;
  /** Cost breakdown by model */
  cost_by_model: ModelCostBreakdown[];
  /** Cost efficiency metrics */
  efficiency: CostEfficiencyMetrics;
  /** Daily cost history (last 30 days) */
  cost_history: DailyCostEntry[];
  /** Current pricing configuration */
  pricing: PricingConfig;
  /** ISO timestamp of last update */
  last_updated: string;
}

/** Data point for cost trend charts */
export interface CostTrendDataPoint {
  /** Date in YYYY-MM-DD format */
  date: string;
  /** Total cost for the period */
  cost_usd: number;
}

/** Response for cost trend endpoint */
export interface CostTrendResponse {
  /** Cost trend data points */
  data_points: CostTrendDataPoint[];
  /** Total cost over the period */
  total_cost_usd: number;
  /** Start date of the trend */
  start_date: string;
  /** End date of the trend */
  end_date: string;
}

/** Parameters for cost trend query */
export interface CostTrendParams {
  /** Start date in YYYY-MM-DD format */
  start_date: string;
  /** End date in YYYY-MM-DD format */
  end_date: string;
}
