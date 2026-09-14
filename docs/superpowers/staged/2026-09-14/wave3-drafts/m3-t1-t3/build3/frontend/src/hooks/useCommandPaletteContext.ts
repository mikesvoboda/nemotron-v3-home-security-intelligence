import { createContext, useContext } from 'react';

/**
 * Context for Command Palette state
 *
 * Allows child components (like Header) to trigger the command palette.
 */
export interface CommandPaletteContextType {
  /** Open the command palette */
  openCommandPalette: () => void;
}

export const CommandPaletteContext = createContext<CommandPaletteContextType | null>(null);

/**
 * Hook to access command palette controls
 *
 * Must be used within a component wrapped by CommandPaletteContext.Provider
 * (provided by Layout component)
 */
export function useCommandPaletteContext() {
  const context = useContext(CommandPaletteContext);
  if (!context) {
    throw new Error('useCommandPaletteContext must be used within Layout');
  }
  return context;
}
