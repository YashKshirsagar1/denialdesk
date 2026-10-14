import type { CaseDetail } from '../types';

function Field({ label, value }: { label: string; value: string | number | null | undefined }) {
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ fontSize: 11, color: '#6c757d', textTransform: 'uppercase', letterSpacing: '0.04em' }}>{label}</div>
      <div style={{ fontSize: 13, fontWeight: 500 }}>{value ?? '—'}</div>
    </div>
  );
}

export function CaseDetailPanel({ detail }: { detail: CaseDetail }) {
  const d = detail;
  const score = d.winnability_score;
  const scoreColor = score == null ? '#6c757d' : score > 0.6 ? '#198754' : score >= 0.3 ? '#e67e00' : '#dc3545';

  return (
    <div>
      <h3 style={{ margin: '0 0 12px', fontSize: 15 }}>Claim Facts</h3>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 24px', marginBottom: 20 }}>
        <Field label="Payer" value={d.payer} />
        <Field label="Patient Ref" value={d.patient_ref ?? '—'} />
        <Field label="Date of Service" value={d.denial_date} />
        <Field label="CPT / HCPCS" value={d.cpt} />
        <Field label="ICD-10" value={d.icd10.join(', ')} />
        <Field label="Billed Amount" value={`$${d.billed_amt.toLocaleString()}`} />
        <Field label="Allowed Amount" value={`$${d.allowed_amt.toLocaleString()}`} />
        <Field label="CARC" value={d.carc} />
        <Field label="RARC" value={d.rarc || '—'} />
        <Field label="Denial Date" value={d.denial_date} />
        <Field label="Filing Deadline" value={d.filing_deadline ?? '—'} />
        <Field label="State" value={d.state} />
      </div>

      {d.diagnosis && (
        <div style={{
          background: '#f8f9fa',
          border: '1px solid #dee2e6',
          borderRadius: 6,
          padding: '12px 16px',
          marginBottom: 16,
        }}>
          <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 8 }}>Diagnosis</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 24px', marginBottom: 8 }}>
            <Field label="Root Cause" value={d.diagnosis.root_cause.replace(/_/g, ' ')} />
            <Field
              label="Winnability Score"
              value={`${Math.round(d.diagnosis.winnability_score * 100)}%`}
            />
            <Field label="Expected Value" value={`$${d.diagnosis.expected_value.toFixed(2)}`} />
            <Field label="Model" value={d.diagnosis.model_version} />
          </div>
          <div style={{ fontSize: 12, color: '#495057', fontStyle: 'italic' }}>{d.diagnosis.rationale}</div>
        </div>
      )}
    </div>
  );
}
