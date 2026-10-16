import { useEffect, useRef, useState } from 'react';
import { authHeaders } from '../auth';

interface Practice {
  id: number;
  name: string;
  specialty: string;
}

interface UploadResult {
  batch_id: number;
  practice_id: number;
  case_count: number;
  errors: string[];
}

interface ProcessResult {
  batch_id: number;
  processed: number;
  declined: number;
  awaiting_review: number;
  errors: { case_id: number; error: string }[];
}

export function UploadForm() {
  const [practices, setPractices] = useState<Practice[]>([]);
  const [practiceId, setPracticeId] = useState<number>(1);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [uploadResult, setUploadResult] = useState<UploadResult | null>(null);
  const [processResult, setProcessResult] = useState<ProcessResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetch('/api/practices')
      .then(r => r.json())
      .then((data: Practice[]) => {
        setPractices(data);
        if (data.length > 0) setPracticeId(data[0].id);
      })
      .catch(() => {});
  }, []);

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setError(null);
    setUploadResult(null);
    setProcessResult(null);
    setUploading(true);

    const form = new FormData();
    form.append('file', file);
    form.append('practice_id', String(practiceId));

    try {
      const resp = await fetch('/api/upload', { method: 'POST', body: form, headers: authHeaders() });
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error(body.detail || `Upload failed (${resp.status})`);
      }
      const result: UploadResult = await resp.json();
      setUploadResult(result);
    } catch (err) {
      setError(String(err));
    } finally {
      setUploading(false);
    }
  }

  async function handleProcess() {
    if (!uploadResult) return;
    setError(null);
    setProcessing(true);
    try {
      const resp = await fetch(`/api/batches/${uploadResult.batch_id}/process`, { method: 'POST', headers: authHeaders() });
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error(body.detail || `Processing failed (${resp.status})`);
      }
      const result: ProcessResult = await resp.json();
      setProcessResult(result);
    } catch (err) {
      setError(String(err));
    } finally {
      setProcessing(false);
    }
  }

  function reset() {
    setFile(null);
    setUploadResult(null);
    setProcessResult(null);
    setError(null);
    if (fileRef.current) fileRef.current.value = '';
  }

  const card: React.CSSProperties = {
    background: '#fff',
    border: '1px solid #dee2e6',
    borderRadius: 6,
    padding: 24,
    maxWidth: 520,
    margin: '32px auto',
  };

  const badge = (color: string): React.CSSProperties => ({
    display: 'inline-block',
    padding: '2px 8px',
    borderRadius: 12,
    background: color,
    fontSize: 12,
    fontWeight: 600,
    marginRight: 6,
  });

  return (
    <div style={{ padding: 24 }}>
      <div style={card}>
        <h2 style={{ margin: '0 0 20px', fontSize: 18 }}>Upload Denial Batch</h2>

        {error && (
          <div style={{ background: '#f8d7da', color: '#58151c', padding: '10px 14px', borderRadius: 4, marginBottom: 16, fontSize: 13 }}>
            {error}
          </div>
        )}

        {!uploadResult && (
          <form onSubmit={handleUpload}>
            <div style={{ marginBottom: 16 }}>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 4 }}>
                Practice
              </label>
              {practices.length === 0 ? (
                <div style={{ color: '#6c757d', fontSize: 13 }}>
                  No practices found. Create one in the database first.
                </div>
              ) : (
                <select
                  value={practiceId}
                  onChange={e => setPracticeId(Number(e.target.value))}
                  style={{ width: '100%', padding: '6px 10px', border: '1px solid #ced4da', borderRadius: 4, fontSize: 13 }}
                >
                  {practices.map(p => (
                    <option key={p.id} value={p.id}>{p.name} ({p.specialty})</option>
                  ))}
                </select>
              )}
            </div>

            <div style={{ marginBottom: 20 }}>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 4 }}>
                File (CSV or 835 EDI)
              </label>
              <input
                ref={fileRef}
                type="file"
                accept=".csv,.txt,.835,.edi"
                onChange={e => setFile(e.target.files?.[0] ?? null)}
                style={{ fontSize: 13 }}
              />
            </div>

            <button
              type="submit"
              disabled={!file || uploading || practices.length === 0}
              style={{
                padding: '8px 20px',
                background: file && !uploading ? '#0d6efd' : '#adb5bd',
                color: '#fff',
                border: 'none',
                borderRadius: 4,
                cursor: file && !uploading ? 'pointer' : 'default',
                fontSize: 14,
                fontWeight: 600,
              }}
            >
              {uploading ? 'Uploading...' : 'Upload'}
            </button>
          </form>
        )}

        {uploadResult && !processResult && (
          <div>
            <div style={{ background: '#d1e7dd', color: '#0a3622', padding: '12px 16px', borderRadius: 4, marginBottom: 16, fontSize: 13 }}>
              Uploaded <strong>{uploadResult.case_count} claims</strong> (Batch #{uploadResult.batch_id})
              {uploadResult.errors.length > 0 && (
                <div style={{ marginTop: 6, color: '#842029' }}>
                  {uploadResult.errors.length} parse error{uploadResult.errors.length > 1 ? 's' : ''}
                </div>
              )}
            </div>

            <p style={{ fontSize: 13, color: '#495057', marginBottom: 16 }}>
              Run the AI pipeline to diagnose each claim and draft appeal letters. Claims scoring below {(0.20 * 100).toFixed(0)}% winnability will be automatically declined.
            </p>

            <div style={{ display: 'flex', gap: 10 }}>
              <button
                onClick={handleProcess}
                disabled={processing}
                style={{
                  padding: '8px 20px',
                  background: processing ? '#adb5bd' : '#198754',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 4,
                  cursor: processing ? 'default' : 'pointer',
                  fontSize: 14,
                  fontWeight: 600,
                }}
              >
                {processing ? 'Processing...' : 'Run Pipeline'}
              </button>
              <button
                onClick={reset}
                style={{ padding: '8px 14px', background: 'none', border: '1px solid #ced4da', borderRadius: 4, fontSize: 13, cursor: 'pointer' }}
              >
                Upload another
              </button>
            </div>
          </div>
        )}

        {processResult && (
          <div>
            <div style={{ background: '#d1e7dd', color: '#0a3622', padding: '12px 16px', borderRadius: 4, marginBottom: 16, fontSize: 13 }}>
              Pipeline complete for Batch #{processResult.batch_id}
            </div>

            <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
              <div style={{ textAlign: 'center', padding: '12px 20px', background: '#f8f9fa', borderRadius: 6, minWidth: 80 }}>
                <div style={{ fontSize: 28, fontWeight: 700 }}>{processResult.processed}</div>
                <div style={{ fontSize: 12, color: '#6c757d' }}>processed</div>
              </div>
              <div style={{ textAlign: 'center', padding: '12px 20px', background: '#fff3cd', borderRadius: 6, minWidth: 80 }}>
                <div style={{ fontSize: 28, fontWeight: 700, color: '#856404' }}>{processResult.declined}</div>
                <div style={{ fontSize: 12, color: '#856404' }}>declined</div>
              </div>
              <div style={{ textAlign: 'center', padding: '12px 20px', background: '#cfe2ff', borderRadius: 6, minWidth: 80 }}>
                <div style={{ fontSize: 28, fontWeight: 700, color: '#084298' }}>{processResult.awaiting_review}</div>
                <div style={{ fontSize: 12, color: '#084298' }}>ready to review</div>
              </div>
            </div>

            {processResult.errors.length > 0 && (
              <div style={{ background: '#f8d7da', color: '#58151c', padding: '10px 14px', borderRadius: 4, marginBottom: 16, fontSize: 12 }}>
                {processResult.errors.length} case error{processResult.errors.length > 1 ? 's' : ''} — check logs for details
              </div>
            )}

            <button
              onClick={reset}
              style={{ padding: '8px 14px', background: '#0d6efd', color: '#fff', border: 'none', borderRadius: 4, fontSize: 13, cursor: 'pointer', fontWeight: 600 }}
            >
              Upload another batch
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
