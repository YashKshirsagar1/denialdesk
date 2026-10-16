import { useNavigate } from 'react-router-dom'
import { CircleDollarSign, Clock3, Inbox, Upload, Wallet } from 'lucide-react'
import { getClinicDashboard, getDocumentRequests, getOnboardingStatus, listCases } from '../api'
import { useAuth } from '../auth'
import { statusMeta } from '../lib/caseStatus'
import { ago, money, rootCause } from '../lib/format'
import { Alert, Async, Empty, PageHead, Stat, StatusBadge, useAsync } from '../components/ui'

export function ClinicDashboard() {
  const { user } = useAuth()
  const nav = useNavigate()
  const dash = useAsync(getClinicDashboard, [])
  const cases = useAsync(() => listCases(8), [])
  const reqs = useAsync(getDocumentRequests, [])
  const onboarding = useAsync(getOnboardingStatus, [])

  const pending = (reqs.data ?? []).filter((r) => r.status === 'pending').length
  const locked = onboarding.data && onboarding.data.onboarding_status !== 'active'
  const first = (user?.full_name ?? '').replace(/^(dr|mr|mrs|ms|prof)\.?\s+/i, '').split(' ')[0]

  return (
    <>
      <PageHead
        title={`Welcome back${first ? `, ${first}` : ''}`}
        sub="Here’s where your denied claims stand."
        actions={<button className="btn primary" disabled={!!locked} onClick={() => nav('/upload')}><Upload size={16} /> Upload denials</button>}
      />

      <div className="stack">
        {locked && (
          <Alert kind="warn">
            <b>Your account is being set up.</b> We’ll unlock uploads as soon as your BAA and service agreement are countersigned
            (status: {onboarding.data!.onboarding_status.replace(/_/g, ' ')}).
          </Alert>
        )}
        {pending > 0 && (
          <Alert kind="warn">
            <b>{pending} document request{pending > 1 ? 's' : ''} need your attention.</b>{' '}
            <button className="link-btn" onClick={() => nav('/requests')}>Open requests →</button>
          </Alert>
        )}

        <Async state={dash}>
          {(d) => (
            <div className="grid cols-4">
              <Stat label="Recovered" value={money(d.dollars_recovered, false)} tone="green" icon={<CircleDollarSign size={15} />}
                hint={`${d.cases_paid} claim${d.cases_paid === 1 ? '' : 's'} paid`} />
              <Stat label="Submitted for recovery" value={money(d.dollars_submitted, false)} tone="blue" icon={<Wallet size={15} />}
                hint={`${d.total_cases} claims uploaded · ${d.cases_declined} not appealable`} />
              <Stat label="In progress" value={d.cases_in_progress} tone="amber" icon={<Clock3 size={15} />} hint="Being worked by our team" />
              <Stat label="Needs your input" value={pending} tone={pending ? 'red' : 'gray'} icon={<Inbox size={15} />}
                hint={pending ? 'Document requests waiting' : 'Nothing waiting on you'} />
            </div>
          )}
        </Async>

        <div className="card">
          <div className="card-head"><h3>Recent claims</h3><button className="link-btn" onClick={() => nav('/claims')}>View all →</button></div>
          <Async state={cases}>
            {(rows) => rows.length === 0 ? (
              <Empty title="No claims yet" action={!locked && <button className="btn primary" onClick={() => nav('/upload')}>Upload your first batch</button>}>
                Upload denied claims and we’ll start recovering them.
              </Empty>
            ) : (
              <div className="table-wrap"><table className="tbl">
                <thead><tr><th>Patient</th><th>Payer</th><th>Denial reason</th><th className="num">Billed</th><th>Status</th><th>Updated</th></tr></thead>
                <tbody>
                  {rows.map((c) => (
                    <tr key={c.id} className="clickable" onClick={() => nav(`/claims/${c.id}`)}>
                      <td className="primary">{c.patient_ref ?? `#${c.id}`}</td>
                      <td>{c.payer}</td>
                      <td>{rootCause(c.root_cause)}</td>
                      <td className="num">{money(c.billed_amt)}</td>
                      <td><StatusBadge state={c.state} /><div className="secondary">{statusMeta(c.state).detail(c.payer)}</div></td>
                      <td className="muted">{ago(c.updated_at)}</td>
                    </tr>
                  ))}
                </tbody></table></div>
            )}
          </Async>
        </div>
      </div>
    </>
  )
}
