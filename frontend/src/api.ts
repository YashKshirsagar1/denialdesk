import { authHeaders } from './auth'
import type {
  AccessLogEntry, BatchSummary, CaseDetail, CaseSummary, ClinicCaseSummary, ClinicDashboard, DeadlineItem,
  DocumentRequest, LoginResponse, OnboardingStatus, OverviewKPIs, PipelineView, PracticeOut, QueueStats,
  ReviewRequest, ReviewResponse, ScoreAccuracy, SessionUser, StatementOut, TeamMember, UploadResult, WinRateTable,
} from './types'

const BASE = '/api'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

/** FastAPI errors carry {detail: string | [{msg}]}; turn either into a readable sentence. */
async function errorMessage(res: Response): Promise<string> {
  try {
    const body = await res.json()
    const d = body?.detail
    if (typeof d === 'string') return d
    if (Array.isArray(d)) return d.map((e) => e.msg).join('; ')
  } catch { /* fall through */ }
  return `Request failed (${res.status})`
}

async function request(path: string, init: RequestInit = {}, auth = true): Promise<Response> {
  const isForm = init.body instanceof FormData
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      ...(isForm ? {} : { 'Content-Type': 'application/json' }),
      ...(auth ? authHeaders() : {}),
      ...init.headers,
    },
  })
  if (!res.ok) {
    // A 401 on a protected call means the session is gone; the login call itself returns 401 for bad credentials.
    if (res.status === 401 && auth) window.dispatchEvent(new Event('dd:unauthorized'))
    throw new ApiError(res.status, await errorMessage(res))
  }
  return res
}

async function api<T>(path: string, init?: RequestInit, auth = true): Promise<T> {
  const res = await request(path, init, auth)
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T)
}

const post = <T>(path: string, body?: unknown) =>
  api<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })

// ---- auth ----
export const login = (email: string, password: string) =>
  api<LoginResponse>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }, false)

export const signup = (body: { practice_name: string; specialty: string; full_name: string; email: string; password: string }) =>
  api<LoginResponse>('/auth/signup', { method: 'POST', body: JSON.stringify(body) }, false)

export const getDemoAccounts = () => api<import('./types').DemoAccounts>('/auth/demo-accounts', undefined, false)
export const getMe = () => api<SessionUser>('/auth/me')
export const changePassword = (current_password: string, new_password: string) =>
  post<void>('/auth/change-password', { current_password, new_password })

// ---- claims ----
export const listCases = (limit = 500) => api<ClinicCaseSummary[]>(`/cases?limit=${limit}`)
export const getCase = (id: number) => api<CaseDetail>(`/cases/${id}`)
export const getQueueStats = () => api<QueueStats>('/queue')
export const getQueueCases = (state = 'awaiting_human_review') =>
  api<CaseSummary[]>(`/queue/cases?state=${encodeURIComponent(state)}`)
export const submitReview = (id: number, req: ReviewRequest) => post<ReviewResponse>(`/cases/${id}/review`, req)

/** Fetch a PDF with the auth header and open it in a new tab (links can't carry a Bearer token). */
export async function openPdf(path: string): Promise<void> {
  const res = await request(path)
  const url = URL.createObjectURL(await res.blob())
  window.open(url, '_blank', 'noopener')
  setTimeout(() => URL.revokeObjectURL(url), 60_000)
}

export async function downloadPdf(path: string, filename: string): Promise<void> {
  const res = await request(path)
  const url = URL.createObjectURL(await res.blob())
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

// ---- upload ----
export function uploadFile(file: File, practiceId?: number): Promise<UploadResult> {
  const fd = new FormData()
  fd.append('file', file)
  if (practiceId !== undefined) fd.append('practice_id', String(practiceId))
  return api<UploadResult>('/upload', { method: 'POST', body: fd })
}
export const startProcessing = (batchId: number) => post(`/batches/${batchId}/process?background=true`)
export const getBatch = (id: number) => api<BatchSummary>(`/batches/${id}`)
export const listBatches = () => api<BatchSummary[]>('/batches')

// ---- clinic ----
export const getClinicDashboard = () => api<ClinicDashboard>('/clinic/dashboard')
export const getOnboardingStatus = () => api<OnboardingStatus>('/clinic/onboarding')
export const getAccessLog = (tenantId?: number) =>
  api<AccessLogEntry[]>(`/clinic/access-log${tenantId !== undefined ? `?tenant_id=${tenantId}` : ''}`)
export const getDocumentRequests = () => api<DocumentRequest[]>('/document-requests')
export const fulfillDocumentRequest = (id: number, file?: File) => {
  const fd = new FormData()
  if (file) fd.append('file', file)
  return api<DocumentRequest>(`/document-requests/${id}/fulfill`, { method: 'POST', body: fd })
}
export const api_listCaseRequests = (caseId: number) => api<DocumentRequest[]>(`/cases/${caseId}/document-requests`)
export const requestDocument = (caseId: number, document_type: string, description: string, requested_by: string) =>
  post<DocumentRequest>(`/cases/${caseId}/document-requests`, { document_type, description, requested_by })

// ---- statements ----
export const getClinicStatements = () => api<StatementOut[]>('/clinic/statements')
export const getOpsStatements = () => api<StatementOut[]>('/ops/statements')
export const generateStatement = (practice_id: number, period_start: string, period_end: string) =>
  post<StatementOut>('/ops/statements/generate', { practice_id, period_start, period_end })
export const markStatementSent = (id: number) => post<StatementOut>(`/ops/statements/${id}/send`)

// ---- ops ----
export const getDeadlines = () => api<DeadlineItem[]>('/ops/deadlines')
export const getKpiOverview = () => api<OverviewKPIs>('/kpis/overview')
export const getWinRates = (minAttempts = 1) => api<WinRateTable>(`/kpis/win-rates?min_attempts=${minAttempts}`)
export const getScoreAccuracy = () => api<ScoreAccuracy>('/kpis/score-accuracy')
export const getPipeline = () => api<PipelineView>('/kpis/pipeline')
export const listPractices = () => api<PracticeOut[]>('/ops/practices')
export const createPractice = (name: string, specialty: string, contact?: string) =>
  post<PracticeOut>('/ops/practices', { name, specialty, contact })
const practiceAction = (id: number, action: string) => post<PracticeOut>(`/ops/practices/${id}/${action}`)
export const signBaa = (id: number) => practiceAction(id, 'sign-baa')
export const signServiceAgreement = (id: number) => practiceAction(id, 'sign-service-agreement')
export const activatePractice = (id: number) => practiceAction(id, 'activate')
export const suspendPractice = (id: number) => practiceAction(id, 'suspend')

export const recordOutcome = (caseId: number, body: { result: string; amount_recovered: number; paid_date?: string; notes?: string }) =>
  post(`/cases/${caseId}/outcome`, body)
export const verifyOutcome = (caseId: number, verified_by: string) =>
  post(`/cases/${caseId}/outcome/verify`, { verification_method: 'clinic_confirmation', verified_by })

// ---- team ----
export const listUsers = () => api<TeamMember[]>('/users')
export const createUser = (body: { email: string; full_name: string; role: string; temp_password: string; tenant_id?: number | null }) =>
  post<TeamMember>('/users', body)
export const updateUser = (id: number, body: { is_active?: boolean; role?: string }) =>
  api<TeamMember>(`/users/${id}`, { method: 'PATCH', body: JSON.stringify(body) })
