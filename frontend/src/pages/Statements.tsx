import { useState } from 'react'
import { Download, Receipt, Send } from 'lucide-react'
import { downloadPdf, generateStatement, getClinicStatements, getOpsStatements, listPractices, markStatementSent } from '../api'
import { useAuth } from '../auth'
import { date, dateTime, money } from '../lib/format'
import { Async, Badge, Empty, Modal, PageHead, Spinner, Stat, useAsync, useToast } from '../components/ui'
import type { StatementOut } from '../types'

export function Statements() {
  const { user } = useAuth()
  const toast = useToast()
  const admin = user?.role === 'ops_admin'
  const state = useAsync(() => (user?.role === 'reviewer' ? Promise.resolve([] as StatementOut[]) : admin ? getOpsStatements() : getClinicStatements()), [admin])
  const [gen, setGen] = useState(false)
  const [busy, setBusy] = useState<number | null>(null)

  const act = async (id: number, fn: () => Promise<unknown>, ok: string) => {
    setBusy(id)
    try { await fn(); toast(ok, 'success'); state.reload() } catch (e) { toast((e as Error).message, 'error') } finally { setBusy(null) }
  }

  return (
    <>
      <PageHead
        title={admin ? 'Billing' : 'Statements'}
        sub={admin ? 'Monthly recovery statements and contingency fees by practice.' : 'Your monthly recovery statements. You only pay a fee on dollars we recover.'}
        actions={admin && <button className="btn primary" onClick={() => setGen(true)}><Receipt size={16} /> Generate statement</button>}
      />
      <Async state={state}>
        {(rows) => (
          <div className="stack">
            <div className="grid cols-3">
              <Stat label="Total recovered" value={money(rows.reduce((s, r) => s + r.total_recovered, 0))} tone="green" />
              <Stat label="Fees" value={money(rows.reduce((s, r) => s + r.fee_amount, 0))} tone="blue" />
              <Stat label="Statements" value={rows.length} tone="gray" />
            </div>
            <div className="card">
              {rows.length === 0 ? <Empty title="No statements yet" icon={<Receipt size={24} />}>Statements appear here after your first verified recovery.</Empty> : (
                <div className="table-wrap"><table className="tbl">
                  <thead><tr>{admin && <th>Practice</th>}<th>Period</th><th className="num">Recovered</th><th className="num">Fee</th><th>Status</th><th /></tr></thead>
                  <tbody>
                    {rows.map((s) => (
                      <tr key={s.id}>
                        {admin && <td className="primary">{s.practice_name}</td>}
                        <td>{date(s.period_start)} – {date(s.period_end)}</td>
                        <td className="num">{money(s.total_recovered)}</td>
                        <td className="num">{money(s.fee_amount)}</td>
                        <td><Badge tone={s.status === 'paid' ? 'green' : s.status === 'sent' ? 'blue' : 'gray'}>{s.status === 'sent' ? `Sent ${dateTime(s.sent_at)}` : s.status === 'paid' ? 'Paid' : 'Draft'}</Badge></td>
                        <td className="right nowrap">
                          <button className="btn sm" onClick={() => downloadPdf(`/statements/${s.id}/pdf`, `statement_${s.id}.pdf`).catch((e) => toast(e.message, 'error'))}><Download size={14} /> PDF</button>{' '}
                          {admin && s.status === 'draft' && (
                            <button className="btn sm primary" disabled={busy === s.id} onClick={() => act(s.id, () => markStatementSent(s.id), 'Statement marked as sent')}>
                              {busy === s.id ? <Spinner /> : <Send size={14} />} Send
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody></table></div>
              )}
            </div>
          </div>
        )}
      </Async>
      {gen && <GenerateModal onClose={() => setGen(false)} onDone={() => { setGen(false); state.reload() }} />}
    </>
  )
}

function GenerateModal({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const toast = useToast()
  const practices = useAsync(listPractices, [])
  const now = new Date()
  const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  const [pid, setPid] = useState<number | ''>('')
  const [start, setStart] = useState(iso(new Date(now.getFullYear(), now.getMonth(), 1)))
  const [end, setEnd] = useState(iso(new Date(now.getFullYear(), now.getMonth() + 1, 0)))
  const [busy, setBusy] = useState(false)
  const go = async () => {
    setBusy(true)
    try { await generateStatement(Number(pid), start, end); toast('Statement generated', 'success'); onDone() }
    catch (e) { toast((e as Error).message, 'error') } finally { setBusy(false) }
  }
  return (
    <Modal title="Generate statement" onClose={onClose} footer={<><button className="btn" onClick={onClose}>Cancel</button>
      <button className="btn primary" disabled={!pid || busy} onClick={go}>{busy ? <Spinner /> : 'Generate'}</button></>}>
      <div className="stack">
        <label className="field">Practice
          <select value={pid} onChange={(e) => setPid(e.target.value ? Number(e.target.value) : '')}>
            <option value="">Select a practice…</option>
            {(practices.data ?? []).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select></label>
        <div className="form-grid">
          <label className="field">Period start<input type="date" value={start} onChange={(e) => setStart(e.target.value)} /></label>
          <label className="field">Period end<input type="date" value={end} onChange={(e) => setEnd(e.target.value)} /></label>
        </div>
        <span className="help">Only verified recoveries paid in this period are included.</span>
      </div>
    </Modal>
  )
}
