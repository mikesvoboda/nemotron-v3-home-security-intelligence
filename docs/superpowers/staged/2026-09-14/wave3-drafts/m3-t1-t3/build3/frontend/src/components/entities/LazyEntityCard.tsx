import { memo, useEffect, useRef, useState } from 'react';

import EntityCard, { type EntityCardProps } from './EntityCard';
import { EntityCardSkeleton } from '../common';

/**
 * LazyEntityCard component - Renders EntityCard lazily using Intersection Observer
 *
 * This component shows a skeleton placeholder until the card comes into view,
 * improving initial render performance when displaying many entity cards.
 * Once the card becomes visible, it loads and renders the full EntityCard.
 * The observer disconnects after first visibility to avoid unnecessary re-renders.
 *
 * @param props - Same props as EntityCard, passed through to the underlying component
 */
const LazyEntityCard = memo(function LazyEntityCard(props: EntityCardProps) {
  const [isVisible, setIsVisible] = useState(false);
  const cardRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const currentRef = cardRef.current;

    // If IntersectionObserver is not supported, render immediately
    if (!currentRef || typeof IntersectionObserver === 'undefined') {
      setIsVisible(true);
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
          observer.disconnect();
        }
      },
      {
        // Load cards slightly before they enter viewport for smoother scrolling
        rootMargin: '100px',
        // Trigger as soon as any part of the element is visible
        threshold: 0,
      }
    );

    observer.observe(currentRef);

    return () => {
      observer.disconnect();
    };
  }, []);

  return (
    <div ref={cardRef} data-testid="lazy-entity-card-wrapper">
      {isVisible ? <EntityCard {...props} /> : <EntityCardSkeleton />}
    </div>
  );
});

export default LazyEntityCard;
