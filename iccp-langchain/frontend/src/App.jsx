import { Navigate, Route, Routes } from 'react-router-dom'
import AppShell from './layouts/AppShell'
import DashboardPage from './pages/DashboardPage'
import WorkspaceChatPage from './pages/WorkspaceChatPage'
import WorkspaceContentPage from './pages/WorkspaceContentPage'
import KnowledgeBasePage from './pages/KnowledgeBasePage'
import ModelComparePage from './pages/ModelComparePage'
import CoverPage from './pages/CoverPage'
import StoryVideoPage from './pages/StoryVideoPage'
import AuthPage from './pages/AuthPage'
import MemoryDebugPage from './pages/MemoryDebugPage'
import RequireAuth from './components/RequireAuth'

function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/chat" element={<WorkspaceChatPage />} />
        <Route path="/writing" element={<WorkspaceContentPage />} />
        <Route path="/cover" element={<CoverPage />} />
        <Route path="/video" element={<StoryVideoPage />} />
        <Route path="/knowledge" element={<KnowledgeBasePage />} />
        <Route path="/auth" element={<AuthPage />} />
        <Route
          path="/model-compare"
          element={
            <RequireAuth requiredRole="admin">
              <ModelComparePage />
            </RequireAuth>
          }
        />
        <Route
          path="/memory"
          element={
            <RequireAuth requiredRole="admin">
              <MemoryDebugPage />
            </RequireAuth>
          }
        />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Route>
    </Routes>
  )
}

export default App
