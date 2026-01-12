/* eslint-disable react-refresh/only-export-components */
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

export interface EndpointRateLimitInfo {
  limit: number;
  remaining: number;
  resetAt: Date;
  isLimited: boolean;
}

export interface RateLimitUpdateInput {
  limit: number;
  remaining: number;
  resetAt: Date;
}

export interface RateLimitState {
  [endpoint: string]: EndpointRateLimitInfo;
}

export interface RateLimitContextType {
  rateLimits: RateLimitState;
  updateRateLimit: (endpoint: string, info: RateLimitUpdateInput) => void;
  getRateLimit: (endpoint: string) => EndpointRateLimitInfo | undefined;
  clearRateLimit: (endpoint: string) => void;
  clearAllRateLimits: () => void;
  isEndpointLimited: (endpoint: string) => boolean;
  isAnyEndpointLimited: () => boolean;
  getLimitedEndpoints: () => string[];
}

export const RateLimitContext = createContext<RateLimitContextType | null>(null);

export interface RateLimitProviderProps {
  children: ReactNode;
}

export function RateLimitProvider({ children }: RateLimitProviderProps) {
  const [rateLimits, setRateLimits] = useState<RateLimitState>({});

  const updateRateLimit = useCallback(
    (endpoint: string, info: RateLimitUpdateInput) => {
      setRateLimits((prev) => ({
        ...prev,
        [endpoint]: { ...info, isLimited: info.remaining === 0 },
      }));
    },
    []
  );

  const getRateLimit = useCallback(
    (endpoint: string) => rateLimits[endpoint],
    [rateLimits]
  );

  const clearRateLimit = useCallback((endpoint: string) => {
    setRateLimits((prev) => {
      const { [endpoint]: _, ...rest } = prev;
      return rest;
    });
  }, []);

  const clearAllRateLimits = useCallback(() => {
    setRateLimits({});
  }, []);

  const isEndpointLimited = useCallback(
    (endpoint: string) => rateLimits[endpoint]?.isLimited ?? false,
    [rateLimits]
  );

  const isAnyEndpointLimited = useCallback(
    () => Object.values(rateLimits).some((info) => info.isLimited),
    [rateLimits]
  );

  const getLimitedEndpoints = useCallback(
    () =>
      Object.entries(rateLimits)
        .filter(([, info]) => info.isLimited)
        .map(([endpoint]) => endpoint),
    [rateLimits]
  );

  const contextValue = useMemo<RateLimitContextType>(
    () => ({
      rateLimits,
      updateRateLimit,
      getRateLimit,
      clearRateLimit,
      clearAllRateLimits,
      isEndpointLimited,
      isAnyEndpointLimited,
      getLimitedEndpoints,
    }),
    [
      rateLimits,
      updateRateLimit,
      getRateLimit,
      clearRateLimit,
      clearAllRateLimits,
      isEndpointLimited,
      isAnyEndpointLimited,
      getLimitedEndpoints,
    ]
  );

  return (
    <RateLimitContext.Provider value={contextValue}>
      {children}
    </RateLimitContext.Provider>
  );
}

export function useRateLimitContext(): RateLimitContextType {
  const context = useContext(RateLimitContext);
  if (!context) {
    throw new Error(
      'useRateLimitContext must be used within a RateLimitProvider'
    );
  }
  return context;
}
