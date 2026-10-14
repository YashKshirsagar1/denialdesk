import { authHeaders } from './auth'
import type { CaseDetail, ClinicCaseSummary, ClinicDashboard, CaseSummary, OverviewKPIs, PipelineView, ReviewRequest, ReviewResponse, ScoreAccuracy, WinRateTable } from './types'

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
