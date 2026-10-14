import { useEffect, useState } from 'react'
import { activatePractice, getCaseDetail, getDeadlines, getQueueCases, listPractices, signBaa, signServiceAgreement, suspendPractice } from '../api'
import { clearToken } from '../auth'
import { CaseDetailPanel } from './CaseDetail'
import { Dashboard } from './Dashboard'
import { DeadlineView } from './DeadlineView'
import { DraftEditor } from './DraftEditor'
import { OutcomeForm } from './OutcomeForm'
import { QueueSidebar } from './QueueSidebar'
import { ReviewPanel } from './ReviewPanel'
import { UploadForm } from './UploadForm'
import type { CaseDetail, CaseSummary, DeadlineItem, DraftInfo, PracticeOut } from '../types'

type Tab = 'upload' | 'queue' | 'deadlines' | 'dashboard' | 'practices'

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

interface Props {
  onLogout: () => void
}

export function OpsConsole({ onLogout }: Props) {
  const [activeTab, setActiveTab] = useState<Tab>('upload')
  const [cases, setCases] = useState<CaseSummary[]>([])
  const [deadlines, setDeadlines] = useState<DeadlineItem[]>([])
  const [practices, setPractices] = useState<PracticeOut[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [detail, setDetail] = useState<CaseDetail | null>(null)
  const [editedContent, setEditedContent] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function loadQueue() {
    try {
      const data = await getQueueCases()
      setCases(data)
    } catch (e) {
      setError(String(e))
    }
  }

  async function loadDeadlines() {
    try {
      const data = await getDeadlines()
      setDeadlines(data)
    } catch (e) {
      setError(String(e))
    }
  }

  async function loadPractices() {
    try {
      const data = await listPractices()
      setPractices(data)
    } catch (e) {
      setError(String(e))
    }
  }

  async function handlePracticeAction(action: () => Promise<PracticeOut>) {
    try {
      const updated = await action()
      setPractices(prev => prev.map(p => p.id === updated.id ? updated : p))
    } catch (e) {
      setError(String(e))
    }
  }

  useEffect(() => {
    loadQueue()
    loadDeadlines()
    loadPractices()
  }, [])

  async function selectCase(id: number) {
    setSelectedId(id)
    setDetail(null)
    setLoading(true)
    try {
      const d = await getCaseDetail(id)
      setDetail(d)
      const appealDraft = d.drafts.find((dr: DraftInfo) => dr.draft_type === 'appeal') ?? null
      setEditedContent(appealDraft?.content ?? '')
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  async function handleReviewed() {
    await loadQueue()
    if (selectedId !== null) {
      const d = await getCaseDetail(selectedId)
      setDetail(d)
      const appealDraft = d.drafts.find((dr: DraftInfo) => dr.draft_type === 'appeal') ?? null
      setEditedContent(appealDraft?.content ?? '')
    }
  }

  const appealDraft: DraftInfo | null = detail?.drafts.find((d: DraftInfo) => d.draft_type === 'appeal') ?? null
  const originalContent = appealDraft?.content ?? ''

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', fontFamily: 'system-ui, sans-serif', fontSize: 14, color: '#212529' }}>
      <div style={{ borderBottom: '1px solid #dee2e6', padding: '0 16px', display: 'flex', alignItems: 'center', background: '#fff', flexShrink: 0 }}>
        <span style={{ fontWeight: 700, fontSize: 15, marginRight: 24, color: '#212529' }}>DenialDesk</span>
        <span style={{ fontSize: 11, color: '#6c757d', marginRight: 20, padding: '2px 8px', background: '#f8f9fa', border: '1px solid #dee2e6', borderRadius: 3 }}>Ops</span>
        <button style={tabBtn(activeTab === 'upload')} onClick={() => setActiveTab('upload')}>Upload</button>
        <button style={tabBtn(activeTab === 'queue')} onClick={() => setActiveTab('queue')}>Review Queue</button>
        <button style={tabBtn(activeTab === 'deadlines')} onClick={() => setActiveTab('deadlines')}>
          Deadlines
          {(() => {
            const urgent = deadlines.filter(d => d.urgency === 'overdue' || d.urgency === 'critical').length
            return urgent > 0 ? (
              <span style={{ marginLeft: 6, background: '#dc3545', color: '#fff', borderRadius: 10, padding: '1px 6px', fontSize: 11, fontWeight: 700 }}>
                {urgent}
              </span>
            ) : null
          })()}
        </button>
        <button style={tabBtn(activeTab === 'dashboard')} onClick={() => setActiveTab('dashboard')}>Dashboard</button>
        <button style={tabBtn(activeTab === 'practices')} onClick={() => setActiveTab('practices')}>Practices</button>
        <div style={{ marginLeft: 'auto' }}>
          <button
            onClick={onLogout}
            style={{ padding: '4px 12px', fontSize: 12, background: 'none', border: '1px solid #dee2e6', borderRadius: 4, cursor: 'pointer', color: '#6c757d' }}
          >
            Sign out
          </button>
        </div>
      </div>

      {activeTab === 'upload' ? (
        <div style={{ flex: 1, overflowY: 'auto', background: '#f8f9fa' }}>
          <UploadForm />
        </div>
      ) : activeTab === 'dashboard' ? (
        <div style={{ flex: 1, overflowY: 'auto', background: '#f8f9fa' }}>
          <Dashboard />
        </div>
      ) : activeTab === 'deadlines' ? (
        <div style={{ flex: 1, overflowY: 'auto', background: '#f8f9fa' }}>
          <DeadlineView deadlines={deadlines} />
        </div>
      ) : activeTab === 'practices' ? (
        <div style={{ flex: 1, overflowY: 'auto', background: '#f8f9fa', padding: 24 }}>
          <h2 style={{ margin: '0 0 16px', fontSize: 18 }}>Practices</h2>
          {practices.length === 0 && <div style={{ color: '#6c757d' }}>No practices yet.</div>}
          {practices.length > 0 && (
            <div style={{ background: '#fff', border: '1px solid #dee2e6', borderRadius: 8, overflow: 'hidden' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead>
                  <tr style={{ background: '#f8f9fa', borderBottom: '1px solid #dee2e6' }}>
                    <th style={{ textAlign: 'left', padding: '10px 14px', color: '#6c757d', fontWeight: 600, fontSize: 12 }}>Name</th>
                    <th style={{ textAlign: 'left', padding: '10px 14px', color: '#6c757d', fontWeight: 600, fontSize: 12 }}>Specialty</th>
                    <th style={{ textAlign: 'left', padding: '10px 14px', color: '#6c757d', fontWeight: 600, fontSize: 12 }}>Status</th>
                    <th style={{ textAlign: 'left', padding: '10px 14px', color: '#6c757d', fontWeight: 600, fontSize: 12 }}>BAA</th>
                    <th style={{ textAlign: 'left', padding: '10px 14px', color: '#6c757d', fontWeight: 600, fontSize: 12 }}>SA</th>
                    <th style={{ textAlign: 'left', padding: '10px 14px', color: '#6c757d', fontWeight: 600, fontSize: 12 }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {practices.map((p, i) => (
                    <tr key={p.id} style={{ borderBottom: '1px solid #dee2e6', background: i % 2 === 0 ? '#fff' : '#fafafa' }}>
                      <td style={{ padding: '10px 14px', fontWeight: 500 }}>{p.name}</td>
                      <td style={{ padding: '10px 14px', color: '#6c757d' }}>{p.specialty}</td>
                      <td style={{ padding: '10px 14px' }}>
                        <span style={{
                          background: p.onboarding_status === 'active' ? '#d1e7dd' : p.onboarding_status === 'suspended' ? '#f8d7da' : '#fff3cd',
                          color: p.onboarding_status === 'active' ? '#0a3622' : p.onboarding_status === 'suspended' ? '#58151c' : '#856404',
                          borderRadius: 4, fontSize: 11, padding: '2px 8px', fontWeight: 600,
                        }}>
                          {p.onboarding_status.replace(/_/g, ' ')}
                        </span>
                      </td>
                      <td style={{ padding: '10px 14px' }}>{p.baa_signed ? '✅' : '—'}</td>
                      <td style={{ padding: '10px 14px' }}>{p.service_agreement_signed ? '✅' : '—'}</td>
                      <td style={{ padding: '10px 14px', display: 'flex', gap: 6 }}>
                        {!p.baa_signed && (
                          <button onClick={() => handlePracticeAction(() => signBaa(p.id))} style={{ fontSize: 11, padding: '3px 8px', cursor: 'pointer', border: '1px solid #ced4da', borderRadius: 3, background: '#fff' }}>Sign BAA</button>
                        )}
                        {!p.service_agreement_signed && (
                          <button onClick={() => handlePracticeAction(() => signServiceAgreement(p.id))} style={{ fontSize: 11, padding: '3px 8px', cursor: 'pointer', border: '1px solid #ced4da', borderRadius: 3, background: '#fff' }}>Sign SA</button>
                        )}
                        {p.onboarding_status !== 'active' && p.onboarding_status !== 'suspended' && (
                          <button onClick={() => handlePracticeAction(() => activatePractice(p.id))} style={{ fontSize: 11, padding: '3px 8px', cursor: 'pointer', border: '1px solid #198754', borderRadius: 3, background: '#d1e7dd', color: '#0a3622' }}>Activate</button>
                        )}
                        {p.onboarding_status !== 'suspended' && (
                          <button onClick={() => handlePracticeAction(() => suspendPractice(p.id))} style={{ fontSize: 11, padding: '3px 8px', cursor: 'pointer', border: '1px solid #dc3545', borderRadius: 3, background: '#f8d7da', color: '#58151c' }}>Suspend</button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : (
        <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
          <QueueSidebar cases={cases} selectedId={selectedId} onSelect={selectCase} />

          <main style={{ flex: 1, overflowY: 'auto', padding: 24 }}>
            {error && (
              <div style={{ background: '#f8d7da', color: '#58151c', padding: '10px 14px', borderRadius: 4, marginBottom: 16 }}>
                {error}
              </div>
            )}

            {!selectedId && (
              <div style={{ color: '#6c757d', marginTop: 60, textAlign: 'center' }}>
                <div style={{ fontSize: 32, marginBottom: 8 }}>&#8592;</div>
                Select a case from the queue to review
              </div>
            )}

            {loading && <div style={{ color: '#6c757d' }}>Loading...</div>}

            {detail && !loading && (
              <>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                  <h2 style={{ margin: 0, fontSize: 18 }}>
                    Case #{detail.id} — {detail.payer}
                  </h2>
                </div>

                <CaseDetailPanel detail={detail} />

                <DraftEditor
                  draft={appealDraft}
                  editedContent={editedContent}
                  onContentChange={setEditedContent}
                />

                {detail.state === 'awaiting_human_review' && (
                  <ReviewPanel
                    caseId={detail.id}
                    draft={appealDraft}
                    editedContent={editedContent}
                    originalContent={originalContent}
                    caseState={detail.state}
                    onReviewed={handleReviewed}
                  />
                )}

                {(detail.state === 'submitted' || detail.state === 'pending_payer') && (
                  <OutcomeForm caseId={detail.id} onOutcomeRecorded={handleReviewed} />
                )}

                {detail.state !== 'awaiting_human_review' &&
                  detail.state !== 'submitted' &&
                  detail.state !== 'pending_payer' && (
                    <div style={{ color: '#6c757d', fontSize: 13, padding: '10px 0' }}>
                      State: <strong>{detail.state}</strong> — no action required
                    </div>
                  )}
              </>
            )}
          </main>
        </div>
      )}
    </div>
  )
}
