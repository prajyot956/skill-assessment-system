import { lazy, Suspense } from 'react'
import { BrowserRouter, Navigate, Outlet, Route, Routes } from 'react-router-dom'
import { AppLayout } from './layouts/AppLayout'
import { useAuth } from './context/AuthContext'
import { Skeleton } from './components/ui'
import { ForgotPasswordPage, LoginPage, RegisterPage, ResetPasswordPage } from './pages/AuthPages'

const DashboardPage = lazy(() => import('./pages/DashboardPage').then((m) => ({ default: m.DashboardPage })))
const ProfilePage = lazy(() => import('./pages/ProfilePage').then((m) => ({ default: m.ProfilePage })))
const SettingsPage = lazy(() => import('./pages/SettingsPage').then((m) => ({ default: m.SettingsPage })))
const ResumePage = lazy(() => import('./pages/ResumePage').then((m) => ({ default: m.ResumePage })))
const ResumeReviewPage = lazy(() => import('./pages/ResumeReviewPage').then((m) => ({ default: m.ResumeReviewPage })))
const AssessmentsPage = lazy(() => import('./pages/AssessmentsPage').then((m) => ({ default: m.AssessmentsPage })))
const AttemptPage = lazy(() => import('./pages/AttemptPage').then((m) => ({ default: m.AttemptPage })))
const ResultPage = lazy(() => import('./pages/ResultPage').then((m) => ({ default: m.ResultPage })))
const HistoryPage = lazy(() => import('./pages/HistoryPage').then((m) => ({ default: m.HistoryPage })))
const AnalysisPage = lazy(() => import('./pages/AnalysisPage').then((m) => ({ default: m.AnalysisPage })))
const CareersPage = lazy(() => import('./pages/CareersPage').then((m) => ({ default: m.CareersPage })))
const RoadmapPage = lazy(() => import('./pages/RoadmapPage').then((m) => ({ default: m.RoadmapPage })))
const PracticePage = lazy(() => import('./pages/PracticePage').then((m) => ({ default: m.PracticePage })))
const AdminPage = lazy(() => import('./pages/AdminPage').then((m) => ({ default: m.AdminPage })))

function Splash() {
  return <div className="grid min-h-screen place-items-center" aria-busy="true" aria-label="Loading"><Skeleton className="h-10 w-10 rounded-full" /></div>
}

function Protected() {
  const { user, loading } = useAuth()
  if (loading) return <Splash />
  return user ? <AppLayout /> : <Navigate to="/login" replace />
}

function AdminOnly() {
  const { user } = useAuth()
  return user?.is_admin ? <Outlet /> : <Navigate to="/" replace />  // the server enforces this too; this only avoids a dead page
}

function PublicOnly() {
  const { user, loading } = useAuth()
  if (loading) return <Splash />
  return user ? <Navigate to="/" replace /> : <Outlet />
}

export default function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<Splash />}>
      <Routes>
        <Route element={<PublicOnly />}>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
        </Route>
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route element={<Protected />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/resume" element={<ResumePage />} />
          <Route path="/resume/review/:id" element={<ResumeReviewPage />} />
          <Route path="/assessments" element={<AssessmentsPage />} />
          <Route path="/assessments/attempt/:id" element={<AttemptPage />} />
          <Route path="/assessments/results/:id" element={<ResultPage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/analysis" element={<AnalysisPage />} />
          <Route path="/careers" element={<CareersPage />} />
          <Route path="/roadmap" element={<RoadmapPage />} />
          <Route path="/practice" element={<PracticePage />} />
          <Route element={<AdminOnly />}><Route path="/admin" element={<AdminPage />} /></Route>
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      </Suspense>
    </BrowserRouter>
  )
}
