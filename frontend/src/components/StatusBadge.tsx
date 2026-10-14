const STATE_COLORS: Record<string, string> = {
  ingested: '#6c757d',
  diagnosed: '#0d6efd',
  declined: '#dc3545',
  approved: '#198754',
  drafted: '#fd7e14',
  awaiting_human_review: '#ffc107',
  submitted: '#0dcaf0',
  pending_payer: '#6610f2',
  paid: '#198754',
  re_denied: '#dc3545',
  escalated: '#d63384',
  closed: '#6c757d',
};

export function StatusBadge({ state }: { state: string }) {
  const bg = STATE_COLORS[state] ?? '#6c757d';
  return (
    <span style={{
      display: 'inline-block',
      padding: '2px 8px',
      borderRadius: 12,
      fontSize: 11,
      fontWeight: 600,
      color: '#fff',
      background: bg,
      letterSpacing: '0.03em',
      textTransform: 'uppercase',
    }}>
      {state.replace(/_/g, ' ')}
    </span>
  );
}
