export type Tone = 'blue' | 'green' | 'amber' | 'red' | 'violet' | 'gray'

interface StatusMeta {
  label: string
  tone: Tone
  /** Plain-English line for clinics. */
  detail: (payer: string) => string
  group: 'analyzing' | 'review' | 'submitted' | 'paid' | 'declined' | 'denied'
}

const META: Record<string, StatusMeta> = {
  ingested: { label: 'Analyzing', tone: 'gray', group: 'analyzing', detail: () => 'Received — our AI is analyzing this denial' },
  diagnosed: { label: 'Analyzing', tone: 'gray', group: 'analyzing', detail: () => 'Denial analysis in progress' },
  approved: { label: 'Drafting', tone: 'blue', group: 'review', detail: () => 'Approved for appeal — drafting the letter' },
  drafted: { label: 'Drafting', tone: 'blue', group: 'review', detail: () => 'Appeal letter drafted' },
  awaiting_human_review: { label: 'In review', tone: 'amber', group: 'review', detail: () => 'Appeal letter ready — with our team for review' },
  submitted: { label: 'Submitted', tone: 'violet', group: 'submitted', detail: (p) => `Appeal submitted to ${p}` },
  pending_payer: { label: 'Pending payer', tone: 'violet', group: 'submitted', detail: (p) => `Waiting for a response from ${p}` },
  escalated: { label: 'Escalated', tone: 'violet', group: 'submitted', detail: () => 'Escalated to a second-level appeal' },
  paid: { label: 'Paid', tone: 'green', group: 'paid', detail: () => 'Recovered — payment received' },
  declined: { label: 'Not appealable', tone: 'red', group: 'declined', detail: () => 'We reviewed this and don’t recommend an appeal' },
  re_denied: { label: 'Re-denied', tone: 'red', group: 'denied', detail: (p) => `${p} upheld the denial` },
  closed: { label: 'Closed', tone: 'gray', group: 'denied', detail: () => 'Closed' },
}

export function statusMeta(state: string): StatusMeta {
  return META[state] ?? { label: state, tone: 'gray', group: 'analyzing', detail: () => state }
}

export const FILTER_GROUPS: { key: string; label: string; match: (state: string) => boolean }[] = [
  { key: 'all', label: 'All', match: () => true },
  { key: 'review', label: 'In review', match: (s) => statusMeta(s).group === 'review' },
  { key: 'submitted', label: 'Submitted', match: (s) => statusMeta(s).group === 'submitted' },
  { key: 'paid', label: 'Paid', match: (s) => s === 'paid' },
  { key: 'declined', label: 'Not appealable', match: (s) => s === 'declined' },
]

// Kept for older call sites.
export function formatCaseStatus(state: string, payer?: string): string {
  return statusMeta(state).detail(payer || 'payer')
}
export function statusColor(state: string): string {
  const t = statusMeta(state).tone
  return { green: '#137a3f', red: '#b42323', violet: '#5b3fc4', amber: '#9a5b00', blue: '#1664c0', gray: '#4b586a' }[t]
}
