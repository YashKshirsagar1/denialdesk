import { useNavigate } from 'react-router-dom'
import { CalendarClock } from 'lucide-react'
import { getDeadlines } from '../api'
import { date, money } from '../lib/format'
import { Async, Badge, Empty, PageHead, StatusBadge, useAsync } from '../components/ui'
import type { Tone } from '../lib/caseStatus'

const URGENCY: Record<string, { label: string; tone: Tone }> = {
  overdue: { label: 'Overdue', tone: 'red' },
  critical: { label: 'Due in ≤3 days', tone: 'red' },
  warning: { label: 'Due in ≤7 days', tone: 'amber' },
  upcoming: { label: 'Due in ≤14 days', tone: 'blue' },
  ok: { label: 'On track', tone: 'green' },
}

export function Deadlines() {
  const nav = useNavigate()
  const dl = useAsync(getDeadlines, [])
  return (
    <>
      <PageHead title="Deadlines" sub="Every open case, soonest appeal deadline first. We never miss a filing window." />
      <div className="card">
        <Async state={dl}>
          {(rows) => rows.length === 0 ? <Empty title="No open deadlines" icon={<CalendarClock size={24} />} /> : (
            <div className="table-wrap"><table className="tbl">
              <thead><tr><th>Deadline</th><th>Patient</th><th>Practice</th><th>Payer</th><th className="num">Billed</th><th>Stage</th><th>Urgency</th></tr></thead>
              <tbody>
                {rows.map((d) => (
                  <tr key={d.case_id} className="clickable" onClick={() => nav(`/claims/${d.case_id}`)}>
                    <td><div className="primary">{date(d.filing_deadline)}</div>
                      <div className="secondary">{d.days_until_deadline < 0 ? `${-d.days_until_deadline} days ago` : `in ${d.days_until_deadline} days`}</div></td>
                    <td className="primary">{d.patient_ref}</td><td>{d.practice_name}</td><td>{d.payer}</td>
                    <td className="num">{money(d.billed_amt)}</td><td><StatusBadge state={d.state} /></td>
                    <td><Badge tone={URGENCY[d.urgency].tone}>{URGENCY[d.urgency].label}</Badge></td>
                  </tr>
                ))}
              </tbody></table></div>
          )}
        </Async>
      </div>
    </>
  )
}
