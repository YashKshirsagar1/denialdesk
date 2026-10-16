import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Check, CheckCircle2, Download, FileText, PencilLine, Phone, Send, Sparkles, X } from 'lucide-react'
import {
  downloadPdf, fulfillDocumentRequest, getCase, openPdf, recordOutcome, requestDocument, submitReview, verifyOutcome,
  api_listCaseRequests,
} from '../api'
import { useAuth } from '../auth'
import { statusMeta } from '../lib/caseStatus'
import {
  attachmentLabel, date, dateTime, DOC_TYPE_LABELS, docTypeLabel, money, pct, rootCause, timelineText,
} from '../lib/format'
import { Alert, Async, Badge, Modal, Spinner, StatusBadge, useAsync, useToast } from '../components/ui'
import type { CaseDetail, DocumentRequest } from '../types'

export function ClaimPage() {
  const { id } = useParams()
  const nav = useNavigate()
  return (
    <>
      <button className="btn ghost sm" style={{ marginBottom: 12 }} onClick={() => nav(-1)}><ArrowLeft size={15} /> Back</button>
      <ClaimView id={Number(id)} />
    </>
  )
}

/** Full claim workspace. `reviewMode` embeds it in the ops review queue (hides the header back-link). */
export function ClaimView({ id, onChanged, reviewMode }: { id: number; onChanged?: () => void; reviewMode?: boolean }) {
  const { isOps } = useAuth()
  const state = useAsync(() => getCase(id), [id])
  const reqs = useAsync(() => api_listCaseRequests(id), [id])

  const refresh = () => { state.reload(); reqs.reload(); onChanged?.() }

  return (
    <Async state={state}>
      {(c) => (
        <div className="stack">
          <Header c={c} ops={isOps} />
          {!isOps && <ClinicStatus c={c} />}
          <div className={reviewMode ? 'stack' : 'split'}>
            <div className="stack">
              <Analysis c={c} />
              <Letter c={c} ops={isOps} onDone={refresh} reviewMode={!!reviewMode} />
            </div>
            <div className="stack">
              <Details c={c} />
              <Requests c={c} reqs={reqs.data ?? []} ops={isOps} onDone={refresh} />
              <Outcome c={c} ops={isOps} onDone={refresh} />
              <Timeline c={c} />
            </div>
          </div>
        </div>
      )}
    </Async>
  )
}

function Header({ c, ops }: { c: CaseDetail; ops: boolean }) {
  const toast = useToast()
  const appeal = c.drafts.find((d) => d.draft_type === 'appeal')
  const call = c.drafts.find((d) => d.draft_type === 'call_packet')
  const guard = (p: Promise<void>) => p.catch((e) => toast(e.message, 'error'))
  return (
    <div className="card card-body row wrap" style={{ gap: 18 }}>
      <div style={{ minWidth: 0 }}>
        <div className="row" style={{ gap: 12 }}>
          <h1 style={{ fontSize: 22 }}>{c.patient_ref ?? `Claim #${c.id}`}</h1>
          <StatusBadge state={c.state} />
        </div>
        <div className="muted" style={{ marginTop: 4 }}>
          {c.payer} · CPT {c.cpt} · DOS {date(c.dos)}{ops && c.practice_name ? ` · ${c.practice_name}` : ''}
        </div>
      </div>
      <div className="spacer" />
      <div style={{ textAlign: 'right' }}>
        <div className="faint" style={{ fontSize: 12 }}>Billed</div>
        <div style={{ fontSize: 22, fontWeight: 700 }}>{money(c.billed_amt)}</div>
      </div>
      <div className="row">
        {appeal && (
          <button className="btn" onClick={() => guard(downloadPdf(`/cases/${c.id}/packet/appeal.pdf`, `appeal_${c.id}.pdf`))}>
            <Download size={16} /> Appeal PDF
          </button>
        )}
        {ops && call && (
          <button className="btn" onClick={() => guard(openPdf(`/cases/${c.id}/packet/call-packet.pdf`))}>
            <Phone size={16} /> Call packet
          </button>
        )}
      </div>
    </div>
  )
}

function ClinicStatus({ c }: { c: CaseDetail }) {
  const m = statusMeta(c.state)
  const kind = m.tone === 'green' ? 'success' : m.tone === 'red' ? 'error' : m.tone === 'amber' ? 'warn' : 'info'
  return <Alert kind={kind}><b>{m.label}.</b> {m.detail(c.payer)}</Alert>
}

function Analysis({ c }: { c: CaseDetail }) {
  const d = c.diagnosis
  if (!d) {
    return <div className="card card-body row"><Spinner /> <span className="muted">Our AI is analyzing this denial…</span></div>
  }
  const s = d.winnability_score
  const color = s >= 0.6 ? 'var(--green-700)' : s >= 0.35 ? '#d9930d' : 'var(--red-700)'
  return (
    <div className="card">
      <div className="card-head"><h3><Sparkles size={15} style={{ verticalAlign: -2, marginRight: 6, color: 'var(--blue-600)' }} />Denial analysis</h3><Badge tone="blue" plain>{rootCause(d.root_cause)}</Badge></div>
      <div className="card-body stack">
        <div className="grid cols-3">
          <div>
            <div className="faint" style={{ fontSize: 12 }}>Likelihood of overturn</div>
            <div style={{ fontSize: 26, fontWeight: 700, color }}>{pct(s)}</div>
            <div className="meter" style={{ marginTop: 6 }}><i style={{ width: pct(s), background: color }} /></div>
          </div>
          <div>
            <div className="faint" style={{ fontSize: 12 }}>Expected recovery</div>
            <div style={{ fontSize: 26, fontWeight: 700 }}>{money(d.expected_value)}</div>
          </div>
          <div>
            <div className="faint" style={{ fontSize: 12 }}>Denial code</div>
            <div style={{ fontSize: 26, fontWeight: 700 }}>CARC {c.carc}</div>
            {c.rarc && <div className="faint" style={{ fontSize: 12 }}>RARC {c.rarc}</div>}
          </div>
        </div>
        {c.carc_description && <div className="muted" style={{ fontSize: 13 }}><b>What the payer said:</b> {c.carc_description}</div>}
        <div><div className="faint" style={{ fontSize: 12, marginBottom: 3 }}>Why we reached this conclusion</div><p>{d.rationale}</p></div>
      </div>
    </div>
  )
}

function parsePacket(content: string): Record<string, unknown> | null {
  try { const v = JSON.parse(content); return v && typeof v === 'object' ? v : null } catch { return null }
}

function Letter({ c, ops, onDone, reviewMode }: { c: CaseDetail; ops: boolean; onDone: () => void; reviewMode: boolean }) {
  const toast = useToast()
  const appeal = c.drafts.find((d) => d.draft_type === 'appeal')
  const call = c.drafts.find((d) => d.draft_type === 'call_packet')
  const [tab, setTab] = useState<'letter' | 'call'>('letter')
  const [editing, setEditing] = useState(false)
  const [text, setText] = useState(appeal?.content ?? '')
  const [busy, setBusy] = useState(false)
  useEffect(() => { setText(appeal?.content ?? ''); setEditing(false); setTab('letter') }, [c.id, appeal?.id])

  if (!appeal) {
    return (
      <div className="card card-body muted">
        {c.state === 'declined'
          ? 'No appeal letter was written because we don’t recommend appealing this denial.'
          : 'The appeal letter will appear here once the analysis is complete.'}
      </div>
    )
  }

  const canReview = ops && c.state === 'awaiting_human_review'
  const act = async (decision: 'approve' | 'reject' | 'edit') => {
    setBusy(true)
    try {
      const r = await submitReview(c.id, { decision, edits: decision === 'edit' ? text : undefined })
      toast(r.message, 'success')
      onDone()
    } catch (e) { toast((e as Error).message, 'error') } finally { setBusy(false) }
  }
  const edited = text !== appeal.content
  const packet = call ? parsePacket(call.content) : null

  return (
    <div className="card">
      <div className="card-head">
        <h3><FileText size={15} style={{ verticalAlign: -2, marginRight: 6, color: 'var(--blue-600)' }} />Appeal letter <span className="faint" style={{ fontWeight: 500 }}>· v{appeal.version}</span></h3>
        <div className="row">
          {!ops && c.state === 'awaiting_human_review' && <Badge tone="amber">Pending team review</Badge>}
          {!ops && ['submitted', 'pending_payer', 'paid', 're_denied', 'escalated'].includes(c.state) && <Badge tone="green">Reviewed & submitted</Badge>}
          {canReview && !editing && <button className="btn sm" onClick={() => setEditing(true)}><PencilLine size={14} /> Edit</button>}
        </div>
      </div>
      {ops && call && (
        <div className="tabs">
          <button className={`tab${tab === 'letter' ? ' on' : ''}`} onClick={() => setTab('letter')}>Appeal letter</button>
          <button className={`tab${tab === 'call' ? ' on' : ''}`} onClick={() => setTab('call')}>Call packet</button>
        </div>
      )}
      <div className="card-body stack">
        {tab === 'letter' ? (
          <>
            <div className="letter-wrap">
              {editing
                ? <textarea className="letter-edit" value={text} onChange={(e) => setText(e.target.value)} aria-label="Edit appeal letter" />
                : <div className="letter">{appeal.content}</div>}
            </div>
            {appeal.attachments.length > 0 && (
              <div>
                <div className="faint" style={{ fontSize: 12, marginBottom: 6 }}>Documents to attach with this appeal</div>
                <div className="row wrap">
                  {appeal.attachments.map((a) => <Badge key={a} tone="gray" plain>{attachmentLabel(a)}</Badge>)}
                </div>
              </div>
            )}
          </>
        ) : packet ? (
          <CallPacket p={packet} />
        ) : (
          <div className="letter-wrap"><div className="letter">{call?.content}</div></div>
        )}
      </div>
      {canReview && tab === 'letter' && (
        <div className="sticky-actions">
          <span className="muted nowrap" style={{ fontSize: 12.5 }}>Nothing is sent until you approve.</span>
          <div className="spacer" />
          {editing && <button className="btn ghost" disabled={busy} onClick={() => { setText(appeal.content); setEditing(false) }}>Cancel edits</button>}
          <button className="btn danger" disabled={busy} onClick={() => act('reject')}><X size={15} /> Reject</button>
          {editing && edited
            ? <button className="btn success" disabled={busy} onClick={() => act('edit')}>{busy ? <Spinner /> : <Send size={15} />} Save edits & approve</button>
            : <button className="btn success" disabled={busy} onClick={() => act('approve')}>{busy ? <Spinner /> : <Check size={15} />} Approve & submit</button>}
        </div>
      )}
    </div>
  )
}

function CallPacket({ p }: { p: Record<string, unknown> }) {
  const str = (k: string) => (typeof p[k] === 'string' ? (p[k] as string) : '')
  const list = (k: string) => (Array.isArray(p[k]) ? (p[k] as unknown[]).map(String) : [])
  return (
    <div className="stack">
      {str('claim_summary') && <div><div className="faint" style={{ fontSize: 12 }}>Claim summary</div><p>{str('claim_summary')}</p></div>}
      {str('the_ask') && <div><div className="faint" style={{ fontSize: 12 }}>The ask</div><p><b>{str('the_ask')}</b></p></div>}
      {str('phone_tree') && <div><div className="faint" style={{ fontSize: 12 }}>Phone tree path</div><p>{str('phone_tree')}</p></div>}
      {list('talking_points').length > 0 && (
        <div><div className="faint" style={{ fontSize: 12 }}>Talking points</div>
          <ul style={{ margin: '4px 0 0', paddingLeft: 18 }}>{list('talking_points').map((t, i) => <li key={i}>{t}</li>)}</ul></div>
      )}
      {str('escalation_trigger') && <div><div className="faint" style={{ fontSize: 12 }}>Escalate if</div><p>{str('escalation_trigger')}</p></div>}
    </div>
  )
}

function Details({ c }: { c: CaseDetail }) {
  const dl = c.filing_deadline
  const days = dl ? Math.round((new Date(`${dl}T00:00:00`).getTime() - Date.now()) / 86400000) : null
  return (
    <div className="card">
      <div className="card-head"><h3>Claim details</h3></div>
      <div className="card-body">
        <dl className="kv">
          <dt>Claim #</dt><dd className="mono">{c.claim_number ?? '—'}</dd>
          <dt>Patient ref</dt><dd>{c.patient_ref ?? '—'}</dd>
          <dt>Payer</dt><dd>{c.payer}</dd>
          <dt>Date of service</dt><dd>{date(c.dos)}</dd>
          <dt>Denial date</dt><dd>{date(c.denial_date)}</dd>
          <dt>CPT / HCPCS</dt><dd className="mono">{c.cpt}{c.modifier ? `-${c.modifier}` : ''}</dd>
          <dt>ICD-10</dt><dd className="mono">{c.icd10.join(', ') || '—'}</dd>
          <dt>Billed / allowed</dt><dd>{money(c.billed_amt)} / {money(c.allowed_amt)}</dd>
          <dt>Appeal deadline</dt>
          <dd>{dl ? <>{date(dl)} {days != null && <Badge tone={days < 0 ? 'red' : days <= 14 ? 'amber' : 'gray'} plain>{days < 0 ? `${-days}d overdue` : `${days}d left`}</Badge>}</> : '—'}</dd>
        </dl>
      </div>
    </div>
  )
}

function Requests({ c, reqs, ops, onDone }: { c: CaseDetail; reqs: DocumentRequest[]; ops: boolean; onDone: () => void }) {
  const toast = useToast()
  const [modal, setModal] = useState(false)
  const [type, setType] = useState('chart_note')
  const [desc, setDesc] = useState('')
  const [busy, setBusy] = useState<number | 'new' | null>(null)

  const upload = async (r: DocumentRequest, file?: File) => {
    setBusy(r.id)
    try { await fulfillDocumentRequest(r.id, file); toast('Document sent to our team', 'success'); onDone() }
    catch (e) { toast((e as Error).message, 'error') } finally { setBusy(null) }
  }
  const create = async () => {
    setBusy('new')
    try { await requestDocument(c.id, type, desc, 'reviewer'); toast('Request sent to the clinic', 'success'); setModal(false); setDesc(''); onDone() }
    catch (e) { toast((e as Error).message, 'error') } finally { setBusy(null) }
  }

  if (!ops && reqs.length === 0) return null
  return (
    <div className="card">
      <div className="card-head">
        <h3>Document requests</h3>
        {ops && <button className="btn sm" onClick={() => setModal(true)}>Request document</button>}
      </div>
      <div className="card-body stack">
        {reqs.length === 0 && <span className="muted">No requests for this claim.</span>}
        {reqs.map((r) => (
          <div key={r.id} className="stack" style={{ gap: 8 }}>
            <div className="row"><b>{docTypeLabel(r.document_type)}</b>
              <Badge tone={r.status === 'pending' ? 'amber' : 'green'}>{r.status === 'pending' ? 'Needed' : 'Received'}</Badge></div>
            <div className="muted" style={{ fontSize: 13 }}>{r.description}</div>
            {!ops && r.status === 'pending' && (
              <label className="btn sm" style={{ width: 'fit-content' }}>
                {busy === r.id ? <Spinner /> : 'Upload document'}
                <input type="file" hidden onChange={(e) => e.target.files?.[0] && upload(r, e.target.files[0])} />
              </label>
            )}
          </div>
        ))}
      </div>
      {modal && (
        <Modal title="Request a document from the clinic" onClose={() => setModal(false)}
          footer={<><button className="btn" onClick={() => setModal(false)}>Cancel</button>
            <button className="btn primary" disabled={!desc.trim() || busy === 'new'} onClick={create}>Send request</button></>}>
          <div className="stack">
            <label className="field">Document type
              <select value={type} onChange={(e) => setType(e.target.value)}>
                {Object.entries(DOC_TYPE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select></label>
            <label className="field">What do you need?
              <textarea value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="e.g. Chart note from the 3/12 visit showing the exam findings" /></label>
          </div>
        </Modal>
      )}
    </div>
  )
}

function Outcome({ c, ops, onDone }: { c: CaseDetail; ops: boolean; onDone: () => void }) {
  const toast = useToast()
  const { user } = useAuth()
  const [result, setResult] = useState('paid')
  const [amount, setAmount] = useState(String(c.billed_amt))
  const [paid, setPaid] = useState(new Date().toISOString().slice(0, 10))
  const [notes, setNotes] = useState('')
  const [busy, setBusy] = useState(false)
  const o = c.outcome
  const canRecord = ops && !o && ['submitted', 'pending_payer', 'escalated'].includes(c.state)
  const canVerify = !!o && !o.verified && o.result !== 'denied' && (ops || user?.role === 'clinic_admin')

  if (!o && !canRecord) return null
  const run = async (fn: () => Promise<unknown>, ok: string) => {
    setBusy(true)
    try { await fn(); toast(ok, 'success'); onDone() } catch (e) { toast((e as Error).message, 'error') } finally { setBusy(false) }
  }

  return (
    <div className="card">
      <div className="card-head"><h3>Outcome</h3>{o && <Badge tone={o.result === 'denied' ? 'red' : 'green'}>{o.result === 'denied' ? 'Denied' : o.result === 'partially_paid' ? 'Partially paid' : 'Paid'}</Badge>}</div>
      <div className="card-body stack">
        {o ? (
          <>
            <dl className="kv">
              <dt>Recovered</dt><dd style={{ color: 'var(--green-700)' }}>{money(o.amount_recovered)}</dd>
              <dt>Paid on</dt><dd>{date(o.paid_date)}</dd>
              <dt>Verified</dt><dd>{o.verified ? <span className="row" style={{ gap: 5 }}><CheckCircle2 size={15} color="var(--green-700)" /> Yes</span> : 'Awaiting confirmation'}</dd>
              {o.verified && o.billable_amount != null && <><dt>Fee</dt><dd>{money(o.billable_amount)}</dd></>}
            </dl>
            {canVerify && (
              <button className="btn primary" disabled={busy} onClick={() => run(() => verifyOutcome(c.id, user?.email ?? 'user'), 'Recovery confirmed')}>
                {busy ? <Spinner /> : <CheckCircle2 size={16} />} Confirm recovery
              </button>
            )}
            {!o.verified && !ops && <span className="help">Confirm once you see the payment so we can finalize your statement.</span>}
          </>
        ) : (
          <>
            <label className="field">Result
              <select value={result} onChange={(e) => setResult(e.target.value)}>
                <option value="paid">Paid in full</option><option value="partially_paid">Partially paid</option><option value="denied">Denied</option>
              </select></label>
            {result !== 'denied' && (
              <div className="form-grid">
                <label className="field">Amount recovered<input type="number" min="0" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} /></label>
                <label className="field">Paid date<input type="date" value={paid} onChange={(e) => setPaid(e.target.value)} /></label>
              </div>
            )}
            <label className="field">Notes<textarea style={{ minHeight: 60 }} value={notes} onChange={(e) => setNotes(e.target.value)} /></label>
            <button className="btn primary" disabled={busy}
              onClick={() => run(() => recordOutcome(c.id, { result, amount_recovered: result === 'denied' ? 0 : Number(amount) || 0, paid_date: result === 'denied' ? undefined : paid, notes }), 'Outcome recorded')}>
              {busy ? <Spinner /> : 'Record outcome'}
            </button>
          </>
        )}
      </div>
    </div>
  )
}

function Timeline({ c }: { c: CaseDetail }) {
  return (
    <div className="card">
      <div className="card-head"><h3>Activity</h3></div>
      <div className="card-body">
        {c.timeline.length === 0 ? <span className="muted">No activity yet.</span> : (
          <ul className="timeline">
            {[...c.timeline].reverse().map((e, i) => (
              <li key={i}>
                <div className="t-title">{timelineText(e.action)}</div>
                <div className="t-meta">{e.actor} · {dateTime(e.timestamp)}</div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

