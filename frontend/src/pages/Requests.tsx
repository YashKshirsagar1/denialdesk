import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { CheckCircle2, Inbox, Paperclip } from 'lucide-react'
import { fulfillDocumentRequest, getDocumentRequests, listCases } from '../api'
import { ago, docTypeLabel } from '../lib/format'
import { Async, Badge, Empty, PageHead, Spinner, useAsync, useToast } from '../components/ui'

export function Requests() {
  const toast = useToast()
  const nav = useNavigate()
  const reqs = useAsync(getDocumentRequests, [])
  const cases = useAsync(() => listCases(), [])
  const [busy, setBusy] = useState<number | null>(null)
  const label = (id: number) => cases.data?.find((c) => c.id === id)?.patient_ref ?? `Claim #${id}`

  async function send(id: number, file?: File) {
    setBusy(id)
    try { await fulfillDocumentRequest(id, file); toast('Sent to our team — thank you', 'success'); reqs.reload() }
    catch (e) { toast((e as Error).message, 'error') } finally { setBusy(null) }
  }

  return (
    <>
      <PageHead title="Requests" sub="When an appeal needs a document only your practice has, it shows up here." />
      <Async state={reqs}>
        {(all) => {
          const open = all.filter((r) => r.status === 'pending')
          const done = all.filter((r) => r.status !== 'pending')
          if (all.length === 0) return <div className="card"><Empty title="Nothing needed right now" icon={<Inbox size={24} />}>We’ll let you know here if an appeal needs more from you.</Empty></div>
          return (
            <div className="stack">
              <div className="card">
                <div className="card-head"><h3>Needs your attention</h3><Badge tone={open.length ? 'amber' : 'green'} plain>{open.length} open</Badge></div>
                {open.length === 0 ? <Empty title="You’re all caught up" icon={<CheckCircle2 size={24} />} /> : open.map((r) => (
                  <div key={r.id} className="card-body row wrap" style={{ borderBottom: '1px solid var(--border)', gap: 16 }}>
                    <div style={{ flex: 1, minWidth: 240 }}>
                      <div className="row"><b>{docTypeLabel(r.document_type)}</b>
                        <button className="link-btn" onClick={() => nav(`/claims/${r.case_id}`)}>{label(r.case_id)}</button>
                        <span className="faint">· {ago(r.created_at)}</span></div>
                      <div className="muted" style={{ marginTop: 3 }}>{r.description}</div>
                    </div>
                    <label className="btn primary">
                      {busy === r.id ? <Spinner /> : <><Paperclip size={15} /> Upload document</>}
                      <input type="file" hidden disabled={busy === r.id} onChange={(e) => e.target.files?.[0] && send(r.id, e.target.files[0])} />
                    </label>
                  </div>
                ))}
              </div>
              {done.length > 0 && (
                <div className="card">
                  <div className="card-head"><h3>Completed</h3></div>
                  <div className="table-wrap"><table className="tbl"><tbody>
                    {done.map((r) => (
                      <tr key={r.id}><td className="primary">{docTypeLabel(r.document_type)}</td>
                        <td className="muted">{label(r.case_id)}</td><td className="muted">{r.description}</td>
                        <td className="right"><Badge tone="green">Received {ago(r.fulfilled_at)}</Badge></td></tr>
                    ))}
                  </tbody></table></div>
                </div>
              )}
            </div>
          )
        }}
      </Async>
    </>
  )
}
