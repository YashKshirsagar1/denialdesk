import { useState } from 'react';
import { submitReview } from '../api';
import type { DraftInfo } from '../types';

interface Props {
  caseId: number;
  draft: DraftInfo | null;
  editedContent: string;
  originalContent: string;
  caseState: string;
  onReviewed: () => void;
}

export function ReviewPanel({ caseId, draft, editedContent, originalContent, caseState, onReviewed }: Props) {
  const showDownloads = caseState === 'awaiting_human_review' || caseState === 'submitted';
  const [reviewer, setReviewer] = useState('Reviewer');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ text: string; ok: boolean } | null>(null);

  const isEdited = draft !== null && editedContent !== originalContent;

  async function submit(decision: 'approve' | 'reject' | 'edit') {
    setLoading(true);
    setMessage(null);
    try {
      const res = await submitReview(caseId, {
        decision,
        reviewer,
        edits: decision === 'edit' ? editedContent : undefined,
      });
      setMessage({ text: res.message, ok: true });
      onReviewed();
    } catch (err: unknown) {
      setMessage({ text: err instanceof Error ? err.message : String(err), ok: false });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{
      borderTop: '1px solid #dee2e6',
      paddingTop: 14,
      display: 'flex',
      flexDirection: 'column',
      gap: 10,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <label style={{ fontSize: 12, color: '#495057', minWidth: 64 }}>Reviewer</label>
        <input
          value={reviewer}
          onChange={e => setReviewer(e.target.value)}
          style={{ fontSize: 13, padding: '4px 8px', border: '1px solid #ced4da', borderRadius: 4, width: 180 }}
        />
      </div>

      <div style={{ display: 'flex', gap: 8 }}>
        <button
          onClick={() => submit('approve')}
          disabled={loading || !draft}
          style={{ ...btnStyle, background: '#198754', color: '#fff' }}
        >
          Approve
        </button>
        <button
          onClick={() => submit('edit')}
          disabled={loading || !isEdited}
          style={{ ...btnStyle, background: isEdited ? '#0d6efd' : '#adb5bd', color: '#fff', cursor: isEdited ? 'pointer' : 'not-allowed' }}
        >
          Edit &amp; Approve
        </button>
        <button
          onClick={() => submit('reject')}
          disabled={loading || !draft}
          style={{ ...btnStyle, background: '#dc3545', color: '#fff' }}
        >
          Reject
        </button>
      </div>

      {showDownloads && (
        <div className="packet-downloads" style={{ display: 'flex', gap: 10, marginTop: 4 }}>
          <a
            href={`/api/cases/${caseId}/packet/appeal.pdf`}
            target="_blank"
            rel="noreferrer"
            style={{ ...linkBtnStyle, background: '#e9ecef', color: '#212529' }}
          >
            Download Appeal Letter (PDF)
          </a>
          <a
            href={`/api/cases/${caseId}/packet/call-packet.pdf`}
            target="_blank"
            rel="noreferrer"
            style={{ ...linkBtnStyle, background: '#e9ecef', color: '#212529' }}
          >
            Download Call Packet (PDF)
          </a>
        </div>
      )}

      {message && (
        <div style={{
          fontSize: 13,
          padding: '8px 12px',
          borderRadius: 4,
          background: message.ok ? '#d1e7dd' : '#f8d7da',
          color: message.ok ? '#0a3622' : '#58151c',
        }}>
          {message.text}
        </div>
      )}
    </div>
  );
}

const btnStyle: React.CSSProperties = {
  padding: '7px 16px',
  border: 'none',
  borderRadius: 4,
  fontSize: 13,
  fontWeight: 600,
  cursor: 'pointer',
};

const linkBtnStyle: React.CSSProperties = {
  padding: '6px 14px',
  borderRadius: 4,
  fontSize: 12,
  fontWeight: 500,
  textDecoration: 'none',
  border: '1px solid #ced4da',
};
