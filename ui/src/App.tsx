import { Routes, Route, Navigate } from 'react-router-dom'
import { ChatProvider } from './contexts/ChatContext'
import AppShell from './layouts/AppShell'
import ChatPage from './pages/ChatPage'
import AdminLayout from './pages/admin/AdminLayout'
import AdminDashboard from './pages/admin/AdminDashboard'
import AdminUsers from './pages/admin/AdminUsers'
import AdminSessions from './pages/admin/AdminSessions'
import RequireAdmin from './pages/admin/RequireAdmin'

export default function App() {
  return (
    <ChatProvider>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/" element={<ChatPage />} />
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
          <Route path="/settings/*" element={<ChatPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </ChatProvider>
  )
}
