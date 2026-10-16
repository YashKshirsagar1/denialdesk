import { useEffect, useState, type FormEvent } from 'react'
import { Activity, FileCheck2, LineChart, ShieldCheck, Sparkles } from 'lucide-react'
import { useAuth } from '../auth'
import { getDemoAccounts, login, signup } from '../api'
import type { DemoAccounts } from '../types'
import { ROLE_LABELS } from '../lib/format'
import { Alert, Spinner } from '../components/ui'

const SPECIALTIES = [
  'Family Medicine', 'Internal Medicine', 'Pediatrics', 'Cardiology', 'Orthopedics', 'Dermatology',
  'OB/GYN', 'Psychiatry', 'Physical Therapy', 'Gastroenterology', 'Urgent Care', 'Other',
]

export function Login() {
  const { signIn, notice } = useAuth()
  const [mode, setMode] = useState<'login' | 'signup'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [practice, setPractice] = useState('')
  const [specialty, setSpecialty] = useState(SPECIALTIES[0])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [demo, setDemo] = useState<DemoAccounts | null>(null)

  useEffect(() => { getDemoAccounts().then(setDemo).catch(() => setDemo(null)) }, [])

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const resp = mode === 'login'
        ? await login(email, password)
        : await signup({ practice_name: practice, specialty, full_name: fullName, email, password })
      signIn(resp)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth">
      <section className="auth-hero">
        <div className="brand" style={{ padding: 0, fontSize: 20 }}>
          <span className="brand-mark"><Activity size={18} /></span> DenialDesk
        </div>
        <div>
          <h2>Recover the revenue your practice already earned.</h2>
          <p className="lead">Upload denied claims. Our AI diagnoses each denial, decides what’s winnable, and writes the appeal — reviewed by our team before it goes out.</p>
          <ul className="feature-list">
            <li><span className="fi"><Sparkles size={18} /></span><span><b>AI-written appeal letters</b>Payer-specific, citing the right policy and the right documents.</span></li>
            <li><span className="fi"><FileCheck2 size={18} /></span><span><b>Human-reviewed before submission</b>Every appeal is approved by an appeals specialist.</span></li>
            <li><span className="fi"><LineChart size={18} /></span><span><b>Pay only when you recover</b>Contingency pricing — no recovery, no fee.</span></li>
          </ul>
        </div>
        <div style={{ color: '#8fa5c4', fontSize: 12.5, display: 'flex', gap: 8, alignItems: 'center' }}>
          <ShieldCheck size={15} /> Every access to your data is logged. Sessions end after 30 minutes idle.
        </div>
      </section>

      <section className="auth-form-wrap">
        <form className="auth-form stack" onSubmit={submit}>
          <div>
            <h1>{mode === 'login' ? 'Sign in' : 'Create your clinic account'}</h1>
            <p className="muted">{mode === 'login' ? 'Welcome back. Enter your credentials to continue.' : 'Set up your practice. Our team activates uploads once your agreements are signed.'}</p>
          </div>

          {notice && <Alert kind="info">{notice}</Alert>}
          {error && <Alert kind="error">{error}</Alert>}

          {mode === 'signup' && (
            <>
              <label className="field">Practice name
                <input value={practice} onChange={(e) => setPractice(e.target.value)} required minLength={2} autoComplete="organization" />
              </label>
              <label className="field">Primary specialty
                <select value={specialty} onChange={(e) => setSpecialty(e.target.value)}>
                  {SPECIALTIES.map((s) => <option key={s}>{s}</option>)}
                </select>
              </label>
              <label className="field">Your name
                <input value={fullName} onChange={(e) => setFullName(e.target.value)} required minLength={2} autoComplete="name" />
              </label>
            </>
          )}
          <label className="field">Work email
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="username" />
          </label>
          <label className="field">Password
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'} />
            {mode === 'signup' && <span className="help">At least 10 characters, with upper and lower case and a number.</span>}
          </label>

          <button className="btn primary lg block" disabled={busy}>
            {busy ? <Spinner /> : mode === 'login' ? 'Sign in' : 'Create account'}
          </button>

          <p className="muted" style={{ textAlign: 'center' }}>
            {mode === 'login' ? (
              <>New practice? <button type="button" className="link-btn" onClick={() => { setMode('signup'); setError(null) }}>Create an account</button></>
            ) : (
              <>Already have an account? <button type="button" className="link-btn" onClick={() => { setMode('login'); setError(null) }}>Sign in</button></>
            )}
          </p>

          {demo && demo.accounts.length > 0 && mode === 'login' && (
            <div className="demo-box">
              <b>Demo accounts</b> <span className="faint">(synthetic data only)</span>
              {demo.accounts.map((a) => (
                <button type="button" key={a.email} onClick={() => { setEmail(a.email); setPassword(demo.password) }}>
                  {ROLE_LABELS[a.role]} — {a.full_name}
                </button>
              ))}
            </div>
          )}
        </form>
      </section>
    </div>
  )
}
