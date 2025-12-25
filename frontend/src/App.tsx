import { BrowserRouter, Routes, Route } from 'react-router-dom';

import DashboardPage from './components/dashboard/DashboardPage';
import EventTimeline from './components/events/EventTimeline';
import Layout from './components/layout/Layout';
import LogsDashboard from './components/logs/LogsDashboard';
import SettingsPage from './components/settings/SettingsPage';

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/timeline" element={<EventTimeline />} />
          <Route path="/logs" element={<LogsDashboard />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}
