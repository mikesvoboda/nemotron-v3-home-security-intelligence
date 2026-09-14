/**
 * NotFoundPage - 404 error page component
 *
 * Displays a user-friendly 404 error page when users navigate to
 * an unknown route. Styled with NVIDIA dark theme and green accents.
 *
 * Features:
 * - Clear 404 error indication
 * - Descriptive message
 * - Return to Dashboard button
 * - NVIDIA dark theme (#76B900 accents)
 * - Accessible heading structure
 *
 * @module pages/NotFoundPage
 */

import { Home } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import Button from '../components/common/Button';

/**
 * NotFoundPage displays when users navigate to a route that doesn't exist.
 * Provides a clear indication of the error and a way to return to the dashboard.
 */
export default function NotFoundPage() {
  const navigate = useNavigate();

  const handleReturnToDashboard = () => {
    void navigate('/');
  };

  return (
    <div
      className="flex min-h-[60vh] flex-col items-center justify-center px-4 py-12 text-center"
      data-testid="not-found-page"
    >
      {/* Error Code */}
      <p className="mb-4 text-8xl font-bold text-[#76B900]">404</p>

      {/* Title */}
      <h1 className="mb-4 text-2xl font-semibold text-white md:text-3xl">Page Not Found</h1>

      {/* Description */}
      <p className="mb-8 max-w-md text-gray-400">
        The page you are looking for does not exist. It may have been moved, deleted, or you may
        have mistyped the URL.
      </p>

      {/* Return to Dashboard Button */}
      <Button
        variant="primary"
        size="lg"
        leftIcon={<Home className="h-5 w-5" />}
        onClick={handleReturnToDashboard}
      >
        Return to Dashboard
      </Button>
    </div>
  );
}
