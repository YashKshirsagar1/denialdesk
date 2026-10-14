import type { DeadlineItem } from '../types'

interface Props {
  deadlines: DeadlineItem[]
}

function rowStyle(urgency: string): React.CSSProperties {
  if (urgency === 'overdue') return { background: '#fee2e2' }
  if (urgency === 'critical') return { background: '#ffedd5' }
  if (urgency === 'warning') return { background: '#fefce8' }
  return { background: '#fff' }
}

function daysLabel(days: number, urgency: string): React.CSSProperties {
  if (urgency === 'overdue') return { color: '#b91c1c', fontWeight: 700 }
  if (urgency === 'critical') return { color: '#c2410c', fontWeight: 700 }
  if (urgency === 'warning') return { color: '#a16207', fontWeight: 600 }
  return { color: '#374151' }
}

function formatDays(days: number): string {
  if (days < 0) return `${days} days`
  if (days === 0) return 'today'
  return `${days} days`
}

export function DeadlineView({ deadlines }: Props) {
  if (deadlines.length === 0) {
    return (
      <div style={{ padding: 24 }}>
        <h2 style={{ margin: '0 0 16px', fontSize: 20 }}>Deadlines</h2>
        <div style={{ color: '#6c757d', fontSize: 14 }}>No active deadlines.</div>
      </div>
    )
  }

  return (
    <div style={{ padding: 24 }}>
      <h2 style={{ margin: '0 0 16px', fontSize: 20 }}>Deadlines</h2>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, background: '#fff', border: '1px solid #dee2e6', borderRadius: 6, overflow: 'hidden' }}>
        <thead>
          <tr style={{ borderBottom: '2px solid #dee2e6', background: '#f8f9fa' }}>
            {['Practice', 'Patient', 'Payer', 'CPT', 'Amount', 'State', 'Deadline', 'Days Left'].map(h => (
              <th key={h} style={{ textAlign: 'left', padding: '8px 12px', color: '#6c757d', fontWeight: 600, fontSize: 12 }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {deadlines.map(d => (
            <tr key={d.case_id} style={{ ...rowStyle(d.urgency), borderBottom: '1px solid #f1f3f5' }}>
              <td style={{ padding: '7px 12px' }}>{d.practice_name ?? '—'}</td>
              <td style={{ padding: '7px 12px', fontFamily: 'monospace', fontSize: 12 }}>{d.patient_ref ?? '—'}</td>
              <td style={{ padding: '7px 12px' }}>{d.payer}</td>
              <td style={{ padding: '7px 12px' }}>{d.cpt}</td>
              <td style={{ padding: '7px 12px' }}>${d.billed_amt.toLocaleString()}</td>
              <td style={{ padding: '7px 12px', color: '#6c757d' }}>{d.state.replace(/_/g, ' ')}</td>
              <td style={{ padding: '7px 12px' }}>{d.filing_deadline}</td>
              <td style={{ padding: '7px 12px', ...daysLabel(d.days_until_deadline, d.urgency) }}>
                {formatDays(d.days_until_deadline)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
