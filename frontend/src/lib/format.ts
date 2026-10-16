export function money(n: number | null | undefined, cents = true): string {
  const v = n ?? 0
  return v.toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: cents ? 2 : 0,
    maximumFractionDigits: cents ? 2 : 0,
  })
}

export function pct(n: number | null | undefined, digits = 0): string {
  return `${((n ?? 0) * 100).toFixed(digits)}%`
}

// Date-only strings ("2026-07-01") must not be parsed as UTC midnight, or they show a day early.
function parse(d: string): Date {
  return /^\d{4}-\d{2}-\d{2}$/.test(d) ? new Date(`${d}T00:00:00`) : new Date(d)
}

export function date(d: string | null | undefined): string {
  if (!d) return '—'
  return parse(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

export function dateTime(d: string | null | undefined): string {
  if (!d) return '—'
  return new Date(d).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
}

export function ago(d: string | null | undefined): string {
  if (!d) return '—'
  const secs = (Date.now() - new Date(d).getTime()) / 1000
  if (secs < 60) return 'just now'
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`
  if (secs < 86400 * 30) return `${Math.floor(secs / 86400)}d ago`
  return date(d)
}

export function daysFromNow(d: string): number {
  const ms = parse(d).getTime() - new Date().setHours(0, 0, 0, 0)
  return Math.round(ms / 86400000)
}

export const ROOT_CAUSE_LABELS: Record<string, string> = {
  missing_prior_auth: 'Missing prior authorization',
  coding_error: 'Coding error',
  eligibility: 'Eligibility / coverage',
  medical_necessity: 'Medical necessity',
  timely_filing: 'Timely filing',
  bundling_ncci: 'Bundling / NCCI edit',
  duplicate: 'Duplicate claim',
  missing_info: 'Missing information',
  not_covered: 'Service not covered',
  other: 'Other',
}

export function rootCause(rc: string | null | undefined): string {
  if (!rc) return '—'
  return ROOT_CAUSE_LABELS[rc] ?? rc.replace(/_/g, ' ')
}

export const ATTACHMENT_LABELS: Record<string, string> = {
  clinical_notes: 'Clinical / chart notes',
  physician_letter: 'Physician letter of medical necessity',
  prior_auth_request: 'Prior authorization request',
  corrected_claim_form: 'Corrected claim form (CMS-1500)',
  coding_rationale: 'Coding rationale',
  eligibility_verification: 'Eligibility verification',
  insurance_card_copy: 'Copy of insurance card',
  clinical_guidelines: 'Supporting clinical guidelines',
  proof_of_timely_filing: 'Proof of timely filing',
  system_logs: 'Clearinghouse / system logs',
  certified_mail_receipt: 'Certified mail receipt',
  modifier_justification: 'Modifier justification',
  operative_report: 'Operative / procedure report',
  original_claim_copy: 'Copy of original claim',
  remittance_advice: 'Remittance advice (ERA / EOB)',
  completed_claim_form: 'Completed claim form',
  supporting_documentation: 'Supporting documentation',
  plan_documents: 'Plan documents / policy citation',
  medical_necessity_letter: 'Medical necessity letter',
  eob: 'Explanation of benefits (EOB)',
}

export function attachmentLabel(a: string): string {
  return ATTACHMENT_LABELS[a] ?? a.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase())
}

export const DOC_TYPE_LABELS: Record<string, string> = {
  chart_note: 'Chart note',
  medical_records: 'Medical records',
  prior_auth: 'Prior authorization',
  eob: 'EOB',
  insurance_card: 'Insurance card',
  other: 'Document',
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  return (parts[0]?.[0] ?? '?').concat(parts.length > 1 ? parts[parts.length - 1][0] : '').toUpperCase()
}

export const ROLE_LABELS: Record<string, string> = {
  clinic_admin: 'Clinic admin',
  clinic_staff: 'Clinic staff',
  reviewer: 'Appeals reviewer',
  ops_admin: 'DenialDesk admin',
}

/** Friendly sentence for an audit-trail action string. */
export function timelineText(action: string): string {
  const [head, note] = action.split(' | ')
  const m = head.match(/^state_transition:(\w+)->(\w+)$/)
  const to = m?.[2]
  const byTo: Record<string, string> = {
    diagnosed: 'Denial analyzed',
    declined: 'Declined — appeal not recommended',
    approved: 'Approved for appeal',
    drafted: 'Appeal letter drafted',
    awaiting_human_review: 'Sent to appeals team for review',
    submitted: note?.includes('rejected') ? 'Returned for redrafting' : 'Appeal approved and submitted',
    pending_payer: 'Waiting on payer response',
    paid: 'Payment received',
    re_denied: 'Payer upheld the denial',
    escalated: 'Escalated to second-level appeal',
    closed: 'Case closed',
  }
  if (to === 'drafted' && note?.includes('rejected')) return 'Draft returned for revision'
  if (to && byTo[to]) return byTo[to]
  if (head.startsWith('ingested')) return 'Claim received'
  if (head.startsWith('document_request_created')) return 'Document requested from clinic'
  return head.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase())
}

export function docTypeLabel(t: string): string {
  return DOC_TYPE_LABELS[t] ?? t.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase())
}
