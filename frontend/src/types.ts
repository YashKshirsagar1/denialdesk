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
}

export interface CaseDetail extends CaseSummary {
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
