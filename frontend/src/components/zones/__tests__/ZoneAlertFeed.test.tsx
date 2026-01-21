/**
 * Tests for ZoneAlertFeed component (NEM-3196)
 */

import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { type ReactNode } from 'react';
import { BrowserRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AlertPriority, TrustViolationType } from '../../../types/zoneAlert';
import { AnomalyType, AnomalySeverity } from '../../../types/zoneAnomaly';
import ZoneAlertFeed from '../ZoneAlertFeed';

import type { UnifiedZoneAlert, TrustViolation } from '../../../types/zoneAlert';
import type { ZoneAnomaly } from '../../../types/zoneAnomaly';

// Declare global for TypeScript
declare const global: {
  Audio: typeof Audio;
};

// Mock Audio
class MockAudio {
  play = vi.fn().mockResolvedValue(undefined);
}
global.Audio = MockAudio as unknown as typeof Audio;

// Mock useZonesQuery
vi.mock('../../../hooks/useZones', () => ({
  useZonesQuery: () => ({
    zones: [
      { id: 'zone-1', name: 'Front Door', color: '#ff0000', zone_type: 'entry_point' },
      { id: 'zone-2', name: 'Backyard', color: '#00ff00', zone_type: 'yard' },
    ],
    isLoading: false,
    error: null,
  }),
}));

// Mock hook functions
const mockAcknowledgeAlert = vi.fn().mockResolvedValue(undefined);
const mockAcknowledgeAll = vi.fn().mockResolvedValue(undefined);
const mockAcknowledgeBySeverity = vi.fn().mockResolvedValue(undefined);
const mockRefetch = vi.fn().mockResolvedValue(undefined);

// Default mock hook return value
const createMockHookReturn = (overrides = {}) => ({
  alerts: [] as UnifiedZoneAlert[],
  unacknowledgedCount: 0,
  totalCount: 0,
  isLoading: false,
  isFetching: false,
  error: null as Error | null,
  isError: false,
  refetch: mockRefetch,
  acknowledgeAlert: mockAcknowledgeAlert,
  acknowledgeAll: mockAcknowledgeAll,
  acknowledgeBySeverity: mockAcknowledgeBySeverity,
  isAcknowledging: false,
  isConnected: true,
  ...overrides,
});

let mockHookReturn = createMockHookReturn();

// Mock useZoneAlerts hook
vi.mock('../../../hooks/useZoneAlerts', () => ({
  useZoneAlerts: () => mockHookReturn,
}));

function Wrapper({ children }: { children: ReactNode }) {
  return <BrowserRouter>{children}</BrowserRouter>;
}

describe('ZoneAlertFeed', () => {
  // Create mock data
  const mockAnomaly: ZoneAnomaly = {
    id: 'anomaly-1',
    zone_id: 'zone-1',
    camera_id: 'cam-1',
    anomaly_type: AnomalyType.UNUSUAL_TIME,
    severity: AnomalySeverity.CRITICAL,
    title: 'Unusual activity at 3 AM',
    description: 'Activity detected at unusual hour',
    expected_value: 5,
    actual_value: 50,
    deviation: 9.0,
    detection_id: 1,
    thumbnail_url: null,
    acknowledged: false,
    acknowledged_at: null,
    acknowledged_by: null,
    timestamp: new Date(Date.now() - 3600000).toISOString(),
    created_at: new Date(Date.now() - 3600000).toISOString(),
    updated_at: new Date(Date.now() - 3600000).toISOString(),
  };

  const mockViolation: TrustViolation = {
    id: 'violation-1',
    zone_id: 'zone-1',
    camera_id: 'cam-1',
    violation_type: TrustViolationType.UNKNOWN_ENTITY,
    severity: 'warning',
    title: 'Unknown person detected',
    description: 'An unknown person was detected in the front door zone',
    entity_id: 'entity-1',
    entity_type: 'person',
    detection_id: 2,
    thumbnail_url: null,
    acknowledged: false,
    acknowledged_at: null,
    acknowledged_by: null,
    timestamp: new Date(Date.now() - 7200000).toISOString(),
    created_at: new Date(Date.now() - 7200000).toISOString(),
    updated_at: new Date(Date.now() - 7200000).toISOString(),
  };

  const mockAnomalyAlert: UnifiedZoneAlert = {
    id: 'anomaly-1',
    source: 'anomaly',
    zone_id: 'zone-1',
    camera_id: 'cam-1',
    severity: 'critical',
    priority: AlertPriority.CRITICAL,
    title: 'Unusual activity at 3 AM',
    description: 'Activity detected at unusual hour',
    thumbnail_url: null,
    acknowledged: false,
    acknowledged_at: null,
    timestamp: new Date(Date.now() - 3600000).toISOString(),
    originalAlert: mockAnomaly,
  };

  const mockViolationAlert: UnifiedZoneAlert = {
    id: 'violation-1',
    source: 'trust_violation',
    zone_id: 'zone-1',
    camera_id: 'cam-1',
    severity: 'warning',
    priority: AlertPriority.WARNING,
    title: 'Unknown person detected',
    description: 'An unknown person was detected in the front door zone',
    thumbnail_url: null,
    acknowledged: false,
    acknowledged_at: null,
    timestamp: new Date(Date.now() - 7200000).toISOString(),
    originalAlert: mockViolation,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    // Reset mock hook return to default
    mockHookReturn = createMockHookReturn();
  });

  it('renders loading state initially', () => {
    mockHookReturn = createMockHookReturn({ isLoading: true });
    render(<ZoneAlertFeed />, { wrapper: Wrapper });

    expect(screen.getByTestId('alert-feed-loading')).toBeInTheDocument();
  });

  it('renders alerts after loading', () => {
    mockHookReturn = createMockHookReturn({
      alerts: [mockAnomalyAlert, mockViolationAlert],
      totalCount: 2,
      unacknowledgedCount: 2,
    });
    render(<ZoneAlertFeed />, { wrapper: Wrapper });

    expect(screen.queryByTestId('alert-feed-loading')).not.toBeInTheDocument();
    expect(screen.getByTestId('alert-feed-list')).toBeInTheDocument();
    expect(screen.getAllByTestId('zone-alert-card')).toHaveLength(2);
  });

  it('displays alert titles', () => {
    mockHookReturn = createMockHookReturn({
      alerts: [mockAnomalyAlert, mockViolationAlert],
      totalCount: 2,
    });
    render(<ZoneAlertFeed />, { wrapper: Wrapper });

    expect(screen.getByText('Unusual activity at 3 AM')).toBeInTheDocument();
    expect(screen.getByText('Unknown person detected')).toBeInTheDocument();
  });

  it('displays zone names', () => {
    mockHookReturn = createMockHookReturn({
      alerts: [mockAnomalyAlert],
      totalCount: 1,
    });
    render(<ZoneAlertFeed />, { wrapper: Wrapper });

    expect(screen.getAllByText('Front Door').length).toBeGreaterThan(0);
  });

  it('shows unacknowledged count in header', () => {
    mockHookReturn = createMockHookReturn({
      alerts: [mockAnomalyAlert, mockViolationAlert],
      totalCount: 2,
      unacknowledgedCount: 2,
    });
    render(<ZoneAlertFeed />, { wrapper: Wrapper });

    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText(/unacknowledged/)).toBeInTheDocument();
  });

  it('shows connection status indicator', () => {
    mockHookReturn = createMockHookReturn({ isConnected: true });
    render(<ZoneAlertFeed />, { wrapper: Wrapper });

    expect(screen.getByText('Live')).toBeInTheDocument();
  });

  it('shows offline status when disconnected', () => {
    mockHookReturn = createMockHookReturn({ isConnected: false });
    render(<ZoneAlertFeed />, { wrapper: Wrapper });

    expect(screen.getByText('Offline')).toBeInTheDocument();
  });

  it('renders empty state when no alerts', () => {
    mockHookReturn = createMockHookReturn({
      alerts: [],
      totalCount: 0,
    });
    render(<ZoneAlertFeed />, { wrapper: Wrapper });

    expect(screen.getByTestId('alert-feed-empty')).toBeInTheDocument();
    expect(screen.getByText('No alerts found')).toBeInTheDocument();
  });

  it('renders error state on fetch error', () => {
    mockHookReturn = createMockHookReturn({
      isError: true,
      error: new Error('Failed to fetch'),
    });
    render(<ZoneAlertFeed />, { wrapper: Wrapper });

    expect(screen.getByTestId('alert-feed-error')).toBeInTheDocument();
    expect(screen.getByText('Failed to load alerts')).toBeInTheDocument();
  });

  it('allows retrying on error', async () => {
    const user = userEvent.setup();
    mockHookReturn = createMockHookReturn({
      isError: true,
      error: new Error('Failed to fetch'),
    });
    render(<ZoneAlertFeed />, { wrapper: Wrapper });

    const retryButton = screen.getByText('Retry');
    await user.click(retryButton);

    expect(mockRefetch).toHaveBeenCalled();
  });

  it('acknowledges a single alert', async () => {
    const user = userEvent.setup();
    mockHookReturn = createMockHookReturn({
      alerts: [mockAnomalyAlert],
      totalCount: 1,
      unacknowledgedCount: 1,
    });
    render(<ZoneAlertFeed />, { wrapper: Wrapper });

    const acknowledgeButtons = screen.getAllByLabelText('Acknowledge alert');
    await user.click(acknowledgeButtons[0]);

    expect(mockAcknowledgeAlert).toHaveBeenCalledWith('anomaly-1', 'anomaly');
  });

  it('acknowledges all alerts', async () => {
    const user = userEvent.setup();
    mockHookReturn = createMockHookReturn({
      alerts: [mockAnomalyAlert, mockViolationAlert],
      totalCount: 2,
      unacknowledgedCount: 2,
    });
    render(<ZoneAlertFeed />, { wrapper: Wrapper });

    const ackAllButton = screen.getByLabelText('Acknowledge all alerts');
    await user.click(ackAllButton);

    expect(mockAcknowledgeAll).toHaveBeenCalled();
  });

  it('acknowledges alerts by severity', async () => {
    const user = userEvent.setup();
    mockHookReturn = createMockHookReturn({
      alerts: [mockAnomalyAlert],
      totalCount: 1,
      unacknowledgedCount: 1,
    });
    render(<ZoneAlertFeed />, { wrapper: Wrapper });

    const quickAckButton = screen.getByRole('button', { name: /Critical \(1\)/ });
    await user.click(quickAckButton);

    expect(mockAcknowledgeBySeverity).toHaveBeenCalledWith('critical');
  });

  it('toggles sound notifications', async () => {
    const user = userEvent.setup();
    mockHookReturn = createMockHookReturn();
    render(<ZoneAlertFeed enableSound={false} />, { wrapper: Wrapper });

    // Sound should be disabled initially
    const soundToggle = screen.getByLabelText('Enable alert sounds');
    await user.click(soundToggle);

    // Now it should say disable
    expect(screen.getByLabelText('Disable alert sounds')).toBeInTheDocument();
  });

  it('calls onAlertClick when alert is clicked', async () => {
    const handleClick = vi.fn();
    const user = userEvent.setup();
    mockHookReturn = createMockHookReturn({
      alerts: [mockAnomalyAlert],
      totalCount: 1,
    });
    render(<ZoneAlertFeed onAlertClick={handleClick} />, { wrapper: Wrapper });

    const alertCards = screen.getAllByTestId('zone-alert-card');
    await user.click(alertCards[0]);

    expect(handleClick).toHaveBeenCalledWith(
      expect.objectContaining({
        id: 'anomaly-1',
        source: 'anomaly',
      })
    );
  });

  it('supports keyboard navigation on alert cards', async () => {
    const handleClick = vi.fn();
    const user = userEvent.setup();
    mockHookReturn = createMockHookReturn({
      alerts: [mockAnomalyAlert],
      totalCount: 1,
    });
    render(<ZoneAlertFeed onAlertClick={handleClick} />, { wrapper: Wrapper });

    const alertCards = screen.getAllByTestId('zone-alert-card');
    alertCards[0].focus();
    await user.keyboard('{Enter}');

    expect(handleClick).toHaveBeenCalled();
  });

  it('groups alerts by time by default', () => {
    mockHookReturn = createMockHookReturn({
      alerts: [mockAnomalyAlert, mockViolationAlert],
      totalCount: 2,
    });
    render(<ZoneAlertFeed />, { wrapper: Wrapper });

    // Should show "Today" group header since mock alerts are from today
    expect(screen.getByText('Today')).toBeInTheDocument();
  });

  it('groups alerts by severity when groupBy=severity', () => {
    mockHookReturn = createMockHookReturn({
      alerts: [mockAnomalyAlert, mockViolationAlert],
      totalCount: 2,
    });
    render(<ZoneAlertFeed groupBy="severity" />, { wrapper: Wrapper });

    // Should show severity group headers (use getAllByRole to find heading elements)
    const headings = screen.getAllByRole('heading', { level: 4 });
    const headingTexts = headings.map((h) => h.textContent);
    expect(headingTexts).toContain('Critical');
    expect(headingTexts).toContain('Warning');
  });

  it('groups alerts by zone when groupBy=zone', () => {
    mockHookReturn = createMockHookReturn({
      alerts: [mockAnomalyAlert],
      totalCount: 1,
    });
    render(<ZoneAlertFeed groupBy="zone" />, { wrapper: Wrapper });

    // Should show zone name as group header
    const groupHeaders = screen.getAllByText('Front Door');
    expect(groupHeaders.length).toBeGreaterThan(0);
  });

  it('displays severity badges correctly', () => {
    mockHookReturn = createMockHookReturn({
      alerts: [mockAnomalyAlert, mockViolationAlert],
      totalCount: 2,
    });
    render(<ZoneAlertFeed />, { wrapper: Wrapper });

    const cards = screen.getAllByTestId('zone-alert-card');
    const criticalCard = cards.find((card) => card.getAttribute('data-severity') === 'critical');
    const warningCard = cards.find((card) => card.getAttribute('data-severity') === 'warning');

    expect(criticalCard).toBeDefined();
    expect(warningCard).toBeDefined();
  });

  it('displays source badges correctly', () => {
    mockHookReturn = createMockHookReturn({
      alerts: [mockAnomalyAlert, mockViolationAlert],
      totalCount: 2,
    });
    render(<ZoneAlertFeed />, { wrapper: Wrapper });

    expect(screen.getAllByText('Anomaly').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Trust Violation').length).toBeGreaterThan(0);
  });

  it('links zone name to zone detail page', () => {
    mockHookReturn = createMockHookReturn({
      alerts: [mockAnomalyAlert],
      totalCount: 1,
    });
    render(<ZoneAlertFeed />, { wrapper: Wrapper });

    const zoneLinks = screen.getAllByRole('link', { name: 'Front Door' });
    expect(zoneLinks[0]).toHaveAttribute('href', '/zones/zone-1');
  });

  it('applies custom className', () => {
    mockHookReturn = createMockHookReturn();
    render(<ZoneAlertFeed className="custom-class" />, { wrapper: Wrapper });

    expect(screen.getByTestId('zone-alert-feed')).toHaveClass('custom-class');
  });

  it('applies maxHeight style', () => {
    mockHookReturn = createMockHookReturn({
      alerts: [mockAnomalyAlert],
      totalCount: 1,
    });
    render(<ZoneAlertFeed maxHeight="400px" />, { wrapper: Wrapper });

    const container = screen.getByTestId('alert-feed-list').parentElement;
    expect(container).toHaveStyle({ maxHeight: '400px' });
  });

  it('shows empty state message for no matching filters', () => {
    mockHookReturn = createMockHookReturn({
      alerts: [],
      totalCount: 0,
    });
    render(<ZoneAlertFeed />, { wrapper: Wrapper });

    // Change filter to trigger "has filters" state
    const severitySelect = screen.getByLabelText('Filter by severity');
    fireEvent.change(severitySelect, { target: { value: 'critical' } });

    expect(screen.getByText('Try adjusting your filters to see more results.')).toBeInTheDocument();
  });

  it('filters alerts by source client-side', () => {
    mockHookReturn = createMockHookReturn({
      alerts: [mockAnomalyAlert, mockViolationAlert],
      totalCount: 2,
    });
    render(<ZoneAlertFeed />, { wrapper: Wrapper });

    // Initially shows both
    expect(screen.getAllByTestId('zone-alert-card')).toHaveLength(2);

    // Filter to only anomalies
    const sourceSelect = screen.getByLabelText('Filter by source');
    fireEvent.change(sourceSelect, { target: { value: 'anomaly' } });

    // Should only show anomaly alerts
    const cards = screen.getAllByTestId('zone-alert-card');
    expect(cards.every((card) => card.getAttribute('data-source') === 'anomaly')).toBe(true);
  });

  it('disables ack button during acknowledging', () => {
    mockHookReturn = createMockHookReturn({
      alerts: [mockAnomalyAlert],
      totalCount: 1,
      unacknowledgedCount: 1,
      isAcknowledging: true,
    });
    render(<ZoneAlertFeed />, { wrapper: Wrapper });

    const acknowledgeButtons = screen.getAllByLabelText('Acknowledge alert');
    expect(acknowledgeButtons[0]).toBeDisabled();
  });

  it('shows acknowledged badge for acknowledged alerts', () => {
    const acknowledgedAlert: UnifiedZoneAlert = {
      ...mockAnomalyAlert,
      acknowledged: true,
      acknowledged_at: new Date().toISOString(),
    };
    mockHookReturn = createMockHookReturn({
      alerts: [acknowledgedAlert],
      totalCount: 1,
      unacknowledgedCount: 0,
    });
    render(<ZoneAlertFeed />, { wrapper: Wrapper });

    // Use getAllByText since there may be multiple acknowledged badges
    const acknowledgedBadges = screen.getAllByText('Acknowledged');
    expect(acknowledgedBadges.length).toBeGreaterThan(0);
  });

  it('shows fetching indicator when refetching', () => {
    mockHookReturn = createMockHookReturn({
      alerts: [mockAnomalyAlert],
      totalCount: 1,
      isFetching: true,
    });
    render(<ZoneAlertFeed />, { wrapper: Wrapper });

    // The RefreshCw icon should be rendered (with animation)
    const feedElement = screen.getByTestId('zone-alert-feed');
    expect(feedElement.querySelector('.animate-spin')).toBeInTheDocument();
  });

  it('hides acknowledge all button when no unacknowledged alerts', () => {
    mockHookReturn = createMockHookReturn({
      alerts: [{ ...mockAnomalyAlert, acknowledged: true }],
      totalCount: 1,
      unacknowledgedCount: 0,
    });
    render(<ZoneAlertFeed />, { wrapper: Wrapper });

    expect(screen.queryByLabelText('Acknowledge all alerts')).not.toBeInTheDocument();
  });
});
