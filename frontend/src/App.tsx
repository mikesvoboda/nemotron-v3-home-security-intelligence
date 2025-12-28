import { BrowserRouter, Routes, Route } from 'react-router-dom';

import AlertsPage from './components/alerts/AlertsPage';
import DashboardPage from './components/dashboard/DashboardPage';
import EntitiesPage from './components/entities/EntitiesPage';
import EventTimeline from './components/events/EventTimeline';
import Layout from './components/layout/Layout';
import LogsDashboard from './components/logs/LogsDashboard';
import SettingsPage from './components/settings/SettingsPage';
import { SystemMonitoringPage } from './components/system';

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/timeline" element={<EventTimeline />} />
          <Route path="/alerts" element={<AlertsPage />} />
          <Route path="/entities" element={<EntitiesPage />} />
          <Route path="/logs" element={<LogsDashboard />} />
          <Route path="/system" element={<SystemMonitoringPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}
