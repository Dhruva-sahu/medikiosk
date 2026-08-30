import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from './hooks/useAuth';
import LoginPage from './pages/auth/LoginPage';
import KioskPage from './pages/kiosk/KioskPage';
import ClinicianDashboard from './pages/clinician/Dashboard';
import CaseDetail from './pages/clinician/CaseDetail';

const queryClient = new QueryClient();

function ProtectedRoute({ children, allowedRoles }: { children: React.ReactNode; allowedRoles?: string[] }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-center">
          <div className="w-8 h-8 border-4 border-brand-500 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-slate-500 mt-3">Loading...</p>
        </div>
      </div>
    );
  }

  if (!user) return <Navigate to="/login" replace />;
  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return <Navigate to={user.role === 'PATIENT' ? '/kiosk' : '/clinician'} replace />;
  }

  return <>{children}</>;
}

function RootRedirect() {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;
  return <Navigate to={user.role === 'PATIENT' ? '/kiosk' : '/clinician'} replace />;
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            {/* Public routes */}
            <Route path="/login" element={<LoginPage />} />
            <Route path="/" element={<RootRedirect />} />

            {/* Patient kiosk routes */}
            <Route
              path="/kiosk"
              element={
                <ProtectedRoute allowedRoles={['PATIENT']}>
                  <KioskPage />
                </ProtectedRoute>
              }
            />

            {/* Clinician routes */}
            <Route
              path="/clinician"
              element={
                <ProtectedRoute allowedRoles={['CLINICIAN', 'ADMIN']}>
                  <ClinicianDashboard />
                </ProtectedRoute>
              }
            />
            <Route
              path="/clinician/case/:sessionId"
              element={
                <ProtectedRoute allowedRoles={['CLINICIAN', 'ADMIN']}>
                  <CaseDetail />
                </ProtectedRoute>
              }
            />

            {/* Catch-all */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}

export default App;
