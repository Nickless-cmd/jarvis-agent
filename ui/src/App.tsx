import { Routes, Route, Navigate } from 'react-router-dom'
import { ChatProvider } from './contexts/ChatContext'
import AppShell from './layouts/AppShell'
import ChatPage from './pages/ChatPage'
import AdminPage from './pages/AdminPage'

export default function App() {
  return (
    <ChatProvider>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/" element={<ChatPage />} />
          <Route path="/admin/*" element={<AdminPage />} />
          <Route path="/settings/*" element={<ChatPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </ChatProvider>
  )
}
