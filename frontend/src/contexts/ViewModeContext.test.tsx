import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it } from 'vitest';

import { UI_MODE_STORAGE_KEY, ViewModeProvider, useViewMode } from './ViewModeContext';
import AdvancedOnly from '../components/common/AdvancedOnly';
import AdvancedBanner from '../components/layout/AdvancedBanner';
import HubTabBar from '../components/layout/HubTabBar';
import ModeSwitch from '../components/layout/ModeSwitch';

function ModeReader() {
  const { mode, setMode } = useViewMode();
  return (
    <div>
      <span data-testid="current-mode">{mode}</span>
      <button onClick={() => setMode('advanced')}>Set Advanced</button>
      <button onClick={() => setMode('easy')}>Set Easy</button>
    </div>
  );
}

describe('ViewModeContext and mode components (F4.9)', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('defaults to easy when localStorage has no ui-mode key', () => {
    render(
      <ViewModeProvider>
        <ModeReader />
      </ViewModeProvider>
    );
    expect(screen.getByTestId('current-mode')).toHaveTextContent('easy');
  });

  it('persists mode changes to localStorage as JSON and restores across remount', async () => {
    const user = userEvent.setup();
    const { unmount } = render(
      <ViewModeProvider>
        <ModeReader />
      </ViewModeProvider>
    );

    await user.click(screen.getByRole('button', { name: 'Set Advanced' }));
    expect(screen.getByTestId('current-mode')).toHaveTextContent('advanced');
    expect(localStorage.getItem(UI_MODE_STORAGE_KEY)).toBe(JSON.stringify('advanced'));

    unmount();

    render(
      <ViewModeProvider>
        <ModeReader />
      </ViewModeProvider>
    );
    expect(screen.getByTestId('current-mode')).toHaveTextContent('advanced');
  });

  it('falls back to easy when localStorage holds an unknown or malformed value', () => {
    localStorage.setItem(UI_MODE_STORAGE_KEY, JSON.stringify('bogus-mode'));
    const { unmount } = render(
      <ViewModeProvider>
        <ModeReader />
      </ViewModeProvider>
    );
    expect(screen.getByTestId('current-mode')).toHaveTextContent('easy');
    unmount();

    localStorage.setItem(UI_MODE_STORAGE_KEY, '{not-valid-json');
    render(
      <ViewModeProvider>
        <ModeReader />
      </ViewModeProvider>
    );
    expect(screen.getByTestId('current-mode')).toHaveTextContent('easy');
  });

  it('returns easy and a no-op setter when useViewMode is called outside ViewModeProvider', async () => {
    const user = userEvent.setup();
    render(<ModeReader />);
    expect(screen.getByTestId('current-mode')).toHaveTextContent('easy');
    await user.click(screen.getByRole('button', { name: 'Set Advanced' }));
    expect(screen.getByTestId('current-mode')).toHaveTextContent('easy');
  });

  it('AdvancedOnly renders children only when mode is advanced', async () => {
    const user = userEvent.setup();
    render(
      <ViewModeProvider>
        <ModeSwitch />
        <AdvancedOnly>
          <div data-testid="secret-advanced-box">GPU Internals</div>
        </AdvancedOnly>
      </ViewModeProvider>
    );

    expect(screen.queryByTestId('secret-advanced-box')).not.toBeInTheDocument();
    await user.click(screen.getByTestId('mode-switch-advanced'));
    expect(screen.getByTestId('secret-advanced-box')).toBeInTheDocument();
    await user.click(screen.getByTestId('mode-switch-easy'));
    expect(screen.queryByTestId('secret-advanced-box')).not.toBeInTheDocument();
  });

  it('HubTabBar renders the tabs for the active hub and highlights the current tab', () => {
    render(
      <ViewModeProvider>
        <MemoryRouter initialEntries={['/settings/rules']}>
          <HubTabBar />
        </MemoryRouter>
      </ViewModeProvider>
    );

    const tablist = screen.getByRole('tablist');
    expect(tablist).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Alerts/i })).toHaveAttribute('aria-selected', 'false');
    expect(screen.getByRole('tab', { name: /Scene changes/i })).toHaveAttribute(
      'aria-selected',
      'false'
    );
    expect(screen.getByRole('tab', { name: /Rules/i })).toHaveAttribute('aria-selected', 'true');
  });

  it('AdvancedBanner shows on an Advanced URL in Easy mode and switches mode on click', async () => {
    const user = userEvent.setup();
    render(
      <ViewModeProvider>
        <MemoryRouter initialEntries={['/operations']}>
          <AdvancedBanner />
        </MemoryRouter>
      </ViewModeProvider>
    );

    expect(screen.getByText('This is an Advanced page')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Back to Home/i })).toHaveAttribute('href', '/');

    await user.click(screen.getByRole('button', { name: /Switch to Advanced/i }));
    expect(screen.queryByText('This is an Advanced page')).not.toBeInTheDocument();
  });
});
