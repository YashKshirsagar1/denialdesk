import { useEffect, useState } from 'react';
import { getCaseDetail, getQueueCases } from './api';
import { CaseDetailPanel } from './components/CaseDetail';
import { DraftEditor } from './components/DraftEditor';
import { QueueSidebar } from './components/QueueSidebar';
import { ReviewPanel } from './components/ReviewPanel';
import type { CaseDetail, CaseSummary, DraftInfo } from './types';

export default function App() {
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [editedContent, setEditedContent] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadQueue() {
    try {
      const data = await getQueueCases();
      setCases(data);
    } catch (e) {
      setError(String(e));
    }
  }

  useEffect(() => { loadQueue(); }, []);

  async function selectCase(id: number) {
    setSelectedId(id);
    setDetail(null);
    setLoading(true);
    try {
      const d = await getCaseDetail(id);
      setDetail(d);
      const appealDraft = d.drafts.find(dr => dr.draft_type === 'appeal') ?? null;
      setEditedContent(appealDraft?.content ?? '');
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  async function handleReviewed() {
    await loadQueue();
    if (selectedId !== null) {
      const d = await getCaseDetail(selectedId);
      setDetail(d);
      const appealDraft = d.drafts.find(dr => dr.draft_type === 'appeal') ?? null;
      setEditedContent(appealDraft?.content ?? '');
    }
  }

  const appealDraft: DraftInfo | null = detail?.drafts.find(d => d.draft_type === 'appeal') ?? null;
  const originalContent = appealDraft?.content ?? '';

  return (
    <div style={{ display: 'flex', height: '100vh', fontFamily: 'system-ui, sans-serif', fontSize: 14, color: '#212529' }}>
      <QueueSidebar cases={cases} selectedId={selectedId} onSelect={selectCase} />

      <main style={{ flex: 1, overflowY: 'auto', padding: 24 }}>
        {error && (
          <div style={{ background: '#f8d7da', color: '#58151c', padding: '10px 14px', borderRadius: 4, marginBottom: 16 }}>
            {error}
          </div>
        )}

        {!selectedId && (
          <div style={{ color: '#6c757d', marginTop: 60, textAlign: 'center' }}>
            <div style={{ fontSize: 32, marginBottom: 8 }}>⬅</div>
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
                onReviewed={handleReviewed}
              />
            )}

            {detail.state !== 'awaiting_human_review' && (
              <div style={{ color: '#6c757d', fontSize: 13, padding: '10px 0' }}>
                State: <strong>{detail.state}</strong> — no action required
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
