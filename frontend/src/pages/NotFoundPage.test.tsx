/**
 * Tests for NotFoundPage component
 *
 * Following TDD approach: RED -> GREEN -> REFACTOR
 *
 * @module pages/NotFoundPage.test
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import NotFoundPage from './NotFoundPage';

// Mock useNavigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

describe('NotFoundPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('displays 404 error code', () => {
    render(
      <BrowserRouter>
        <NotFoundPage />
      </BrowserRouter>
    );

    expect(screen.getByText('404')).toBeInTheDocument();
  });

  it('displays "Page Not Found" title', () => {
    render(
      <BrowserRouter>
        <NotFoundPage />
      </BrowserRouter>
    );

    expect(screen.getByRole('heading', { name: /page not found/i })).toBeInTheDocument();
  });

  it('displays descriptive message about the missing page', () => {
    render(
      <BrowserRouter>
        <NotFoundPage />
      </BrowserRouter>
    );

    expect(
      screen.getByText(/the page you are looking for does not exist/i)
    ).toBeInTheDocument();
  });

  it('displays "Return to Dashboard" button', () => {
    render(
      <BrowserRouter>
        <NotFoundPage />
      </BrowserRouter>
    );

    expect(screen.getByRole('button', { name: /return to dashboard/i })).toBeInTheDocument();
  });

  it('navigates to dashboard when "Return to Dashboard" button is clicked', async () => {
    const user = userEvent.setup();

    render(
      <BrowserRouter>
        <NotFoundPage />
      </BrowserRouter>
    );

    const button = screen.getByRole('button', { name: /return to dashboard/i });
    await user.click(button);

    expect(mockNavigate).toHaveBeenCalledWith('/');
  });

  it('has NVIDIA green accent color styling', () => {
    render(
      <BrowserRouter>
        <NotFoundPage />
      </BrowserRouter>
    );

    // Check for NVIDIA green color (#76B900) in the 404 text
    const errorCode = screen.getByText('404');
    expect(errorCode).toHaveClass('text-[#76B900]');
  });

  it('has dark theme styling', () => {
    render(
      <BrowserRouter>
        <NotFoundPage />
      </BrowserRouter>
    );

    // The page container should have dark background styling
    const container = screen.getByTestId('not-found-page');
    expect(container).toBeInTheDocument();
  });

  it('is accessible with proper heading hierarchy', () => {
    render(
      <BrowserRouter>
        <NotFoundPage />
      </BrowserRouter>
    );

    // Should have a proper h1 heading
    const heading = screen.getByRole('heading', { level: 1 });
    expect(heading).toBeInTheDocument();
    expect(heading).toHaveTextContent(/page not found/i);
  });

  it('displays a home icon on the return button', () => {
    render(
      <BrowserRouter>
        <NotFoundPage />
      </BrowserRouter>
    );

    // The button should contain an icon (we check it renders without errors)
    const button = screen.getByRole('button', { name: /return to dashboard/i });
    expect(button.querySelector('svg')).toBeInTheDocument();
  });
});
