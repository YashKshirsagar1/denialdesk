import { useState } from 'react'
import { clearToken, getCurrentUser, isLoggedIn } from './auth'
import { ClinicPortal } from './components/ClinicPortal'
import { LoginPage } from './components/LoginPage'
import { OpsConsole } from './components/OpsConsole'

export default function App() {
  const [loggedIn, setLoggedIn] = useState(isLoggedIn())

  function handleLogout() {
    clearToken()
    setLoggedIn(false)
  }

  if (!loggedIn) {
    return <LoginPage onLogin={() => setLoggedIn(true)} />
  }

  const user = getCurrentUser()
  if (!user) {
    clearToken()
    return <LoginPage onLogin={() => setLoggedIn(true)} />
  }

  if (user.role === 'clinic_admin' || user.role === 'clinic_staff') {
    return <ClinicPortal onLogout={handleLogout} />
  }

  return <OpsConsole onLogout={handleLogout} />
}
