import { useState } from 'react'
import { setToken } from '../auth'

interface Props {
  onLogin: () => void
}

const ROLES = ['clinic_admin', 'clinic_staff', 'reviewer', 'ops_admin'] as const
type RoleOption = typeof ROLES[number]

export function LoginPage({ onLogin }: Props) {
  const [email, setEmail] = useState('dev@denialdesk.local')
  const [role, setRole] = useState<RoleOption>('ops_admin')
  const [tenantId, setTenantId] = useState<string>('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/auth/dev-token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email,
          role,
          tenant_id: tenantId ? parseInt(tenantId, 10) : null,
          user_id: email,
        }),
      })
      if (!res.ok) {
        const text = await res.text()
        throw new Error(`Login failed: ${text}`)
      }
      const data = await res.json()
      setToken(data.access_token)
      onLogin()
    } catch (err) {
      setError(String(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      height: '100vh',
      background: '#f8f9fa',
      fontFamily: 'system-ui, sans-serif',
    }}>
      <div style={{ background: '#fff', borderRadius: 8, padding: 40, width: 380, boxShadow: '0 2px 12px rgba(0,0,0,0.08)' }}>
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: 24, gap: 10 }}>
          <span style={{ fontWeight: 700, fontSize: 20, color: '#212529' }}>DenialDesk</span>
          <span style={{
            background: '#fff3cd',
            color: '#856404',
            fontSize: 11,
            fontWeight: 600,
            padding: '2px 8px',
            borderRadius: 4,
            border: '1px solid #ffc107',
          }}>
            DEV MODE
          </span>
        </div>

        <p style={{ color: '#6c757d', fontSize: 13, marginBottom: 24, marginTop: 0 }}>
          This is a development login. In production, authentication is handled by Auth0 with MFA.
        </p>

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6, color: '#495057' }}>
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              style={{ width: '100%', padding: '8px 10px', border: '1px solid #ced4da', borderRadius: 4, fontSize: 14, boxSizing: 'border-box' }}
            />
          </div>

          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6, color: '#495057' }}>
              Role
            </label>
            <select
              value={role}
              onChange={e => setRole(e.target.value as RoleOption)}
              style={{ width: '100%', padding: '8px 10px', border: '1px solid #ced4da', borderRadius: 4, fontSize: 14 }}
            >
              {ROLES.map(r => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
          </div>

          <div style={{ marginBottom: 24 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6, color: '#495057' }}>
              Tenant ID <span style={{ fontWeight: 400, color: '#6c757d' }}>(leave blank for ops_admin)</span>
            </label>
            <input
              type="number"
              value={tenantId}
              onChange={e => setTenantId(e.target.value)}
              placeholder="e.g. 1"
              style={{ width: '100%', padding: '8px 10px', border: '1px solid #ced4da', borderRadius: 4, fontSize: 14, boxSizing: 'border-box' }}
            />
          </div>

          {error && (
            <div style={{ background: '#f8d7da', color: '#58151c', padding: '8px 12px', borderRadius: 4, fontSize: 13, marginBottom: 16 }}>
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            style={{
              width: '100%',
              padding: '10px 0',
              background: loading ? '#adb5bd' : '#0d6efd',
              color: '#fff',
              border: 'none',
              borderRadius: 4,
              fontSize: 14,
              fontWeight: 600,
              cursor: loading ? 'not-allowed' : 'pointer',
            }}
          >
            {loading ? 'Signing in...' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  )
}
