import { useState } from 'react';

import DashboardPage from './components/dashboard/DashboardPage';
import Layout from './components/layout/Layout';
import LogsDashboard from './components/logs/LogsDashboard';

export default function App() {
  const [currentPath, setCurrentPath] = useState(window.location.pathname);

  // Listen to navigation changes
  const handleNavChange = (path: string) => {
    setCurrentPath(path);
    window.history.pushState({}, '', path);
  };

  // Render content based on current path
  const renderContent = () => {
    switch (currentPath) {
      case '/logs':
        return <LogsDashboard />;
      case '/':
      default:
        return <DashboardPage />;
    }
  };

  return (
    <Layout onNavChange={handleNavChange}>
      {renderContent()}
    </Layout>
  );
}
