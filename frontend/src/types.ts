export interface DiagnosisInfo {
  root_cause: string;
  winnability_score: number;
  expected_value: number;
  rationale: string;
  model_version: string;
}

export interface DraftInfo {
  id: number;
  draft_type: string;
  content: string;
  attachments: string[];
  version: number;
  created_at: string;
}

export interface CaseSummary {
  id: number;
  payer: string;
  patient_ref: string | null;
  cpt: string;
  billed_amt: number;
  carc: string;
  denial_date: string | null;
  state: string;
  winnability_score: number | null;
  root_cause: string | null;
  created_at: string;
  practice_name: string | null;
}

export interface DeadlineItem {
  case_id: number;
  practice_name: string | null;
  payer: string;
  patient_ref: string | null;
  cpt: string;
  billed_amt: number;
  state: string;
  filing_deadline: string;
  days_until_deadline: number;
  urgency: 'overdue' | 'critical' | 'warning' | 'upcoming' | 'ok';
}

export interface TimelineEvent {
  timestamp: string;
  actor: string;
  action: string;
}

export interface OutcomeInfo {
  result: string | null;
  amount_recovered: number;
  paid_date: string | null;
  verified: boolean;
  billable_amount: number | null;
}

export interface CaseDetail extends CaseSummary {
  dos: string | null;
  claim_number: string | null;
  carc_description: string | null;
  modifier: string | null;
  updated_at: string | null;
  timeline: TimelineEvent[];
  outcome: OutcomeInfo | null;
  icd10: string[];
  allowed_amt: number;
  rarc: string;
  filing_deadline: string | null;
  diagnosis: DiagnosisInfo | null;
  drafts: DraftInfo[];
}

export interface QueueStats {
  awaiting_review: number;
  drafted: number;
  submitted: number;
  paid: number;
  declined: number;
  total_active: number;
}

export interface ReviewRequest {
  decision: 'approve' | 'reject' | 'edit';
  edits?: string;
  reviewer?: string;
  notes?: string;
}

export interface ReviewResponse {
  case_id: number;
  new_state: string;
  draft_id: number | null;
  message: string;
}

export interface OverviewKPIs {
  total_cases: number;
  total_attempted: number;
  total_paid: number;
  total_denied_final: number;
  recovery_rate: number;
  total_amount_billed: number;
  total_amount_recovered: number;
  avg_amount_recovered: number;
  total_declined: number;
  decline_rate: number;
  avg_winnability_score: number;
  avg_days_to_payment: number;
  pipeline: Record<string, number>;
}

export interface WinRateRow {
  payer: string;
  reason_code: string;
  specialty: string;
  attempts: number;
  wins: number;
  win_rate: number;
}

export interface WinRateTable {
  rows: WinRateRow[];
  total_rows: number;
}

export interface ScoreAccuracyRow {
  score_bucket: string;
  count: number;
  actual_win_rate: number;
  avg_predicted_score: number;
}

export interface ScoreAccuracy {
  rows: ScoreAccuracyRow[];
  correlation_note: string;
}

export interface PipelineStage {
  state: string;
  count: number;
  pct: number;
}

export interface PipelineView {
  stages: PipelineStage[];
  total: number;
}

export interface ClinicCaseSummary {
  id: number;
  payer: string;
  patient_ref: string | null;
  dos: string | null;
  cpt: string;
  billed_amt: number;
  carc: string;
  denial_date: string | null;
  state: string;
  winnability_score: number | null;
  root_cause: string | null;
  updated_at: string;
  practice_name: string | null;
  filing_deadline: string | null;
}

export interface DocumentRequest {
  id: number;
  case_id: number;
  tenant_id: number | null;
  requested_by: string;
  document_type: string;
  description: string;
  status: 'pending' | 'fulfilled' | 'cancelled';
  created_at: string;
  fulfilled_at: string | null;
  file_path: string | null;
}

export interface ClinicDashboard {
  dollars_submitted: number;
  dollars_recovered: number;
  cases_in_progress: number;
  cases_paid: number;
  cases_declined: number;
  total_cases: number;
}

export interface AccessLogEntry {
  id: number;
  actor_id: string;
  actor_role: string;
  resource: string;
  action: string;
  http_method: string;
  path: string;
  timestamp: string;
}

export interface OnboardingChecklist {
  baa_signed: boolean;
  service_agreement_signed: boolean;
  practice_details: boolean;
  specialties: boolean;
  payers_billed: boolean;
  payer_portal_access: boolean;
}

export interface OnboardingStatus {
  practice_id: number;
  name: string;
  onboarding_status: string;
  baa_signed: boolean;
  service_agreement_signed: boolean;
  details_complete: boolean;
  checklist: OnboardingChecklist;
}

export interface StatementOut {
  id: number;
  practice_id: number;
  practice_name: string | null;
  period_start: string;
  period_end: string;
  total_recovered: number;
  fee_amount: number;
  status: 'draft' | 'sent' | 'paid';
  generated_at: string;
  sent_at: string | null;
  stripe_invoice_id: string | null;
  pdf_path: string | null;
}

export interface PracticeOut {
  id: number;
  name: string;
  specialty: string;
  contact: string | null;
  onboarding_status: string;
  baa_signed: boolean;
  service_agreement_signed: boolean;
  address: string | null;
  phone: string | null;
  npi: string | null;
  specialties: string[] | null;
  payers_billed: string[] | null;
}

export type Role = 'clinic_admin' | 'clinic_staff' | 'reviewer' | 'ops_admin';

export interface SessionUser {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  tenant_id: number | null;
  practice_name: string | null;
  must_change_password: boolean;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: SessionUser;
}

export interface BatchSummary {
  id: number;
  practice_id: number;
  practice_name: string | null;
  filename: string | null;
  uploaded_at: string;
  total: number;
  analyzing: number;
  declined: number;
  in_progress: number;
  paid: number;
  done: boolean;
}

export interface UploadResult {
  batch_id: number;
  practice_id: number;
  case_count: number;
  errors: string[];
}

export interface TeamMember {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  tenant_id: number | null;
  practice_name: string | null;
  is_active: boolean;
  last_login_at: string | null;
}

export interface DemoAccounts {
  password: string;
  accounts: { email: string; full_name: string; role: Role }[];
}
