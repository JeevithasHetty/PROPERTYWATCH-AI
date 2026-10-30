import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Navbar from './components/Navbar';
import Sidebar from './components/Sidebar';

import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import PropertyInventoryPage from './pages/PropertyInventoryPage';
import PropertyRegistrationPage from './pages/PropertyRegistrationPage';
import PropertyDetailPage from './pages/PropertyDetailPage';
import SatelliteMonitoringPage from './pages/SatelliteMonitoringPage';
import ImageComparisonPage from './pages/ImageComparisonPage';
import ModificationAlertsPage from './pages/ModificationAlertsPage';
import ReviewerWorkspacePage from './pages/ReviewerWorkspacePage';
import ChronologicalHistoryPage from './pages/ChronologicalHistoryPage';
import ReportsPage from './pages/ReportsPage';
import SettingsPage from './pages/SettingsPage';
import ClaimsPage from './pages/ClaimsPage';

// Layout wrapper for authenticated pages
const AppLayout = () => {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#070b14', color: '#94a3b8' }}>
        <div className="animate-spin" style={{ display: 'inline-block', width: '32px', height: '32px', border: '3px solid #22a866', borderTopColor: 'transparent', borderRadius: '50%', marginBottom: '16px' }} />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="app-container">
      <Sidebar />
      <div className="main-content">
        <Navbar />
        <main className="page-wrapper">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />

          {/* Protected Application Routes */}
          <Route element={<AppLayout />}>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/properties" element={<PropertyInventoryPage />} />
            <Route path="/properties/new" element={<PropertyRegistrationPage />} />
            <Route path="/properties/:id" element={<PropertyDetailPage />} />
            <Route path="/satellite" element={<SatelliteMonitoringPage />} />
            <Route path="/analysis" element={<ImageComparisonPage />} />
            <Route path="/modifications" element={<ModificationAlertsPage />} />
            <Route path="/claims" element={<ClaimsPage />} />
            <Route path="/reviews" element={<ReviewerWorkspacePage />} />
            <Route path="/history" element={<ChronologicalHistoryPage />} />
            <Route path="/reports" element={<ReportsPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Route>

          {/* Fallback */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
