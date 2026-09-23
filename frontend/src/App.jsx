import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import ProtectedRoute from './components/ProtectedRoute'
import { AuthProvider } from './context/AuthContext'
import { ThemeProvider } from './context/ThemeContext'
import ChatPage from './pages/ChatPage'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'

const App = () => {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            {/* Public routes */}
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />

            {/* Protected chat route */}
            <Route
              path="/chat"
              element={
                <ProtectedRoute>
                  <ChatPage />
                </ProtectedRoute>
              }
            />

            {/* Redirect root → /chat (ProtectedRoute will bounce to /login if unauth) */}
            <Route path="/" element={<Navigate to="/chat" replace />} />

            {/* Catch-all */}
            <Route path="*" element={<Navigate to="/chat" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  )
}

export default App
