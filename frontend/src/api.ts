import type { CaseDetail, CaseSummary, ReviewRequest, ReviewResponse } from './types';

const BASE = '/api';

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export function getQueueCases(state = 'awaiting_human_review,drafted'): Promise<CaseSummary[]> {
  return apiFetch<CaseSummary[]>(`/queue/cases?state=${encodeURIComponent(state)}`);
}

export function getCaseDetail(id: number): Promise<CaseDetail> {
  return apiFetch<CaseDetail>(`/cases/${id}`);
}

export function submitReview(id: number, req: ReviewRequest): Promise<ReviewResponse> {
  return apiFetch<ReviewResponse>(`/cases/${id}/review`, {
    method: 'POST',
    body: JSON.stringify(req),
  });
}
