import { clsx } from 'clsx';
import { useEffect, useRef, useState } from 'react';

import { getRiskColor, getRiskLabel, getRiskLevel } from '../../utils/risk';

/**
 * Generates an SVG path for a sparkline chart
 * @param data - Array of data points (0-100)
 * @param height - Height of the SVG canvas
 * @param fillPath - Whether to generate a filled area path (true) or line path (false)
 * @returns SVG path string
 */
function generateSparklinePath(data: number[], height: number, fillPath: boolean): string {
  if (data.length === 0) return '';

  const maxValue = Math.max(...data, 100); // Ensure scale includes 100
  const minValue = Math.min(...data, 0); // Ensure scale includes 0
  const range = maxValue - minValue || 1; // Avoid division by zero
  const padding = 2; // Padding from edges
  const availableHeight = height - padding * 2;

  // Calculate points
  const points = data.map((value, index) => {
    const x = (index / (data.length - 1 || 1)) * 100; // Percentage of width
    const normalizedValue = (value - minValue) / range;
    const y = height - padding - normalizedValue * availableHeight; // Invert Y axis
    return { x: `${x}%`, y };
  });

  if (points.length === 0) return '';

  // Build path
  let path = `M ${points[0].x} ${points[0].y}`;

  // Add line segments
  for (let i = 1; i < points.length; i++) {
    path += ` L ${points[i].x} ${points[i].y}`;
  }

  // For filled area, close the path
  if (fillPath) {
    path += ` L ${points[points.length - 1].x} ${height}`;
    path += ` L ${points[0].x} ${height}`;
    path += ' Z';
  }

  return path;
}

export interface RiskGaugeProps {
  /** Risk score value between 0-100 */
  value: number;
  /** Optional array of historical risk values for sparkline display */
  history?: number[];
  /** Size variant for the gauge */
  size?: 'sm' | 'md' | 'lg';
  /** Whether to show the risk level label */
  showLabel?: boolean;
  /** Additional CSS classes */
  className?: string;
}

/**
 * RiskGauge displays a circular SVG-based gauge showing the current risk score (0-100)
 * with color-coded severity levels and smooth animations. Optionally displays a sparkline
 * of recent risk history.
 *
 * Color coding (thresholds match backend SeverityService):
 * - Green (0-29): Low risk
 * - Yellow (30-59): Medium risk
 * - Orange (60-84): High risk
 * - Red (85-100): Critical risk
 *
 * Thresholds can be fetched from GET /api/system/severity for dynamic configuration.
 *
 * Features NVIDIA theme with primary green (#76B900) and dark backgrounds.
 */
export default function RiskGauge({
  value,
  history,
  size = 'md',
  showLabel = true,
  className,
}: RiskGaugeProps) {
  // Validate and clamp risk score
  const clampedValue = Math.max(0, Math.min(100, value));

  // Warn in development if value is out of range
  if (import.meta.env.MODE !== 'production' && (value < 0 || value > 100)) {
    console.warn(`RiskGauge: value ${value} is out of range [0-100]. Clamping to ${clampedValue}.`);
  }

  // Animated value for smooth transitions
  const [animatedValue, setAnimatedValue] = useState(0);
  // Use ref to track the starting value for animation without causing re-renders
  const animationStartRef = useRef(0);

  // Animate value changes
  useEffect(() => {
    // Skip animation in test environment for instant updates
    if (import.meta.env.MODE === 'test') {
      setAnimatedValue(clampedValue);
      animationStartRef.current = clampedValue;
      return;
    }

    const duration = 1000; // 1 second animation
    const steps = 60; // 60fps
    const stepDuration = duration / steps;

    // Capture the starting value at the beginning of this animation
    const startValue = animationStartRef.current;
    const stepSize = (clampedValue - startValue) / steps;

    let currentStep = 0;
    const timer = setInterval(() => {
      currentStep++;
      if (currentStep >= steps) {
        setAnimatedValue(clampedValue);
        animationStartRef.current = clampedValue;
        clearInterval(timer);
      } else {
        const newValue = startValue + stepSize * currentStep;
        setAnimatedValue(newValue);
      }
    }, stepDuration);

    return () => clearInterval(timer);
    // Only depend on clampedValue - NOT animatedValue to avoid infinite loop
  }, [clampedValue]);

  // Get risk level and associated styling
  const level = getRiskLevel(clampedValue);
  const color = getRiskColor(level);
  const label = getRiskLabel(level);

  // Size configurations
  const dimensions = {
    sm: { size: 120, stroke: 8, fontSize: 20 },
    md: { size: 160, stroke: 12, fontSize: 28 },
    lg: { size: 200, stroke: 16, fontSize: 36 },
  }[size];

  // SVG circle calculations
  const { size: svgSize, stroke } = dimensions;
  const radius = (svgSize - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const center = svgSize / 2;

  // Calculate stroke dash offset for animated arc
  const progress = animatedValue / 100;
  const strokeDashoffset = circumference * (1 - progress);

  // Get gradient colors based on risk level
  // Thresholds match backend SeverityService: LOW 0-29, MEDIUM 30-59, HIGH 60-84, CRITICAL 85-100
  const getGradientStops = () => {
    const stops = [
      { offset: '0%', color: '#76B900' }, // NVIDIA Green (low: 0-29)
      { offset: '29%', color: '#76B900' },
      { offset: '30%', color: '#FFB800' }, // NVIDIA Yellow (medium: 30-59)
      { offset: '59%', color: '#FFB800' },
      { offset: '60%', color: '#E74856' }, // NVIDIA Red (high: 60-84)
      { offset: '84%', color: '#E74856' },
      { offset: '85%', color: '#ef4444' }, // red-500 (critical: 85-100)
      { offset: '100%', color: '#ef4444' },
    ];
    return stops;
  };

  // Container padding based on size
  const containerPadding = {
    sm: 'p-4',
    md: 'p-6',
    lg: 'p-8',
  }[size];

  // Label text size
  const labelSize = {
    sm: 'text-sm',
    md: 'text-base',
    lg: 'text-lg',
  }[size];

  return (
    <div
      className={clsx('flex flex-col items-center justify-center', containerPadding, className)}
      role="meter"
      aria-valuenow={clampedValue}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={`Risk level: ${label}, score ${clampedValue}`}
    >
      {/* SVG Circular Gauge */}
      <div className="relative">
        <svg width={svgSize} height={svgSize} className="-rotate-90 transform" aria-hidden="true">
          {/* Define gradient for gauge colors */}
          <defs>
            <linearGradient id="riskGradient" x1="0%" y1="0%" x2="100%" y2="0%">
              {getGradientStops().map((stop) => (
                <stop key={stop.offset} offset={stop.offset} stopColor={stop.color} />
              ))}
            </linearGradient>

            {/* Glow filter for high/critical risk */}
            <filter id="glow">
              <feGaussianBlur stdDeviation="2" result="coloredBlur" />
              <feMerge>
                <feMergeNode in="coloredBlur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Background circle (track) */}
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke="#2A2A2A"
            strokeWidth={stroke}
          />

          {/* Animated progress circle */}
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={stroke}
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            className="transition-all duration-500 ease-out"
            filter={level === 'critical' || level === 'high' ? 'url(#glow)' : undefined}
          />
        </svg>

        {/* Center text display */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <div
            className={clsx('font-bold text-white', `text-[${dimensions.fontSize}px]`)}
            style={{ fontSize: `${dimensions.fontSize}px` }}
          >
            {Math.round(animatedValue)}
          </div>
          {showLabel && (
            <div className={clsx('mt-1 font-medium', labelSize)} style={{ color }}>
              {label}
            </div>
          )}
        </div>
      </div>

      {/* Optional sparkline for risk history */}
      {history && history.length > 0 && (
        <div className="mt-4 w-full max-w-xs">
          <div className="mb-1 text-center text-xs text-text-secondary">Risk History</div>
          <svg width="100%" height="40" className="w-full" aria-hidden="true">
            {/* Simple line sparkline */}
            {history.length > 1 && (
              <>
                {/* Background area */}
                <path
                  d={generateSparklinePath(history, 40, true)}
                  fill={`${color}20`}
                  stroke="none"
                />
                {/* Line */}
                <path
                  d={generateSparklinePath(history, 40, false)}
                  fill="none"
                  stroke={color}
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </>
            )}
          </svg>
        </div>
      )}
    </div>
  );
}
