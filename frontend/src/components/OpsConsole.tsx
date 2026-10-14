import { useEffect, useState } from 'react'
import { getCaseDetail, getQueueCases } from '../api'
import { clearToken } from '../auth'
import { CaseDetailPanel } from './CaseDetail'
import { Dashboard } from './Dashboard'
import { DraftEditor } from './DraftEditor'
import { OutcomeForm } from './OutcomeForm'
import { QueueSidebar } from './QueueSidebar'
import { ReviewPanel } from './ReviewPanel'
import { UploadForm } from './UploadForm'
import type { CaseDetail, CaseSummary, DraftInfo } from '../types'

type Tab = 'upload' | 'queue' | 'dashboard'

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

  useEffect(() => {
    loadQueue()
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

      {activeTab === 'upload' ? (
        <div style={{ flex: 1, overflowY: 'auto', background: '#f8f9fa' }}>
          <UploadForm />
        </div>
      ) : activeTab === 'dashboard' ? (
        <div style={{ flex: 1, overflowY: 'auto', background: '#f8f9fa' }}>
          <Dashboard />
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
