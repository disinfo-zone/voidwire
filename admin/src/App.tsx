import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import ReadingsPage from './pages/ReadingsPage';
import SourcesPage from './pages/SourcesPage';
import TemplatesPage from './pages/TemplatesPage';
import DictionaryPage from './pages/DictionaryPage';
import SettingsPage from './pages/SettingsPage';
import PipelinePage from './pages/PipelinePage';
import EventsPage from './pages/EventsPage';
import AuditPage from './pages/AuditPage';
import LLMConfigPage from './pages/LLMConfigPage';
import ThreadsPage from './pages/ThreadsPage';
import SignalsPage from './pages/SignalsPage';
import BackupPage from './pages/BackupPage';
import SetupWizardPage from './pages/SetupWizardPage';
import ContentPage from './pages/ContentPage';
import { useAuth } from './hooks/useAuth';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { token } = useAuth();
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <BrowserRouter basename="/admin">
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/setup" element={<SetupWizardPage />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route index element={<DashboardPage />} />
          <Route path="readings" element={<ReadingsPage />} />
          <Route path="sources" element={<SourcesPage />} />
          <Route path="templates" element={<TemplatesPage />} />
          <Route path="dictionary" element={<DictionaryPage />} />
          <Route path="pipeline" element={<PipelinePage />} />
          <Route path="events" element={<EventsPage />} />
          <Route path="threads" element={<ThreadsPage />} />
          <Route path="signals" element={<SignalsPage />} />
          <Route path="llm" element={<LLMConfigPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="content" element={<ContentPage />} />
          <Route path="backup" element={<BackupPage />} />
          <Route path="audit" element={<AuditPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
