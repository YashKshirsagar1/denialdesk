import { ShieldCheck } from 'lucide-react'
import { getAccessLog } from '../api'
import { dateTime } from '../lib/format'
import { Async, Badge, Empty, PageHead, useAsync } from '../components/ui'

export function AccessLog() {
  const log = useAsync(() => getAccessLog(), [])
  return (
    <>
      <PageHead title="Access log" sub="Every time patient data is viewed or changed — who, what and when. Required for HIPAA." />
      <div className="card">
        <Async state={log}>
          {(rows) => rows.length === 0 ? <Empty title="No activity yet" icon={<ShieldCheck size={24} />} /> : (
            <div className="table-wrap"><table className="tbl">
              <thead><tr><th>When</th><th>Who</th><th>Action</th><th>Resource</th></tr></thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id}>
                    <td className="nowrap">{dateTime(r.timestamp)}</td>
                    <td><span className="mono">{r.actor_id}</span> <span className="faint">· {r.actor_role.replace(/_/g, ' ')}</span></td>
                    <td><Badge tone={r.action === 'read' ? 'gray' : 'blue'} plain>{r.action}</Badge></td>
                    <td className="mono">{r.resource}</td>
                  </tr>
                ))}
              </tbody></table></div>
          )}
        </Async>
      </div>
    </>
  )
}
