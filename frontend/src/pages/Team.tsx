import { useState, type FormEvent } from 'react'
import { UserPlus } from 'lucide-react'
import { createUser, listPractices, listUsers, updateUser } from '../api'
import { useAuth } from '../auth'
import { ago, ROLE_LABELS } from '../lib/format'
import { Alert, Async, Badge, Modal, PageHead, Spinner, useAsync, useToast } from '../components/ui'

export function Team() {
  const { user } = useAuth()
  const toast = useToast()
  const admin = user?.role === 'ops_admin'
  const users = useAsync(listUsers, [])
  const [adding, setAdding] = useState(false)

  const toggle = async (id: number, active: boolean) => {
    try { await updateUser(id, { is_active: active }); toast(active ? 'Access restored' : 'Access removed', 'success'); users.reload() }
    catch (e) { toast((e as Error).message, 'error') }
  }

  return (
    <>
      <PageHead title={admin ? 'Users' : 'Team'} sub={admin ? 'Everyone who can sign in to DenialDesk.' : 'Manage who at your practice can use DenialDesk.'}
        actions={<button className="btn primary" onClick={() => setAdding(true)}><UserPlus size={16} /> Add user</button>} />
      <div className="card">
        <Async state={users}>
          {(rows) => (
            <div className="table-wrap"><table className="tbl">
              <thead><tr><th>Name</th>{admin && <th>Practice</th>}<th>Role</th><th>Last sign-in</th><th>Status</th><th /></tr></thead>
              <tbody>
                {rows.map((u) => (
                  <tr key={u.id}>
                    <td><div className="primary">{u.full_name || '—'}</div><div className="secondary">{u.email}</div></td>
                    {admin && <td>{u.practice_name ?? 'DenialDesk'}</td>}
                    <td>{ROLE_LABELS[u.role]}</td>
                    <td className="muted">{u.last_login_at ? ago(u.last_login_at) : 'Never'}</td>
                    <td><Badge tone={u.is_active ? 'green' : 'gray'}>{u.is_active ? 'Active' : 'Disabled'}</Badge></td>
                    <td className="right">
                      {String(u.id) !== String(user?.id) && (
                        <button className={`btn sm${u.is_active ? ' danger' : ''}`} onClick={() => toggle(u.id, !u.is_active)}>{u.is_active ? 'Remove access' : 'Restore'}</button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody></table></div>
          )}
        </Async>
      </div>
      {adding && <AddUser admin={!!admin} onClose={() => setAdding(false)} onDone={() => { setAdding(false); users.reload() }} />}
    </>
  )
}

function AddUser({ admin, onClose, onDone }: { admin: boolean; onClose: () => void; onDone: () => void }) {
  const practices = useAsync(() => (admin ? listPractices() : Promise.resolve([])), [admin])
  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [role, setRole] = useState(admin ? 'reviewer' : 'clinic_staff')
  const [tenant, setTenant] = useState<number | ''>('')
  const [pw, setPw] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const clinicRole = role.startsWith('clinic')

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true); setErr(null)
    try { await createUser({ email, full_name: name, role, temp_password: pw, tenant_id: clinicRole && tenant !== '' ? tenant : null }); onDone() }
    catch (e2) { setErr((e2 as Error).message) } finally { setBusy(false) }
  }
  return (
    <Modal title="Add a user" onClose={onClose}>
      <form className="stack" onSubmit={submit}>
        {err && <Alert kind="error">{err}</Alert>}
        <label className="field">Full name<input value={name} onChange={(e) => setName(e.target.value)} required /></label>
        <label className="field">Email<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required /></label>
        <label className="field">Role
          <select value={role} onChange={(e) => setRole(e.target.value)}>
            <option value="clinic_staff">Clinic staff</option><option value="clinic_admin">Clinic admin</option>
            {admin && <><option value="reviewer">Appeals reviewer</option><option value="ops_admin">DenialDesk admin</option></>}
          </select></label>
        {admin && clinicRole && (
          <label className="field">Practice
            <select value={tenant} required onChange={(e) => setTenant(e.target.value ? Number(e.target.value) : '')}>
              <option value="">Select…</option>{(practices.data ?? []).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select></label>
        )}
        <label className="field">Temporary password
          <input type="text" value={pw} onChange={(e) => setPw(e.target.value)} required autoComplete="off" />
          <span className="help">10+ characters with upper/lower case and a number. They’ll be asked to change it at first sign-in.</span></label>
        <div className="row" style={{ justifyContent: 'flex-end' }}>
          <button type="button" className="btn" onClick={onClose}>Cancel</button>
          <button className="btn primary" disabled={busy}>{busy ? <Spinner /> : 'Add user'}</button>
        </div>
      </form>
    </Modal>
  )
}
