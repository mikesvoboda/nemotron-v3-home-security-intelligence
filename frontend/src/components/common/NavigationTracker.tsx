/**
 * NavigationTracker - Invisible component that tracks route navigation.
 *
 * Listens to route changes and logs navigation events for analytics
 * and debugging purposes. Should be placed inside the BrowserRouter.
 *
 * @example
 * ```tsx
 * <BrowserRouter>
 *   <NavigationTracker />
 *   <Routes>...</Routes>
 * </BrowserRouter>
 * ```
 */
import { useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';

import { logger } from '../../services/logger';

/**
 * NavigationTracker component that logs route changes.
 *
 * This component renders nothing (null) but uses the router's
 * location to track navigation between pages.
 */
export function NavigationTracker(): null {
  const location = useLocation();
  const prevPathRef = useRef<string>(location.pathname);
  const isFirstRender = useRef(true);

  useEffect(() => {
    // Skip the first render to avoid logging initial page load
    // (that's already captured in the URL extra field of other logs)
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }

    const currentPath = location.pathname;
    const prevPath = prevPathRef.current;

    if (prevPath !== currentPath) {
      logger.navigate(prevPath, currentPath, {
        search: location.search || undefined,
        hash: location.hash || undefined,
      });
      prevPathRef.current = currentPath;
    }
  }, [location.pathname, location.search, location.hash]);

  return null;
}

export default NavigationTracker;
