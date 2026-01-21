/**
 * Tests for ZonePresenceIndicator component
 */

import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import ZonePresenceIndicator, {
  MemberAvatar,
  CountBadge,
  EmptyState,
} from './ZonePresenceIndicator';
import { getInitials, formatTimeSince } from './zonePresenceUtils';

import type { ZonePresenceMember } from '../../hooks/useZonePresence';

// ============================================================================
// Mocks
// ============================================================================

// Mock the useZonePresence hook
const mockUseZonePresence = vi.fn();
vi.mock('../../hooks/useZonePresence', () => ({
  useZonePresence: (zoneId: string) => mockUseZonePresence(zoneId),
}));

// Mock data for tests
const createMockMember = (
  overrides: Partial<ZonePresenceMember> = {}
): ZonePresenceMember => ({
  id: 1,
  name: 'John Doe',
  role: 'resident',
  lastSeen: new Date().toISOString(),
  isStale: false,
  isActive: true,
  ...overrides,
});

describe('ZonePresenceIndicator', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Default mock implementation
    mockUseZonePresence.mockReturnValue({
      members: [],
      isConnected: true,
      isLoading: false,
      error: null,
      presentCount: 0,
      activeCount: 0,
      clearPresence: vi.fn(),
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Loading State', () => {
    it('should render loading skeleton when loading', () => {
      mockUseZonePresence.mockReturnValue({
        members: [],
        isConnected: true,
        isLoading: true,
        error: null,
        presentCount: 0,
        activeCount: 0,
        clearPresence: vi.fn(),
      });

      render(<ZonePresenceIndicator zoneId="zone-1" />);

      expect(screen.getByTestId('presence-loading')).toBeInTheDocument();
    });
  });

  describe('Empty State', () => {
    it('should render empty state when no members present', () => {
      mockUseZonePresence.mockReturnValue({
        members: [],
        isConnected: true,
        isLoading: false,
        error: null,
        presentCount: 0,
        activeCount: 0,
        clearPresence: vi.fn(),
      });

      render(<ZonePresenceIndicator zoneId="zone-1" />);

      expect(screen.getByTestId('presence-empty-state')).toBeInTheDocument();
    });

    it('should have "No one present" title in empty state', () => {
      mockUseZonePresence.mockReturnValue({
        members: [],
        isConnected: true,
        isLoading: false,
        error: null,
        presentCount: 0,
        activeCount: 0,
        clearPresence: vi.fn(),
      });

      render(<ZonePresenceIndicator zoneId="zone-1" />);

      const emptyState = screen.getByTestId('presence-empty-state');
      expect(emptyState).toHaveAttribute('title', 'No one present');
    });
  });

  describe('Member Display', () => {
    it('should render avatars for present members', () => {
      const members = [
        createMockMember({ id: 1, name: 'John Doe' }),
        createMockMember({ id: 2, name: 'Jane Smith' }),
      ];

      mockUseZonePresence.mockReturnValue({
        members,
        isConnected: true,
        isLoading: false,
        error: null,
        presentCount: 2,
        activeCount: 2,
        clearPresence: vi.fn(),
      });

      render(<ZonePresenceIndicator zoneId="zone-1" />);

      expect(screen.getByTestId('presence-avatar-1')).toBeInTheDocument();
      expect(screen.getByTestId('presence-avatar-2')).toBeInTheDocument();
    });

    it('should display member initials in avatars', () => {
      const members = [createMockMember({ id: 1, name: 'John Doe' })];

      mockUseZonePresence.mockReturnValue({
        members,
        isConnected: true,
        isLoading: false,
        error: null,
        presentCount: 1,
        activeCount: 1,
        clearPresence: vi.fn(),
      });

      render(<ZonePresenceIndicator zoneId="zone-1" />);

      expect(screen.getByText('JD')).toBeInTheDocument();
    });

    it('should limit displayed avatars to maxAvatars', () => {
      const members = [
        createMockMember({ id: 1, name: 'John Doe' }),
        createMockMember({ id: 2, name: 'Jane Smith' }),
        createMockMember({ id: 3, name: 'Bob Johnson' }),
        createMockMember({ id: 4, name: 'Alice Williams' }),
      ];

      mockUseZonePresence.mockReturnValue({
        members,
        isConnected: true,
        isLoading: false,
        error: null,
        presentCount: 4,
        activeCount: 4,
        clearPresence: vi.fn(),
      });

      render(<ZonePresenceIndicator zoneId="zone-1" maxAvatars={2} />);

      expect(screen.getByTestId('presence-avatar-1')).toBeInTheDocument();
      expect(screen.getByTestId('presence-avatar-2')).toBeInTheDocument();
      expect(screen.queryByTestId('presence-avatar-3')).not.toBeInTheDocument();
      expect(screen.queryByTestId('presence-avatar-4')).not.toBeInTheDocument();
    });

    it('should show count badge when members exceed maxAvatars', () => {
      const members = [
        createMockMember({ id: 1, name: 'John Doe' }),
        createMockMember({ id: 2, name: 'Jane Smith' }),
        createMockMember({ id: 3, name: 'Bob Johnson' }),
        createMockMember({ id: 4, name: 'Alice Williams' }),
      ];

      mockUseZonePresence.mockReturnValue({
        members,
        isConnected: true,
        isLoading: false,
        error: null,
        presentCount: 4,
        activeCount: 4,
        clearPresence: vi.fn(),
      });

      render(<ZonePresenceIndicator zoneId="zone-1" maxAvatars={2} showCount />);

      expect(screen.getByTestId('presence-count-badge')).toBeInTheDocument();
      expect(screen.getByText('+2')).toBeInTheDocument();
    });

    it('should not show count badge when showCount is false', () => {
      const members = [
        createMockMember({ id: 1, name: 'John Doe' }),
        createMockMember({ id: 2, name: 'Jane Smith' }),
        createMockMember({ id: 3, name: 'Bob Johnson' }),
      ];

      mockUseZonePresence.mockReturnValue({
        members,
        isConnected: true,
        isLoading: false,
        error: null,
        presentCount: 3,
        activeCount: 3,
        clearPresence: vi.fn(),
      });

      render(<ZonePresenceIndicator zoneId="zone-1" maxAvatars={2} showCount={false} />);

      expect(screen.queryByTestId('presence-count-badge')).not.toBeInTheDocument();
    });
  });

  describe('Pulse Animation', () => {
    it('should show pulse animation for active members', () => {
      const members = [createMockMember({ id: 1, name: 'John Doe', isActive: true })];

      mockUseZonePresence.mockReturnValue({
        members,
        isConnected: true,
        isLoading: false,
        error: null,
        presentCount: 1,
        activeCount: 1,
        clearPresence: vi.fn(),
      });

      render(<ZonePresenceIndicator zoneId="zone-1" />);

      expect(screen.getByTestId('presence-pulse-1')).toBeInTheDocument();
    });

    it('should not show pulse animation for inactive members', () => {
      const members = [createMockMember({ id: 1, name: 'John Doe', isActive: false })];

      mockUseZonePresence.mockReturnValue({
        members,
        isConnected: true,
        isLoading: false,
        error: null,
        presentCount: 1,
        activeCount: 0,
        clearPresence: vi.fn(),
      });

      render(<ZonePresenceIndicator zoneId="zone-1" />);

      expect(screen.queryByTestId('presence-pulse-1')).not.toBeInTheDocument();
    });
  });

  describe('Stale Presence', () => {
    it('should apply opacity class to stale members', () => {
      const members = [createMockMember({ id: 1, name: 'John Doe', isStale: true })];

      mockUseZonePresence.mockReturnValue({
        members,
        isConnected: true,
        isLoading: false,
        error: null,
        presentCount: 1,
        activeCount: 0,
        clearPresence: vi.fn(),
      });

      render(<ZonePresenceIndicator zoneId="zone-1" />);

      const avatar = screen.getByTestId('presence-avatar-1');
      const avatarInner = avatar.querySelector('.opacity-50');
      expect(avatarInner).toBeInTheDocument();
    });
  });

  describe('Size Variants', () => {
    it('should render small size variant', () => {
      const members = [createMockMember({ id: 1, name: 'John Doe' })];

      mockUseZonePresence.mockReturnValue({
        members,
        isConnected: true,
        isLoading: false,
        error: null,
        presentCount: 1,
        activeCount: 1,
        clearPresence: vi.fn(),
      });

      render(<ZonePresenceIndicator zoneId="zone-1" size="sm" />);

      const avatar = screen.getByTestId('presence-avatar-1');
      const avatarDiv = avatar.querySelector('.h-6.w-6');
      expect(avatarDiv).toBeInTheDocument();
    });

    it('should render medium size variant (default)', () => {
      const members = [createMockMember({ id: 1, name: 'John Doe' })];

      mockUseZonePresence.mockReturnValue({
        members,
        isConnected: true,
        isLoading: false,
        error: null,
        presentCount: 1,
        activeCount: 1,
        clearPresence: vi.fn(),
      });

      render(<ZonePresenceIndicator zoneId="zone-1" />);

      const avatar = screen.getByTestId('presence-avatar-1');
      const avatarDiv = avatar.querySelector('.h-8.w-8');
      expect(avatarDiv).toBeInTheDocument();
    });

    it('should render large size variant', () => {
      const members = [createMockMember({ id: 1, name: 'John Doe' })];

      mockUseZonePresence.mockReturnValue({
        members,
        isConnected: true,
        isLoading: false,
        error: null,
        presentCount: 1,
        activeCount: 1,
        clearPresence: vi.fn(),
      });

      render(<ZonePresenceIndicator zoneId="zone-1" size="lg" />);

      const avatar = screen.getByTestId('presence-avatar-1');
      const avatarDiv = avatar.querySelector('.h-10.w-10');
      expect(avatarDiv).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have proper aria-label for presence count', () => {
      const members = [
        createMockMember({ id: 1, name: 'John Doe' }),
        createMockMember({ id: 2, name: 'Jane Smith' }),
      ];

      mockUseZonePresence.mockReturnValue({
        members,
        isConnected: true,
        isLoading: false,
        error: null,
        presentCount: 2,
        activeCount: 2,
        clearPresence: vi.fn(),
      });

      render(<ZonePresenceIndicator zoneId="zone-1" />);

      const container = screen.getByRole('group');
      expect(container).toHaveAttribute('aria-label', '2 people present');
    });

    it('should use singular for single person', () => {
      const members = [createMockMember({ id: 1, name: 'John Doe' })];

      mockUseZonePresence.mockReturnValue({
        members,
        isConnected: true,
        isLoading: false,
        error: null,
        presentCount: 1,
        activeCount: 1,
        clearPresence: vi.fn(),
      });

      render(<ZonePresenceIndicator zoneId="zone-1" />);

      const container = screen.getByRole('group');
      expect(container).toHaveAttribute('aria-label', '1 person present');
    });

    it('should have tooltips on avatars', () => {
      const members = [createMockMember({ id: 1, name: 'John Doe' })];

      mockUseZonePresence.mockReturnValue({
        members,
        isConnected: true,
        isLoading: false,
        error: null,
        presentCount: 1,
        activeCount: 1,
        clearPresence: vi.fn(),
      });

      render(<ZonePresenceIndicator zoneId="zone-1" />);

      const avatar = screen.getByTestId('presence-avatar-1');
      expect(avatar).toHaveAttribute('title', expect.stringContaining('John Doe'));
    });
  });

  describe('Custom className', () => {
    it('should apply custom className', () => {
      mockUseZonePresence.mockReturnValue({
        members: [],
        isConnected: true,
        isLoading: false,
        error: null,
        presentCount: 0,
        activeCount: 0,
        clearPresence: vi.fn(),
      });

      render(<ZonePresenceIndicator zoneId="zone-1" className="custom-class" />);

      const container = screen.getByTestId('presence-container');
      expect(container).toHaveClass('custom-class');
    });
  });

  describe('Zone ID', () => {
    it('should call useZonePresence with correct zone ID', () => {
      mockUseZonePresence.mockReturnValue({
        members: [],
        isConnected: true,
        isLoading: false,
        error: null,
        presentCount: 0,
        activeCount: 0,
        clearPresence: vi.fn(),
      });

      render(<ZonePresenceIndicator zoneId="test-zone-123" />);

      expect(mockUseZonePresence).toHaveBeenCalledWith('test-zone-123');
    });
  });
});

// ============================================================================
// Helper Function Tests
// ============================================================================

describe('getInitials', () => {
  it('should get initials from two-word name', () => {
    expect(getInitials('John Doe')).toBe('JD');
  });

  it('should get first two chars from single-word name', () => {
    expect(getInitials('John')).toBe('JO');
  });

  it('should handle names with multiple spaces', () => {
    expect(getInitials('  John   Doe  ')).toBe('JD');
  });

  it('should handle three-word names', () => {
    expect(getInitials('John Middle Doe')).toBe('JD');
  });

  it('should convert to uppercase', () => {
    expect(getInitials('john doe')).toBe('JD');
  });
});

describe('formatTimeSince', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2025-01-21T12:00:00Z'));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('should format seconds as "Just now"', () => {
    const timestamp = new Date('2025-01-21T11:59:30Z').toISOString();
    expect(formatTimeSince(timestamp)).toBe('Just now');
  });

  it('should format minutes', () => {
    const timestamp = new Date('2025-01-21T11:55:00Z').toISOString();
    expect(formatTimeSince(timestamp)).toBe('5m ago');
  });

  it('should format hours', () => {
    const timestamp = new Date('2025-01-21T10:00:00Z').toISOString();
    expect(formatTimeSince(timestamp)).toBe('2h ago');
  });

  it('should format days', () => {
    const timestamp = new Date('2025-01-19T12:00:00Z').toISOString();
    expect(formatTimeSince(timestamp)).toBe('2d ago');
  });
});

// ============================================================================
// Subcomponent Tests
// ============================================================================

describe('MemberAvatar', () => {
  const mockMember = createMockMember({ id: 1, name: 'John Doe' });

  it('should render member initials', () => {
    render(<MemberAvatar member={mockMember} size="md" />);
    expect(screen.getByText('JD')).toBeInTheDocument();
  });

  it('should apply role-based colors', () => {
    const familyMember = createMockMember({ role: 'family' });
    render(<MemberAvatar member={familyMember} size="md" />);

    const avatar = screen.getByTestId(`presence-avatar-${familyMember.id}`);
    const avatarDiv = avatar.querySelector('.bg-blue-500');
    expect(avatarDiv).toBeInTheDocument();
  });

  it('should render tooltip with name and time', () => {
    render(<MemberAvatar member={mockMember} size="md" showTooltip />);

    const avatar = screen.getByTestId('presence-avatar-1');
    expect(avatar).toHaveAttribute('title', expect.stringContaining('John Doe'));
  });

  it('should not render tooltip when showTooltip is false', () => {
    render(<MemberAvatar member={mockMember} size="md" showTooltip={false} />);

    const avatar = screen.getByTestId('presence-avatar-1');
    expect(avatar).not.toHaveAttribute('title');
  });
});

describe('CountBadge', () => {
  const mockMembers = [
    createMockMember({ id: 1, name: 'John Doe' }),
    createMockMember({ id: 2, name: 'Jane Smith' }),
  ];

  it('should render count', () => {
    render(<CountBadge count={2} members={mockMembers} size="md" />);
    expect(screen.getByText('+2')).toBeInTheDocument();
  });

  it('should have tooltip with member names', () => {
    render(<CountBadge count={2} members={mockMembers} size="md" />);

    const badge = screen.getByTestId('presence-count-badge');
    const tooltip = badge.querySelector('[role="tooltip"]');
    expect(tooltip?.textContent).toContain('John Doe');
    expect(tooltip?.textContent).toContain('Jane Smith');
  });
});

describe('EmptyState', () => {
  it('should render users icon', () => {
    render(<EmptyState size="md" />);

    const emptyState = screen.getByTestId('presence-empty-state');
    const svg = emptyState.querySelector('svg');
    expect(svg).toBeInTheDocument();
  });

  it('should apply correct size classes', () => {
    render(<EmptyState size="sm" />);

    const emptyState = screen.getByTestId('presence-empty-state');
    expect(emptyState).toHaveClass('h-6', 'w-6');
  });
});
