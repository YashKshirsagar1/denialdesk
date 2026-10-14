import type { CaseSummary } from '../types';
import { StatusBadge } from './StatusBadge';

function ScoreBar({ score }: { score: number | null }) {
  if (score === null) return <span style={{ color: '#aaa', fontSize: 11 }}>—</span>;
  const pct = Math.round(score * 100);
  const color = score > 0.6 ? '#198754' : score >= 0.3 ? '#ffc107' : '#dc3545';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
      <div style={{ flex: 1, height: 6, background: '#e9ecef', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 3 }} />
      </div>
      <span style={{ fontSize: 11, color, fontWeight: 600, minWidth: 28 }}>{pct}%</span>
    </div>
  );
}

interface Props {
  cases: CaseSummary[];
  selectedId: number | null;
  onSelect: (id: number) => void;
}

export function QueueSidebar({ cases, selectedId, onSelect }: Props) {
  return (
    <aside style={{
      width: 280,
      minWidth: 280,
      borderRight: '1px solid #dee2e6',
      display: 'flex',
      flexDirection: 'column',
      overflowY: 'auto',
      background: '#f8f9fa',
    }}>
      <div style={{ padding: '12px 16px', borderBottom: '1px solid #dee2e6', fontWeight: 700, fontSize: 14 }}>
        Review Queue ({cases.length})
      </div>
      {cases.length === 0 && (
        <div style={{ padding: 24, color: '#6c757d', fontSize: 13, textAlign: 'center' }}>
          No cases in queue
        </div>
      )}
      {cases.map(c => (
        <div
          key={c.id}
          onClick={() => onSelect(c.id)}
          style={{
            padding: '10px 16px',
            borderBottom: '1px solid #dee2e6',
            cursor: 'pointer',
            background: selectedId === c.id ? '#e8f4fd' : undefined,
            borderLeft: selectedId === c.id ? '3px solid #0d6efd' : '3px solid transparent',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
            <span style={{ fontWeight: 600, fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 160 }}>
              {c.payer}
            </span>
            <StatusBadge state={c.state} />
          </div>
          {c.practice_name && (
            <div style={{ fontSize: 11, color: '#6c757d', marginBottom: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {c.practice_name}
            </div>
          )}
          <div style={{ fontSize: 12, color: '#495057', marginBottom: 4 }}>
            CPT {c.cpt} · CARC {c.carc} · ${c.billed_amt.toLocaleString()}
          </div>
          <ScoreBar score={c.winnability_score} />
        </div>
      ))}
    </aside>
  );
}
