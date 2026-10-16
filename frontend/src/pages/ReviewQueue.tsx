import { useEffect, useMemo, useState } from 'react'
import { CheckCircle2 } from 'lucide-react'
import { getQueueCases } from '../api'
import { ago, money, pct, rootCause } from '../lib/format'
import { Async, Empty, PageHead, useAsync } from '../components/ui'
import { ClaimView } from './ClaimDetail'

export function ReviewQueue() {
  const queue = useAsync(() => getQueueCases('awaiting_human_review'), [])
  const [sel, setSel] = useState<number | null>(null)
  const [q, setQ] = useState('')
  const rows = useMemo(() => (queue.data ?? []).filter((c) =>
    !q || [c.practice_name, c.payer, c.patient_ref, c.carc].some((v) => (v ?? '').toLowerCase().includes(q.toLowerCase()))), [queue.data, q])

  // Keep a valid selection: first item by default, next item after the current one is approved away.
  useEffect(() => {
    if (!rows.length) { setSel(null); return }
    if (sel == null || !rows.some((r) => r.id === sel)) setSel(rows[0].id)
  }, [rows, sel])

  return (
    <>
      <PageHead title="Review queue" sub="Read each AI-drafted appeal. Nothing is submitted to a payer until a human approves it." />
      <Async state={queue}>
        {(all) => all.length === 0 ? (
          <div className="card"><Empty title="Queue is clear" icon={<CheckCircle2 size={24} />}>No appeals are waiting for review. New ones appear as clinics upload denials.</Empty></div>
        ) : (
          <div className="queue-layout">
            <div className="card">
              <div className="toolbar"><input type="search" style={{ maxWidth: 'none' }} placeholder={`Search ${all.length} appeals…`} value={q} onChange={(e) => setQ(e.target.value)} /></div>
              <div className="queue-list">
                {rows.map((c) => (
                  <div key={c.id} className={`q-item${sel === c.id ? ' on' : ''}`} onClick={() => setSel(c.id)} tabIndex={0}
                    onKeyDown={(e) => e.key === 'Enter' && setSel(c.id)}>
                    <div className="row"><b>{c.patient_ref ?? `#${c.id}`}</b><div className="spacer" /><b>{money(c.billed_amt, false)}</b></div>
                    <div className="muted" style={{ fontSize: 12.5 }}>{c.practice_name} · {c.payer}</div>
                    <div className="row" style={{ marginTop: 4, fontSize: 12 }}>
                      <span className="faint">{rootCause(c.root_cause)} · CARC {c.carc}</span>
                      <div className="spacer" />
                      {c.winnability_score != null && <span style={{ fontWeight: 600 }}>{pct(c.winnability_score)} odds</span>}
                    </div>
                    <div className="faint" style={{ fontSize: 11.5 }}>{ago(c.created_at)}</div>
                  </div>
                ))}
              </div>
            </div>
            <div>{sel != null && <ClaimView key={sel} id={sel} reviewMode onChanged={queue.reload} />}</div>
          </div>
        )}
      </Async>
    </>
  )
}
