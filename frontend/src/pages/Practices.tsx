import { useState, type FormEvent } from 'react'
import { Building2, CheckCircle2, Circle, Plus } from 'lucide-react'
import { activatePractice, createPractice, listPractices, signBaa, signServiceAgreement, suspendPractice } from '../api'
import { Alert, Async, Badge, Empty, Modal, PageHead, Spinner, useAsync, useToast } from '../components/ui'
import type { PracticeOut } from '../types'
import type { Tone } from '../lib/caseStatus'

const STATUS: Record<string, { label: string; tone: Tone }> = {
  pending_agreements: { label: 'Awaiting agreements', tone: 'amber' },
  pending_details: { label: 'Awaiting details', tone: 'amber' },
  active: { label: 'Active', tone: 'green' },
  suspended: { label: 'Suspended', tone: 'red' },
}

export function Practices() {
  const toast = useToast()
  const list = useAsync(listPractices, [])
  const [adding, setAdding] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)

  const act = async (key: string, fn: () => Promise<unknown>, ok: string) => {
    setBusy(key)
    try { await fn(); toast(ok, 'success'); list.reload() } catch (e) { toast((e as Error).message, 'error') } finally { setBusy(null) }
  }

  return (
    <>
      <PageHead title="Practices" sub="Clinic onboarding. A clinic can’t upload until both agreements are signed and you activate it."
        actions={<button className="btn primary" onClick={() => setAdding(true)}><Plus size={16} /> Add practice</button>} />
      <Async state={list}>
        {(rows) => rows.length === 0 ? <div className="card"><Empty title="No practices yet" icon={<Building2 size={24} />} /></div> : (
          <div className="grid" style={{ gap: 14 }}>
            {rows.map((p) => <PracticeCard key={p.id} p={p} busy={busy} act={act} />)}
          </div>
        )}
      </Async>
      {adding && <AddPractice onClose={() => setAdding(false)} onDone={() => { setAdding(false); list.reload() }} />}
    </>
  )
}

function PracticeCard({ p, busy, act }: { p: PracticeOut; busy: string | null; act: (k: string, fn: () => Promise<unknown>, ok: string) => void }) {
  const s = STATUS[p.onboarding_status] ?? { label: p.onboarding_status, tone: 'gray' as Tone }
  const Step = ({ ok, label }: { ok: boolean; label: string }) => (
    <span className="row" style={{ gap: 6 }}>{ok ? <CheckCircle2 size={16} color="var(--green-700)" /> : <Circle size={16} color="var(--border-strong)" />}{label}</span>
  )
  const btn = (key: string, label: string, fn: () => Promise<unknown>, ok: string, cls = '') => (
    <button className={`btn sm ${cls}`} disabled={busy !== null} onClick={() => act(`${p.id}:${key}`, fn, ok)}>
      {busy === `${p.id}:${key}` ? <Spinner /> : label}
    </button>
  )
  const ready = p.baa_signed && p.service_agreement_signed
  return (
    <div className="card card-body row wrap" style={{ gap: 20 }}>
      <div style={{ minWidth: 220, flex: 1 }}>
        <div className="row"><h3>{p.name}</h3><Badge tone={s.tone}>{s.label}</Badge></div>
        <div className="muted">{p.specialty}{p.contact ? ` · ${p.contact}` : ''}</div>
      </div>
      <div className="stack" style={{ gap: 6 }}>
        <Step ok={p.baa_signed} label="BAA signed" />
        <Step ok={p.service_agreement_signed} label="Service agreement signed" />
      </div>
      <div className="row wrap">
        {!p.baa_signed && btn('baa', 'Mark BAA signed', () => signBaa(p.id), 'BAA recorded')}
        {!p.service_agreement_signed && btn('sa', 'Mark agreement signed', () => signServiceAgreement(p.id), 'Service agreement recorded')}
        {p.onboarding_status !== 'active' && btn('act', 'Activate', () => activatePractice(p.id), `${p.name} activated`, ready ? 'primary' : '')}
        {p.onboarding_status === 'active' && btn('sus', 'Suspend', () => suspendPractice(p.id), `${p.name} suspended`, 'danger')}
      </div>
    </div>
  )
}

function AddPractice({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const [name, setName] = useState('')
  const [specialty, setSpecialty] = useState('')
  const [contact, setContact] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  async function submit(e: FormEvent) {
    e.preventDefault(); setBusy(true); setErr(null)
    try { await createPractice(name, specialty, contact || undefined); onDone() } catch (e2) { setErr((e2 as Error).message) } finally { setBusy(false) }
  }
  return (
    <Modal title="Add a practice" onClose={onClose}>
      <form className="stack" onSubmit={submit}>
        {err && <Alert kind="error">{err}</Alert>}
        <label className="field">Practice name<input value={name} onChange={(e) => setName(e.target.value)} required /></label>
        <label className="field">Specialty<input value={specialty} onChange={(e) => setSpecialty(e.target.value)} required /></label>
        <label className="field">Contact email<input type="email" value={contact} onChange={(e) => setContact(e.target.value)} /></label>
        <span className="help">After creating the practice, add its first admin under Users.</span>
        <div className="row" style={{ justifyContent: 'flex-end' }}>
          <button type="button" className="btn" onClick={onClose}>Cancel</button>
          <button className="btn primary" disabled={busy}>{busy ? <Spinner /> : 'Create'}</button>
        </div>
      </form>
    </Modal>
  )
}
