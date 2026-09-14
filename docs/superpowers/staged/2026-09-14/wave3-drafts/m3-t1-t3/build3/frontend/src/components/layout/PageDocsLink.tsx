import { BookOpen } from 'lucide-react';
import { useLocation } from 'react-router-dom';

import { PAGE_DOCUMENTATION } from '../../config/pageDocumentation';

const GITHUB_BASE_URL =
  'https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence/blob/main/';

/**
 * Renders a contextual documentation link based on the current route.
 * The link text and destination change as the user navigates between pages.
 *
 * Returns null for routes without configured documentation.
 */
export function PageDocsLink() {
  const { pathname } = useLocation();
  const pageDoc = PAGE_DOCUMENTATION[pathname];

  // Don't render if no docs configured for this page
  if (!pageDoc) {
    return null;
  }

  const url = `${GITHUB_BASE_URL}${pageDoc.docPath}`;

  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium text-[#76B900] transition-colors hover:bg-[#76B900]/20 hover:text-white"
      title={pageDoc.description}
    >
      <BookOpen className="h-4 w-4" aria-hidden="true" />
      <span className="hidden sm:inline">{pageDoc.label} Documentation</span>
      <span className="sm:hidden">Docs</span>
    </a>
  );
}
