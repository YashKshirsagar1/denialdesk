export function formatCaseStatus(state: string, payer?: string, updatedAt?: string): string {
  const date = updatedAt
    ? new Date(updatedAt).toLocaleDateString('en-US', { month: 'numeric', day: 'numeric' })
    : ''
  const payerName = payer || 'payer'
  const map: Record<string, string> = {
    ingested: 'Received — analyzing claim',
    diagnosed: 'Review in progress',
    declined: 'Declined — not pursuing appeal',
    approved: 'Approved for appeal',
    drafted: 'Appeal draft in progress',
    awaiting_human_review: 'Appeal under internal review',
    submitted: date
      ? `Appeal submitted to ${payerName} on ${date}`
      : `Appeal submitted to ${payerName}`,
    pending_payer: `Waiting for response from ${payerName}`,
    paid: 'Paid',
    re_denied: 'Re-denied — escalating',
    escalated: 'Escalated to second-level appeal',
    closed: 'Closed',
  }
  return map[state] ?? state
}

export function statusColor(state: string): string {
  if (['paid'].includes(state)) return '#15803d'        // green-700
  if (['declined', 'closed', 're_denied'].includes(state)) return '#dc2626'  // red-600
  if (['submitted', 'pending_payer', 'escalated'].includes(state)) return '#2563eb'  // blue-600
  return '#6b7280'  // gray-600
}
