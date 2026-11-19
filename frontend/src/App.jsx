import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { homeFor, useAuth } from './auth'
import Layout from './components/Layout'
import { Spinner } from './components/ui'
import AdminIncident from './pages/admin/AdminIncident'
import AdminOverview from './pages/admin/AdminOverview'
import Policies from './pages/admin/Policies'
import Users from './pages/admin/Users'
import IncidentDetail from './pages/IncidentDetail'
import IncidentList from './pages/IncidentList'
import Login from './pages/Login'
import NewIncident from './pages/NewIncident'

const Dashboard = lazy(() => import('./pages/Dashboard')) // charts load only when opened

function RequireAuth({ roles, children }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return <Spinner />
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  if (roles && !roles.includes(user.role)) return <Navigate to={homeFor(user.role)} replace />
  return children
}

export default function App() {
  const { user } = useAuth()
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<RequireAuth><Layout /></RequireAuth>}>
        <Route path="/" element={<Navigate to={user ? homeFor(user.role) : '/login'} replace />} />
        <Route path="/report/new" element={<NewIncident />} />
        <Route path="/incidents" element={<IncidentList />} />
        <Route path="/incidents/:id" element={<IncidentDetail />} />
        <Route path="/dashboard" element={<RequireAuth roles={['safety_officer', 'admin']}><Suspense fallback={<Spinner />}><Dashboard /></Suspense></RequireAuth>} />
        <Route path="/admin" element={<RequireAuth roles={['admin']}><AdminOverview /></RequireAuth>} />
        <Route path="/admin/incidents/:id" element={<RequireAuth roles={['admin']}><AdminIncident /></RequireAuth>} />
        <Route path="/admin/users" element={<RequireAuth roles={['admin']}><Users /></RequireAuth>} />
        <Route path="/policies" element={<RequireAuth roles={['safety_officer', 'admin']}><Policies /></RequireAuth>} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
