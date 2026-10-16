import { useNavigate } from 'react-router-dom'
import { CalendarClock, CircleDollarSign, ClipboardCheck, Gauge, Percent, Timer } from 'lucide-react'
import { getDeadlines, getKpiOverview, getPipeline, getQueueStats } from '../api'
import { statusMeta } from '../lib/caseStatus'
import { money, pct } from '../lib/format'
import { Alert, Async, PageHead, Stat, useAsync } from '../components/ui'

export function OpsOverview() {
  const nav = useNavigate()
  const kpi = useAsync(getKpiOverview, [])
  const pipe = useAsync(getPipeline, [])
  const queue = useAsync(getQueueStats, [])
  const dl = useAsync(getDeadlines, [])
  const urgent = (dl.data ?? []).filter((d) => d.urgency === 'overdue' || d.urgency === 'critical')

  return (
    <>
      <PageHead title="Operations overview" sub="Cross-clinic performance and the work waiting on your team." />
      <div className="stack">
        {queue.data && queue.data.awaiting_review > 0 && (
          <Alert kind="info"><b>{queue.data.awaiting_review} appeal{queue.data.awaiting_review > 1 ? 's' : ''} waiting for review.</b>{' '}
            <button className="link-btn" onClick={() => nav('/review')}>Open the queue →</button></Alert>
        )}
        {urgent.length > 0 && (
          <Alert kind="warn"><b>{urgent.length} case{urgent.length > 1 ? 's' : ''} overdue or due within 3 days.</b>{' '}
            <button className="link-btn" onClick={() => nav('/deadlines')}>View deadlines →</button></Alert>
        )}
        <Async state={kpi}>
          {(k) => (
            <div className="grid cols-4">
              <Stat label="Total recovered" value={money(k.total_amount_recovered, false)} tone="green" icon={<CircleDollarSign size={15} />} hint={`${money(k.avg_amount_recovered, false)} avg per win`} />
              <Stat label="Recovery rate" value={pct(k.recovery_rate)} tone="violet" icon={<Percent size={15} />} hint={`${k.total_paid} paid of ${k.total_attempted} attempted`} />
              <Stat label="Declined at triage" value={pct(k.decline_rate)} tone="red" icon={<Gauge size={15} />} hint={`${k.total_declined} of ${k.total_cases} claims`} />
              <Stat label="Days to payment" value={k.avg_days_to_payment ? k.avg_days_to_payment.toFixed(0) : '—'} tone="blue" icon={<Timer size={15} />} hint="Upload to paid, average" />
            </div>
          )}
        </Async>
        <div className="grid cols-2" style={{ alignItems: 'start' }}>
          <div className="card">
            <div className="card-head"><h3><ClipboardCheck size={15} style={{ verticalAlign: -2, marginRight: 6 }} />Pipeline</h3></div>
            <div className="card-body">
              <Async state={pipe}>
                {(p) => p.stages.length === 0 ? <span className="muted">No cases yet.</span> : (
                  <>{p.stages.map((s) => (
                    <div className="bar-row" key={s.state}>
                      <span>{statusMeta(s.state).label}{s.state !== statusMeta(s.state).label.toLowerCase() && <span className="faint"> · {s.state.replace(/_/g, ' ')}</span>}</span>
                      <div className="bar"><i style={{ width: `${Math.max(s.pct * 100, s.count ? 2 : 0)}%` }} /></div>
                      <span className="right" style={{ fontWeight: 600 }}>{s.count}</span>
                    </div>
                  ))}</>
                )}
              </Async>
            </div>
          </div>
          <div className="card">
            <div className="card-head"><h3><CalendarClock size={15} style={{ verticalAlign: -2, marginRight: 6 }} />Closest deadlines</h3>
              <button className="link-btn" onClick={() => nav('/deadlines')}>All →</button></div>
            <Async state={dl}>
              {(rows) => rows.length === 0 ? <div className="card-body muted">No open deadlines.</div> : (
                <table className="tbl"><tbody>
                  {rows.slice(0, 6).map((d) => (
                    <tr key={d.case_id} className="clickable" onClick={() => nav(`/claims/${d.case_id}`)}>
                      <td><div className="primary">{d.patient_ref}</div><div className="secondary">{d.practice_name} · {d.payer}</div></td>
                      <td className="right" style={{ color: d.days_until_deadline < 0 ? 'var(--red-700)' : undefined, fontWeight: 600 }}>
                        {d.days_until_deadline < 0 ? `${-d.days_until_deadline}d overdue` : `${d.days_until_deadline}d left`}</td>
                    </tr>
                  ))}
                </tbody></table>
              )}
            </Async>
          </div>
        </div>
      </div>
    </>
  )
}
