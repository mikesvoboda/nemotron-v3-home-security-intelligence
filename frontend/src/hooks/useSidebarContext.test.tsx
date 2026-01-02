import { render, screen, fireEvent , renderHook } from '@testing-library/react';
import { useState, type ReactNode } from 'react';
import { describe, it, expect, vi } from 'vitest';

import { SidebarContext, useSidebarContext } from './useSidebarContext';

import type { SidebarContextType } from './useSidebarContext';

describe('useSidebarContext', () => {
  describe('Context Provider', () => {
    // Helper to create a wrapper with SidebarContext provider
    function createWrapper(initialState: boolean = false) {
      return function Wrapper({ children }: { children: ReactNode }) {
        const [isMobileMenuOpen, setMobileMenuOpen] = useState(initialState);

        const toggleMobileMenu = () => {
          setMobileMenuOpen((prev) => !prev);
        };

        const value: SidebarContextType = {
          isMobileMenuOpen,
          setMobileMenuOpen,
          toggleMobileMenu,
        };

        return <SidebarContext.Provider value={value}>{children}</SidebarContext.Provider>;
      };
    }

    it('provides isMobileMenuOpen state', () => {
      const wrapper = createWrapper(false);

      const { result } = renderHook(() => useSidebarContext(), { wrapper });

      expect(result.current.isMobileMenuOpen).toBe(false);
    });

    it('provides isMobileMenuOpen as true when initialized as true', () => {
      const wrapper = createWrapper(true);

      const { result } = renderHook(() => useSidebarContext(), { wrapper });

      expect(result.current.isMobileMenuOpen).toBe(true);
    });

    it('provides setMobileMenuOpen function', () => {
      const wrapper = createWrapper(false);

      const { result } = renderHook(() => useSidebarContext(), { wrapper });

      expect(typeof result.current.setMobileMenuOpen).toBe('function');
    });

    it('provides toggleMobileMenu function', () => {
      const wrapper = createWrapper(false);

      const { result } = renderHook(() => useSidebarContext(), { wrapper });

      expect(typeof result.current.toggleMobileMenu).toBe('function');
    });
  });

  describe('Error Handling', () => {
    it('throws error when used outside of context provider', () => {
      // Suppress console.error for this test since we expect an error
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      expect(() => {
        renderHook(() => useSidebarContext());
      }).toThrow('useSidebarContext must be used within Layout');

      consoleSpy.mockRestore();
    });

    it('error message references Layout component', () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      try {
        renderHook(() => useSidebarContext());
      } catch (error) {
        expect((error as Error).message).toContain('Layout');
      }

      consoleSpy.mockRestore();
    });
  });

  describe('State Management', () => {
    it('setMobileMenuOpen updates state to true', () => {
      function Wrapper({ children }: { children: ReactNode }) {
        const [isMobileMenuOpen, setMobileMenuOpen] = useState(false);

        const toggleMobileMenu = () => {
          setMobileMenuOpen((prev) => !prev);
        };

        const value: SidebarContextType = {
          isMobileMenuOpen,
          setMobileMenuOpen,
          toggleMobileMenu,
        };

        return <SidebarContext.Provider value={value}>{children}</SidebarContext.Provider>;
      }

      function TestComponent() {
        const { isMobileMenuOpen, setMobileMenuOpen } = useSidebarContext();
        return (
          <div>
            <span data-testid="state">{isMobileMenuOpen ? 'open' : 'closed'}</span>
            <button onClick={() => setMobileMenuOpen(true)} data-testid="open-btn">
              Open
            </button>
          </div>
        );
      }

      render(
        <Wrapper>
          <TestComponent />
        </Wrapper>
      );

      expect(screen.getByTestId('state')).toHaveTextContent('closed');

      fireEvent.click(screen.getByTestId('open-btn'));

      expect(screen.getByTestId('state')).toHaveTextContent('open');
    });

    it('setMobileMenuOpen updates state to false', () => {
      function Wrapper({ children }: { children: ReactNode }) {
        const [isMobileMenuOpen, setMobileMenuOpen] = useState(true);

        const toggleMobileMenu = () => {
          setMobileMenuOpen((prev) => !prev);
        };

        const value: SidebarContextType = {
          isMobileMenuOpen,
          setMobileMenuOpen,
          toggleMobileMenu,
        };

        return <SidebarContext.Provider value={value}>{children}</SidebarContext.Provider>;
      }

      function TestComponent() {
        const { isMobileMenuOpen, setMobileMenuOpen } = useSidebarContext();
        return (
          <div>
            <span data-testid="state">{isMobileMenuOpen ? 'open' : 'closed'}</span>
            <button onClick={() => setMobileMenuOpen(false)} data-testid="close-btn">
              Close
            </button>
          </div>
        );
      }

      render(
        <Wrapper>
          <TestComponent />
        </Wrapper>
      );

      expect(screen.getByTestId('state')).toHaveTextContent('open');

      fireEvent.click(screen.getByTestId('close-btn'));

      expect(screen.getByTestId('state')).toHaveTextContent('closed');
    });

    it('toggleMobileMenu toggles state from false to true', () => {
      function Wrapper({ children }: { children: ReactNode }) {
        const [isMobileMenuOpen, setMobileMenuOpen] = useState(false);

        const toggleMobileMenu = () => {
          setMobileMenuOpen((prev) => !prev);
        };

        const value: SidebarContextType = {
          isMobileMenuOpen,
          setMobileMenuOpen,
          toggleMobileMenu,
        };

        return <SidebarContext.Provider value={value}>{children}</SidebarContext.Provider>;
      }

      function TestComponent() {
        const { isMobileMenuOpen, toggleMobileMenu } = useSidebarContext();
        return (
          <div>
            <span data-testid="state">{isMobileMenuOpen ? 'open' : 'closed'}</span>
            <button onClick={toggleMobileMenu} data-testid="toggle-btn">
              Toggle
            </button>
          </div>
        );
      }

      render(
        <Wrapper>
          <TestComponent />
        </Wrapper>
      );

      expect(screen.getByTestId('state')).toHaveTextContent('closed');

      fireEvent.click(screen.getByTestId('toggle-btn'));

      expect(screen.getByTestId('state')).toHaveTextContent('open');
    });

    it('toggleMobileMenu toggles state from true to false', () => {
      function Wrapper({ children }: { children: ReactNode }) {
        const [isMobileMenuOpen, setMobileMenuOpen] = useState(true);

        const toggleMobileMenu = () => {
          setMobileMenuOpen((prev) => !prev);
        };

        const value: SidebarContextType = {
          isMobileMenuOpen,
          setMobileMenuOpen,
          toggleMobileMenu,
        };

        return <SidebarContext.Provider value={value}>{children}</SidebarContext.Provider>;
      }

      function TestComponent() {
        const { isMobileMenuOpen, toggleMobileMenu } = useSidebarContext();
        return (
          <div>
            <span data-testid="state">{isMobileMenuOpen ? 'open' : 'closed'}</span>
            <button onClick={toggleMobileMenu} data-testid="toggle-btn">
              Toggle
            </button>
          </div>
        );
      }

      render(
        <Wrapper>
          <TestComponent />
        </Wrapper>
      );

      expect(screen.getByTestId('state')).toHaveTextContent('open');

      fireEvent.click(screen.getByTestId('toggle-btn'));

      expect(screen.getByTestId('state')).toHaveTextContent('closed');
    });

    it('multiple toggles work correctly', () => {
      function Wrapper({ children }: { children: ReactNode }) {
        const [isMobileMenuOpen, setMobileMenuOpen] = useState(false);

        const toggleMobileMenu = () => {
          setMobileMenuOpen((prev) => !prev);
        };

        const value: SidebarContextType = {
          isMobileMenuOpen,
          setMobileMenuOpen,
          toggleMobileMenu,
        };

        return <SidebarContext.Provider value={value}>{children}</SidebarContext.Provider>;
      }

      function TestComponent() {
        const { isMobileMenuOpen, toggleMobileMenu } = useSidebarContext();
        return (
          <div>
            <span data-testid="state">{isMobileMenuOpen ? 'open' : 'closed'}</span>
            <button onClick={toggleMobileMenu} data-testid="toggle-btn">
              Toggle
            </button>
          </div>
        );
      }

      render(
        <Wrapper>
          <TestComponent />
        </Wrapper>
      );

      expect(screen.getByTestId('state')).toHaveTextContent('closed');

      // Toggle 1: closed -> open
      fireEvent.click(screen.getByTestId('toggle-btn'));
      expect(screen.getByTestId('state')).toHaveTextContent('open');

      // Toggle 2: open -> closed
      fireEvent.click(screen.getByTestId('toggle-btn'));
      expect(screen.getByTestId('state')).toHaveTextContent('closed');

      // Toggle 3: closed -> open
      fireEvent.click(screen.getByTestId('toggle-btn'));
      expect(screen.getByTestId('state')).toHaveTextContent('open');
    });
  });

  describe('Context Value Types', () => {
    it('isMobileMenuOpen is a boolean', () => {
      function Wrapper({ children }: { children: ReactNode }) {
        const value: SidebarContextType = {
          isMobileMenuOpen: false,
          setMobileMenuOpen: () => {},
          toggleMobileMenu: () => {},
        };

        return <SidebarContext.Provider value={value}>{children}</SidebarContext.Provider>;
      }

      const { result } = renderHook(() => useSidebarContext(), { wrapper: Wrapper });

      expect(typeof result.current.isMobileMenuOpen).toBe('boolean');
    });

    it('setMobileMenuOpen accepts boolean parameter', () => {
      const mockSetMobileMenuOpen = vi.fn();

      function Wrapper({ children }: { children: ReactNode }) {
        const value: SidebarContextType = {
          isMobileMenuOpen: false,
          setMobileMenuOpen: mockSetMobileMenuOpen,
          toggleMobileMenu: () => {},
        };

        return <SidebarContext.Provider value={value}>{children}</SidebarContext.Provider>;
      }

      function TestComponent() {
        const { setMobileMenuOpen } = useSidebarContext();
        return (
          <button onClick={() => setMobileMenuOpen(true)} data-testid="set-true">
            Set True
          </button>
        );
      }

      render(
        <Wrapper>
          <TestComponent />
        </Wrapper>
      );

      fireEvent.click(screen.getByTestId('set-true'));

      expect(mockSetMobileMenuOpen).toHaveBeenCalledWith(true);
    });

    it('toggleMobileMenu is callable as a function', () => {
      const mockToggleMobileMenu = vi.fn();

      function Wrapper({ children }: { children: ReactNode }) {
        const value: SidebarContextType = {
          isMobileMenuOpen: false,
          setMobileMenuOpen: () => {},
          toggleMobileMenu: mockToggleMobileMenu,
        };

        return <SidebarContext.Provider value={value}>{children}</SidebarContext.Provider>;
      }

      function TestComponent() {
        const { toggleMobileMenu } = useSidebarContext();
        return (
          <button onClick={() => toggleMobileMenu()} data-testid="toggle">
            Toggle
          </button>
        );
      }

      render(
        <Wrapper>
          <TestComponent />
        </Wrapper>
      );

      fireEvent.click(screen.getByTestId('toggle'));

      expect(mockToggleMobileMenu).toHaveBeenCalledTimes(1);
    });
  });

  describe('Multiple Consumers', () => {
    it('multiple consumers share the same state', () => {
      function Wrapper({ children }: { children: ReactNode }) {
        const [isMobileMenuOpen, setMobileMenuOpen] = useState(false);

        const toggleMobileMenu = () => {
          setMobileMenuOpen((prev) => !prev);
        };

        const value: SidebarContextType = {
          isMobileMenuOpen,
          setMobileMenuOpen,
          toggleMobileMenu,
        };

        return <SidebarContext.Provider value={value}>{children}</SidebarContext.Provider>;
      }

      function Consumer1() {
        const { isMobileMenuOpen, toggleMobileMenu } = useSidebarContext();
        return (
          <div>
            <span data-testid="consumer1-state">{isMobileMenuOpen ? 'open' : 'closed'}</span>
            <button onClick={toggleMobileMenu} data-testid="consumer1-toggle">
              Toggle from C1
            </button>
          </div>
        );
      }

      function Consumer2() {
        const { isMobileMenuOpen } = useSidebarContext();
        return (
          <span data-testid="consumer2-state">{isMobileMenuOpen ? 'open' : 'closed'}</span>
        );
      }

      render(
        <Wrapper>
          <Consumer1 />
          <Consumer2 />
        </Wrapper>
      );

      // Both consumers start with closed state
      expect(screen.getByTestId('consumer1-state')).toHaveTextContent('closed');
      expect(screen.getByTestId('consumer2-state')).toHaveTextContent('closed');

      // Toggle from Consumer1
      fireEvent.click(screen.getByTestId('consumer1-toggle'));

      // Both consumers should now show open
      expect(screen.getByTestId('consumer1-state')).toHaveTextContent('open');
      expect(screen.getByTestId('consumer2-state')).toHaveTextContent('open');
    });
  });

  describe('Context Default Value', () => {
    it('SidebarContext throws error when accessed outside provider', () => {
      // Verify the context throws when used outside provider
      // This indirectly confirms the default value is null
      const TestComponent = () => {
        useSidebarContext();
        return null;
      };

      // Suppress error output for cleaner test output
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      expect(() => {
        render(<TestComponent />);
      }).toThrow('useSidebarContext must be used within a Layout component');

      consoleSpy.mockRestore();
    });
  });
});
