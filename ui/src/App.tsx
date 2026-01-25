import { Routes, Route, Navigate } from 'react-router-dom'
import { ChatProvider } from './contexts/ChatContext'
import { AuthProvider } from './contexts/AuthContext'
import { ProfileProvider } from './profile'
import AppShell from './layouts/AppShell'
import ChatPage from './pages/ChatPage'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import SettingsPage from './pages/SettingsPage'
import AdminLayout from './pages/admin/AdminLayout'
import AdminDashboard from './pages/admin/AdminDashboard'
import AdminUsers from './pages/admin/AdminUsers'
import AdminSessions from './pages/admin/AdminSessions'
import RequireAdmin from './pages/admin/RequireAdmin'

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        {/* Login page - no ProfileProvider, no AppShell */}
        <Route path="/login" element={<LoginPage />} />
        
        {/* Protected routes with ProfileProvider and AppShell */}
        <Route
          element={
            <ProfileProvider>
              <ChatProvider>
                <AppShell />
              </ChatProvider>
            </ProfileProvider>
          }
        >
          <Route path="/" element={<ChatPage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/settings/*" element={<SettingsPage />} />
          <Route
            path="/admin"
            element={
              <RequireAdmin>
                <AdminLayout />
              </RequireAdmin>
            }
          >
            <Route index element={<AdminDashboard />} />
            <Route path="dashboard" element={<AdminDashboard />} />
            <Route path="users" element={<AdminUsers />} />
            <Route path="sessions" element={<AdminSessions />} />
          </Route>
        </Route>
        
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  )
}
