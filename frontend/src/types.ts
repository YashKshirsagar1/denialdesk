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
