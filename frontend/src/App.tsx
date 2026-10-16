import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './auth'
import { Layout } from './components/Layout'
import { Login } from './pages/Login'
import { ClinicDashboard } from './pages/ClinicDashboard'
import { Claims } from './pages/Claims'
import { ClaimPage } from './pages/ClaimDetail'
import { UploadPage } from './pages/Upload'
import { Requests } from './pages/Requests'
import { Statements } from './pages/Statements'
import { Team } from './pages/Team'
import { AccessLog } from './pages/AccessLog'
import { SettingsPage } from './pages/Settings'
import { OpsOverview } from './pages/OpsOverview'
import { ReviewQueue } from './pages/ReviewQueue'
import { Deadlines } from './pages/Deadlines'
import { Practices } from './pages/Practices'
import { Analytics } from './pages/Analytics'
import { ForcePasswordChange } from './pages/Settings'

export default function App() {
  const { user, isOps } = useAuth()
  if (!user) return <Login />
  if (user.must_change_password) return <ForcePasswordChange />

  const admin = user.role === 'ops_admin'
  const clinicAdmin = user.role === 'clinic_admin'

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={isOps ? (admin ? <OpsOverview /> : <Navigate to="/review" replace />) : <ClinicDashboard />} />
        <Route path="claims" element={<Claims />} />
        <Route path="claims/:id" element={<ClaimPage />} />
        <Route path="statements" element={<Statements />} />
        <Route path="settings" element={<SettingsPage />} />
        {!isOps && <Route path="upload" element={<UploadPage />} />}
        {!isOps && <Route path="requests" element={<Requests />} />}
        {isOps && <Route path="review" element={<ReviewQueue />} />}
        {isOps && <Route path="deadlines" element={<Deadlines />} />}
        {admin && <Route path="practices" element={<Practices />} />}
        {admin && <Route path="analytics" element={<Analytics />} />}
        {(admin || clinicAdmin) && <Route path="team" element={<Team />} />}
        {(admin || clinicAdmin) && <Route path="audit" element={<AccessLog />} />}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
