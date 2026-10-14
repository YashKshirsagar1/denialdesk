import { authHeaders } from './auth'
import type { AccessLogEntry, CaseDetail, ClinicCaseSummary, ClinicDashboard, CaseSummary, DeadlineItem, DocumentRequest, OnboardingStatus, PracticeOut, OverviewKPIs, PipelineView, ReviewRequest, ReviewResponse, ScoreAccuracy, StatementOut, WinRateTable } from './types'

const BASE = '/api'

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...authHeaders(), ...init?.headers },
    ...init,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`API ${res.status}: ${text}`)
  }
  return res.json() as Promise<T>
}

export function getQueueCases(state = 'awaiting_human_review,drafted'): Promise<CaseSummary[]> {
  return apiFetch<CaseSummary[]>(`/queue/cases?state=${encodeURIComponent(state)}`)
}

export function getCaseDetail(id: number): Promise<CaseDetail> {
  return apiFetch<CaseDetail>(`/cases/${id}`)
}

export function submitReview(id: number, req: ReviewRequest): Promise<ReviewResponse> {
  return apiFetch<ReviewResponse>(`/cases/${id}/review`, {
    method: 'POST',
    body: JSON.stringify(req),
  })
}

export function getKpiOverview(): Promise<OverviewKPIs> {
  return apiFetch<OverviewKPIs>('/kpis/overview')
}

export function getWinRates(minAttempts = 1): Promise<WinRateTable> {
  return apiFetch<WinRateTable>(`/kpis/win-rates?min_attempts=${minAttempts}`)
}

export function getScoreAccuracy(): Promise<ScoreAccuracy> {
  return apiFetch<ScoreAccuracy>('/kpis/score-accuracy')
}

export function getPipeline(): Promise<PipelineView> {
  return apiFetch<PipelineView>('/kpis/pipeline')
}

export function getAllCases(limit = 100, offset = 0): Promise<ClinicCaseSummary[]> {
  return apiFetch<ClinicCaseSummary[]>(`/cases?limit=${limit}&offset=${offset}`)
}

export function getClinicDashboard(): Promise<ClinicDashboard> {
  return apiFetch<ClinicDashboard>('/clinic/dashboard')
}

export function getDeadlines(): Promise<DeadlineItem[]> {
  return apiFetch<DeadlineItem[]>('/ops/deadlines')
}

export function getDocumentRequests(): Promise<DocumentRequest[]> {
  return apiFetch<DocumentRequest[]>('/document-requests')
}

export function getAccessLog(tenantId?: number): Promise<AccessLogEntry[]> {
  const params = tenantId !== undefined ? `?tenant_id=${tenantId}` : ''
  return apiFetch<AccessLogEntry[]>(`/clinic/access-log${params}`)
}

export function getOnboardingStatus(): Promise<OnboardingStatus> {
  return apiFetch<OnboardingStatus>('/clinic/onboarding')
}

export function listPractices(): Promise<PracticeOut[]> {
  return apiFetch<PracticeOut[]>('/ops/practices')
}

export function createPractice(name: string, specialty: string, contact?: string): Promise<PracticeOut> {
  return apiFetch<PracticeOut>('/ops/practices', {
    method: 'POST',
    body: JSON.stringify({ name, specialty, contact }),
  })
}

export function signBaa(practiceId: number): Promise<PracticeOut> {
  return apiFetch<PracticeOut>(`/ops/practices/${practiceId}/sign-baa`, { method: 'POST' })
}

export function signServiceAgreement(practiceId: number): Promise<PracticeOut> {
  return apiFetch<PracticeOut>(`/ops/practices/${practiceId}/sign-service-agreement`, { method: 'POST' })
}

export function activatePractice(practiceId: number): Promise<PracticeOut> {
  return apiFetch<PracticeOut>(`/ops/practices/${practiceId}/activate`, { method: 'POST' })
}

export function suspendPractice(practiceId: number): Promise<PracticeOut> {
  return apiFetch<PracticeOut>(`/ops/practices/${practiceId}/suspend`, { method: 'POST' })
}

export function getClinicStatements(): Promise<StatementOut[]> {
  return apiFetch<StatementOut[]>('/clinic/statements')
}

export function getOpsStatements(): Promise<StatementOut[]> {
  return apiFetch<StatementOut[]>('/ops/statements')
}

export function generateStatement(practiceId: number, periodStart: string, periodEnd: string): Promise<StatementOut> {
  return apiFetch<StatementOut>('/ops/statements/generate', {
    method: 'POST',
    body: JSON.stringify({ practice_id: practiceId, period_start: periodStart, period_end: periodEnd }),
  })
}

export function markStatementSent(statementId: number): Promise<StatementOut> {
  return apiFetch<StatementOut>(`/ops/statements/${statementId}/send`, { method: 'POST' })
}

export function downloadStatementPdf(statementId: number): void {
  const token = authHeaders().Authorization
  const headers = token ? `&token=ignored` : ''
  // Use window.open for file download — auth header injected via fetch below
  fetch(`/api/statements/${statementId}/pdf`, {
    headers: token ? { Authorization: token } : {},
  }).then(async (res) => {
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `statement_${statementId}.pdf`
    a.click()
    URL.revokeObjectURL(url)
  })
}

export function fulfillDocumentRequest(reqId: number, file?: File): Promise<DocumentRequest> {
  const formData = new FormData()
  if (file) formData.append('file', file)
  const token = authHeaders().Authorization
  return fetch(`${BASE}/document-requests/${reqId}/fulfill`, {
    method: 'POST',
    headers: token ? { Authorization: token } : {},
    body: formData,
  }).then(async (res) => {
    if (!res.ok) {
      const text = await res.text()
      throw new Error(`API ${res.status}: ${text}`)
    }
    return res.json() as Promise<DocumentRequest>
  })
}
