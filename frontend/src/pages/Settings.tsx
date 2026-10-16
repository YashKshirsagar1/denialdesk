import { useState, type FormEvent } from 'react'
import { CheckCircle2, Circle } from 'lucide-react'
import { changePassword, getOnboardingStatus } from '../api'
import { useAuth } from '../auth'
import { ROLE_LABELS } from '../lib/format'
import { Alert, PageHead, Spinner, useAsync, useToast } from '../components/ui'

function PasswordForm({ onDone, forced }: { onDone: () => void; forced?: boolean }) {
  const [cur, setCur] = useState('')
  const [next, setNext] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true); setErr(null)
    try { await changePassword(cur, next); setCur(''); setNext(''); onDone() }
    catch (e2) { setErr((e2 as Error).message) } finally { setBusy(false) }
  }
  return (
    <form className="stack" onSubmit={submit} style={{ maxWidth: 380 }}>
      {err && <Alert kind="error">{err}</Alert>}
      <label className="field">{forced ? 'Temporary password' : 'Current password'}
        <input type="password" value={cur} onChange={(e) => setCur(e.target.value)} required autoComplete="current-password" /></label>
      <label className="field">New password
        <input type="password" value={next} onChange={(e) => setNext(e.target.value)} required autoComplete="new-password" />
        <span className="help">At least 10 characters, with upper and lower case and a number.</span></label>
      <button className="btn primary" style={{ width: 'fit-content' }} disabled={busy}>{busy ? <Spinner /> : 'Update password'}</button>
    </form>
  )
}

export function ForcePasswordChange() {
  const { updateUser, signOut } = useAuth()
  return (
    <div className="auth-form-wrap" style={{ minHeight: '100%' }}>
      <div className="card card-body stack" style={{ maxWidth: 460 }}>
        <h2>Choose a new password</h2>
        <p className="muted">Your account was created with a temporary password. Set your own to continue.</p>
        <PasswordForm forced onDone={() => updateUser({ must_change_password: false })} />
        <button className="link-btn" style={{ width: 'fit-content' }} onClick={() => signOut()}>Sign out</button>
      </div>
    </div>
  )
}

export function SettingsPage() {
  const { user, isClinic } = useAuth()
  const toast = useToast()
  const onboarding = useAsync(() => (isClinic ? getOnboardingStatus() : Promise.resolve(null)), [isClinic])
  if (!user) return null
  const o = onboarding.data
  const steps = o ? [
    ['Business Associate Agreement signed', o.checklist.baa_signed],
    ['Service agreement signed', o.checklist.service_agreement_signed],
    ['Practice details (address, phone, NPI)', o.checklist.practice_details],
    ['Specialties added', o.checklist.specialties],
    ['Payers you bill added', o.checklist.payers_billed],
    ['Payer-portal access delegated to our staff', o.checklist.payer_portal_access],
  ] as const : []

  return (
    <>
      <PageHead title="Settings" />
      <div className="grid cols-2" style={{ alignItems: 'start' }}>
        <div className="stack">
          <div className="card">
            <div className="card-head"><h3>Profile</h3></div>
            <div className="card-body"><dl className="kv">
              <dt>Name</dt><dd>{user.full_name}</dd><dt>Email</dt><dd>{user.email}</dd>
              <dt>Role</dt><dd>{ROLE_LABELS[user.role]}</dd>
              {user.practice_name && <><dt>Practice</dt><dd>{user.practice_name}</dd></>}
            </dl></div>
          </div>
          <div className="card">
            <div className="card-head"><h3>Change password</h3></div>
            <div className="card-body"><PasswordForm onDone={() => toast('Password updated', 'success')} /></div>
          </div>
        </div>
        {isClinic && o && (
          <div className="card">
            <div className="card-head"><h3>Onboarding checklist</h3>
              <span className="muted">{steps.filter((s) => s[1]).length} of {steps.length}</span></div>
            <div className="card-body stack">
              {steps.map(([label, ok]) => (
                <div key={label} className="row">{ok ? <CheckCircle2 size={18} color="var(--green-700)" /> : <Circle size={18} color="var(--border-strong)" />}
                  <span style={{ color: ok ? 'var(--text)' : 'var(--text-2)' }}>{label}</span></div>
              ))}
              <span className="help">Our team completes the agreement and portal-access steps with you during onboarding.</span>
            </div>
          </div>
        )}
      </div>
    </>
  )
}
