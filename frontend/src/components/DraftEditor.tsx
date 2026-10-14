import type { DraftInfo } from '../types';

interface Props {
  draft: DraftInfo | null;
  editedContent: string;
  onContentChange: (s: string) => void;
}

export function DraftEditor({ draft, editedContent, onContentChange }: Props) {
  if (!draft) {
    return (
      <div style={{ padding: 24, color: '#6c757d', fontSize: 13 }}>
        No appeal draft available.
      </div>
    );
  }

  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
        <h3 style={{ margin: 0, fontSize: 15 }}>Appeal Letter</h3>
        <span style={{
          background: '#e9ecef',
          color: '#495057',
          fontSize: 11,
          padding: '2px 8px',
          borderRadius: 10,
          fontWeight: 600,
        }}>
          v{draft.version}
        </span>
        {editedContent !== draft.content && (
          <span style={{ fontSize: 11, color: '#fd7e14', fontWeight: 600 }}>● Edited</span>
        )}
      </div>

      {draft.attachments.length > 0 && (
        <div style={{ marginBottom: 8 }}>
          <span style={{ fontSize: 11, color: '#6c757d', textTransform: 'uppercase' }}>Attachments: </span>
          {draft.attachments.map(a => (
            <span key={a} style={{
              display: 'inline-block',
              background: '#e8f4fd',
              color: '#0d6efd',
              fontSize: 11,
              padding: '1px 7px',
              borderRadius: 10,
              marginRight: 4,
            }}>
              {a.replace(/_/g, ' ')}
            </span>
          ))}
        </div>
      )}

      <textarea
        value={editedContent}
        onChange={e => onContentChange(e.target.value)}
        style={{
          width: '100%',
          height: 340,
          fontFamily: 'monospace',
          fontSize: 12,
          padding: 10,
          border: '1px solid #dee2e6',
          borderRadius: 4,
          resize: 'vertical',
          boxSizing: 'border-box',
          lineHeight: 1.5,
        }}
      />
    </div>
  );
}
