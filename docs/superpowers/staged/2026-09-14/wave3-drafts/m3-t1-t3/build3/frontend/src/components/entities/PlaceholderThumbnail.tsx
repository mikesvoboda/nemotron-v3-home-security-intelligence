import { Car, HelpCircle, User } from 'lucide-react';
import { memo } from 'react';

export interface PlaceholderThumbnailProps {
  /** Entity type to determine which silhouette icon to display */
  entityType: string;
  /** Optional additional CSS classes */
  className?: string;
}

/**
 * PlaceholderThumbnail component displays a silhouette icon for entities
 * when a thumbnail image is missing or fails to load.
 *
 * - Person entities: User icon silhouette
 * - Vehicle entities: Car icon silhouette
 * - Unknown/other entities: HelpCircle icon silhouette
 */
const PlaceholderThumbnail = memo(function PlaceholderThumbnail({
  entityType,
  className = '',
}: PlaceholderThumbnailProps) {
  // Determine which icon to render based on entity type
  const renderIcon = () => {
    switch (entityType) {
      case 'person':
        return <User className="lucide-user h-16 w-16" />;
      case 'vehicle':
        return <Car className="lucide-car h-16 w-16" />;
      default:
        return <HelpCircle className="lucide-help-circle h-16 w-16" />;
    }
  };

  return (
    <div
      data-testid="placeholder-thumbnail"
      className={`flex h-full w-full items-center justify-center text-gray-600 ${className}`}
    >
      {renderIcon()}
    </div>
  );
});

export default PlaceholderThumbnail;
