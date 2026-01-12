import { useCallback, useMemo } from 'react';

import {
  useRateLimitContext,
  type EndpointRateLimitInfo,
  type RateLimitUpdateInput,
} from '../contexts/RateLimitContext';

export interface UseRateLimitReturn {
  rateLimit: EndpointRateLimitInfo | undefined;
  isLimited: boolean;
  remaining: number | undefined;
  limit: number | undefined;
  resetAt: Date | undefined;
  update: (info: RateLimitUpdateInput) => void;
  clear: () => void;
}

export function useRateLimit(endpoint: string): UseRateLimitReturn {
  const { getRateLimit, updateRateLimit, clearRateLimit, isEndpointLimited } =
    useRateLimitContext();

  const rateLimit = getRateLimit(endpoint);
  const isLimited = isEndpointLimited(endpoint);

  const update = useCallback(
    (info: RateLimitUpdateInput) => {
      updateRateLimit(endpoint, info);
    },
    [updateRateLimit, endpoint]
  );

  const clear = useCallback(() => {
    clearRateLimit(endpoint);
  }, [clearRateLimit, endpoint]);

  return useMemo<UseRateLimitReturn>(
    () => ({
      rateLimit,
      isLimited,
      remaining: rateLimit?.remaining,
      limit: rateLimit?.limit,
      resetAt: rateLimit?.resetAt,
      update,
      clear,
    }),
    [rateLimit, isLimited, update, clear]
  );
}
