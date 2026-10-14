import { useEffect, useState } from 'react'
import { getAllCases, getClinicDashboard, getCaseDetail } from '../api'
import { clearToken } from '../auth'
import { formatCaseStatus, statusColor } from '../lib/caseStatus'
import { UploadForm } from './UploadForm'
import type { ClinicCaseSummary, ClinicDashboard, CaseDetail } from '../types'

type Tab = 'upload' | 'claims' | 'dashboard'

const tabBtn = (active: boolean): React.CSSProperties => ({
  padding: '8px 20px',
  background: 'none',
  border: 'none',
  borderBottom: active ? '2px solid #0d6efd' : '2px solid transparent',
  fontWeight: active ? 700 : 400,
  color: active ? '#0d6efd' : '#495057',
  cursor: 'pointer',
  fontSize: 14,
})

const statCard = (label: string, value: string, sub?: string) => (
  <div style={{
    background: '#fff',
    border: '1px solid #dee2e6',
    borderRadius: 8,
    padding: '20px 24px',
    minWidth: 160,
    flex: 1,
  }}>
    <div style={{ fontSize: 13, color: '#6c757d', marginBottom: 6 }}>{label}</div>
    <div style={{ fontSize: 28, fontWeight: 700, color: '#212529' }}>{value}</div>
    {sub && <div style={{ fontSize: 12, color: '#6c757d', marginTop: 4 }}>{sub}</div>}
  </div>
)

function fmt$(n: number) {
  return '$' + n.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })
}

interface Props {
  onLogout: () => void
}

export function ClinicPortal({ onLogout }: Props) {
  const [activeTab, setActiveTab] = useState<Tab>('claims')
  const [cases, setCases] = useState<ClinicCaseSummary[]>([])
  const [dashboard, setDashboard] = useState<ClinicDashboard | null>(null)
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const [expandedDetail, setExpandedDetail] = useState<CaseDetail | null>(null)
  const [loadingCases, setLoadingCases] = useState(false)
  const [loadingDash, setLoadingDash] = useState(false)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function loadCases() {
    setLoadingCases(true)
    setError(null)
    try {
      const data = await getAllCases()
      setCases(data)
    } catch (e) {
      setError(String(e))
    } finally {
      setLoadingCases(false)
    }
  }

  async function loadDashboard() {
    setLoadingDash(true)
    setError(null)
    try {
      const data = await getClinicDashboard()
      setDashboard(data)
    } catch (e) {
      setError(String(e))
    } finally {
      setLoadingDash(false)
    }
  }

  useEffect(() => {
    loadCases()
  }, [])

  useEffect(() => {
    if (activeTab === 'dashboard' && dashboard === null) {
      loadDashboard()
    }
  }, [activeTab])

  async function toggleExpand(id: number) {
    if (expandedId === id) {
      setExpandedId(null)
      setExpandedDetail(null)
      return
    }
    setExpandedId(id)
    setExpandedDetail(null)
    setLoadingDetail(true)
    try {
      const detail = await getCaseDetail(id)
      setExpandedDetail(detail)
    } catch {
      setExpandedDetail(null)
    } finally {
      setLoadingDetail(false)
    }
  }

  const recoveryRate = dashboard
    ? dashboard.dollars_submitted > 0
      ? ((dashboard.dollars_recovered / dashboard.dollars_submitted) * 100).toFixed(1) + '%'
      : '—'
    : '—'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', fontFamily: 'system-ui, sans-serif', fontSize: 14, color: '#212529' }}>
      {/* Header */}
      <div style={{ borderBottom: '1px solid #dee2e6', padding: '0 16px', display: 'flex', alignItems: 'center', background: '#fff', flexShrink: 0 }}>
        <span style={{ fontWeight: 700, fontSize: 15, marginRight: 16, color: '#212529' }}>DenialDesk</span>
        <button style={tabBtn(activeTab === 'upload')} onClick={() => setActiveTab('upload')}>Upload Claims</button>
        <button style={tabBtn(activeTab === 'claims')} onClick={() => setActiveTab('claims')}>My Claims</button>
        <button style={tabBtn(activeTab === 'dashboard')} onClick={() => setActiveTab('dashboard')}>Dashboard</button>
        <div style={{ marginLeft: 'auto' }}>
          <button
            onClick={onLogout}
            style={{ padding: '4px 12px', fontSize: 12, background: 'none', border: '1px solid #dee2e6', borderRadius: 4, cursor: 'pointer', color: '#6c757d' }}
          >
            Sign out
          </button>
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', background: '#f8f9fa' }}>
        {error && (
          <div style={{ margin: 16, background: '#f8d7da', color: '#58151c', padding: '10px 14px', borderRadius: 4 }}>
            {error}
          </div>
        )}

        {/* Upload tab */}
        {activeTab === 'upload' && <UploadForm />}

        {/* Dashboard tab */}
        {activeTab === 'dashboard' && (
          <div style={{ padding: 24 }}>
            <h2 style={{ margin: '0 0 20px', fontSize: 18 }}>Recovery Overview</h2>
            {loadingDash && <div style={{ color: '#6c757d' }}>Loading...</div>}
            {dashboard && (
              <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                {statCard('Total Submitted', fmt$(dashboard.dollars_submitted), `${dashboard.total_cases} claims`)}
                {statCard('Recovered', fmt$(dashboard.dollars_recovered))}
                {statCard('In Progress', String(dashboard.cases_in_progress), 'claims active')}
                {statCard('Recovery Rate', recoveryRate, 'of submitted dollars')}
              </div>
            )}
          </div>
        )}

        {/* Claims tab */}
        {activeTab === 'claims' && (
          <div style={{ padding: 24 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <h2 style={{ margin: 0, fontSize: 18 }}>My Claims</h2>
              <button
                onClick={loadCases}
                style={{ padding: '4px 12px', fontSize: 12, background: 'none', border: '1px solid #ced4da', borderRadius: 4, cursor: 'pointer', color: '#6c757d' }}
              >
                Refresh
              </button>
            </div>

            {loadingCases && <div style={{ color: '#6c757d' }}>Loading claims...</div>}

            {!loadingCases && cases.length === 0 && (
              <div style={{ color: '#6c757d', textAlign: 'center', padding: '40px 0' }}>
                No claims yet. Upload a batch to get started.
              </div>
            )}

            {!loadingCases && cases.length > 0 && (
              <div style={{ background: '#fff', border: '1px solid #dee2e6', borderRadius: 8, overflow: 'hidden' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                  <thead>
                    <tr style={{ background: '#f8f9fa', borderBottom: '1px solid #dee2e6' }}>
                      <th style={{ textAlign: 'left', padding: '10px 14px', fontWeight: 600, color: '#6c757d', fontSize: 12 }}>Patient</th>
                      <th style={{ textAlign: 'left', padding: '10px 14px', fontWeight: 600, color: '#6c757d', fontSize: 12 }}>DOS</th>
                      <th style={{ textAlign: 'left', padding: '10px 14px', fontWeight: 600, color: '#6c757d', fontSize: 12 }}>CPT</th>
                      <th style={{ textAlign: 'left', padding: '10px 14px', fontWeight: 600, color: '#6c757d', fontSize: 12 }}>Payer</th>
                      <th style={{ textAlign: 'right', padding: '10px 14px', fontWeight: 600, color: '#6c757d', fontSize: 12 }}>Billed</th>
                      <th style={{ textAlign: 'left', padding: '10px 14px', fontWeight: 600, color: '#6c757d', fontSize: 12 }}>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cases.map((c, i) => (
                      <>
                        <tr
                          key={c.id}
                          onClick={() => toggleExpand(c.id)}
                          style={{
                            borderBottom: '1px solid #dee2e6',
                            cursor: 'pointer',
                            background: expandedId === c.id ? '#f0f4ff' : i % 2 === 0 ? '#fff' : '#fafafa',
                          }}
                        >
                          <td style={{ padding: '10px 14px' }}>{c.patient_ref || '—'}</td>
                          <td style={{ padding: '10px 14px', color: '#6c757d' }}>{c.dos || '—'}</td>
                          <td style={{ padding: '10px 14px' }}>{c.cpt || '—'}</td>
                          <td style={{ padding: '10px 14px' }}>{c.payer}</td>
                          <td style={{ padding: '10px 14px', textAlign: 'right' }}>
                            ${(c.billed_amt || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                          </td>
                          <td style={{ padding: '10px 14px' }}>
                            <span style={{ color: statusColor(c.state), fontWeight: 500 }}>
                              {formatCaseStatus(c.state, c.payer, c.updated_at)}
                            </span>
                          </td>
                        </tr>

                        {expandedId === c.id && (
                          <tr key={`${c.id}-detail`}>
                            <td colSpan={6} style={{ padding: '16px 20px', background: '#f0f4ff', borderBottom: '1px solid #dee2e6' }}>
                              {loadingDetail && <div style={{ color: '#6c757d', fontSize: 12 }}>Loading details...</div>}
                              {!loadingDetail && expandedDetail && (
                                <div style={{ fontSize: 13 }}>
                                  {expandedDetail.diagnosis && (
                                    <div style={{ marginBottom: 10 }}>
                                      <strong>Diagnosis:</strong> {expandedDetail.diagnosis.root_cause.replace(/_/g, ' ')}
                                      {' — '}
                                      <span style={{ color: '#6c757d' }}>{expandedDetail.diagnosis.rationale}</span>
                                    </div>
                                  )}
                                  {expandedDetail.drafts.length > 0 && (
                                    <div>
                                      <strong>Appeal draft:</strong>{' '}
                                      <span style={{ color: '#6c757d' }}>
                                        {expandedDetail.drafts[0].draft_type} (v{expandedDetail.drafts[0].version})
                                      </span>
                                    </div>
                                  )}
                                  {!expandedDetail.diagnosis && expandedDetail.drafts.length === 0 && (
                                    <span style={{ color: '#6c757d' }}>Claim received — analysis in progress</span>
                                  )}
                                </div>
                              )}
                            </td>
                          </tr>
                        )}
                      </>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
