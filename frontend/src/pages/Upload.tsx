import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { CheckCircle2, FileSpreadsheet, FileText, Lock, Sparkles, UploadCloud, XCircle } from 'lucide-react'
import { getBatch, getOnboardingStatus, listBatches, startProcessing, uploadFile } from '../api'
import { date } from '../lib/format'
import { Alert, Async, Empty, PageHead, Spinner, useAsync } from '../components/ui'
import type { BatchSummary } from '../types'

type Phase = 'queued' | 'uploading' | 'analyzing' | 'done' | 'error'
interface Item {
  key: string
  file: File
  phase: Phase
  error?: string
  warnings?: string[]
  batchId?: number
  batch?: BatchSummary
}

const ACCEPT = '.csv,.835,.edi,.x12,.txt,.pdf'

const TEMPLATE = [
  'claim_number,patient_ref,dos,cpt,icd10,billed_amt,allowed_amt,payer,carc,rarc,denial_date',
  'CLM-1001,PT-0001,2026-07-08,99214,"I10,E11.9",185.00,0,Aetna,16,M76,2026-08-12',
].join('\n')

function downloadTemplate() {
  const url = URL.createObjectURL(new Blob([TEMPLATE], { type: 'text/csv' }))
  const a = document.createElement('a')
  a.href = url
  a.download = 'denialdesk_claims_template.csv'
  a.click()
  URL.revokeObjectURL(url)
}

export function UploadPage() {
  const nav = useNavigate()
  const onboarding = useAsync(getOnboardingStatus, [])
  const batches = useAsync(listBatches, [])
  const [items, setItems] = useState<Item[]>([])
  const [over, setOver] = useState(false)
  const input = useRef<HTMLInputElement>(null)
  const alive = useRef(true)
  useEffect(() => () => { alive.current = false }, [])

  const patch = useCallback((key: string, p: Partial<Item>) => {
    if (alive.current) setItems((l) => l.map((i) => (i.key === key ? { ...i, ...p } : i)))
  }, [])

  const run = useCallback(async (it: Item) => {
    patch(it.key, { phase: 'uploading' })
    try {
      const up = await uploadFile(it.file)
      if (up.case_count === 0) {
        patch(it.key, { phase: 'error', error: up.errors[0] ?? 'No claims found in this file.', warnings: up.errors })
        return
      }
      patch(it.key, { phase: 'analyzing', batchId: up.batch_id, warnings: up.errors })
      await startProcessing(up.batch_id)
      // Poll until every claim has left the "analyzing" state.
      for (let i = 0; i < 300 && alive.current; i++) {
        const b = await getBatch(up.batch_id)
        patch(it.key, { batch: b })
        if (b.done) { patch(it.key, { phase: 'done' }); batches.reload(); return }
        await new Promise((r) => setTimeout(r, 2000))
      }
      patch(it.key, { phase: 'error', error: 'Analysis is taking longer than expected. Check Claims for progress.' })
    } catch (e) {
      patch(it.key, { phase: 'error', error: (e as Error).message })
    }
  }, [patch, batches])

  const add = (files: FileList | File[]) => {
    const fresh: Item[] = Array.from(files).map((f) => ({ key: `${f.name}-${f.size}-${Math.random()}`, file: f, phase: 'queued' as Phase }))
    setItems((l) => [...fresh, ...l])
    fresh.forEach((f) => void run(f))
  }

  const locked = onboarding.data && onboarding.data.onboarding_status !== 'active'

  return (
    <>
      <PageHead title="Upload denials" sub="Send us your denied claims. We’ll diagnose each one and write the appeals for the ones worth fighting." />

      {locked && (
        <div className="card card-body stack" style={{ marginBottom: 16 }}>
          <div className="row"><Lock size={18} color="var(--amber-700)" /><h3>Uploads unlock after onboarding</h3></div>
          <p className="muted">Your account is <b>{onboarding.data!.onboarding_status.replace(/_/g, ' ')}</b>. Our team needs to countersign your Business Associate Agreement and service agreement before we can accept patient data.</p>
          <div className="row wrap" style={{ gap: 18 }}>
            {([['BAA signed', onboarding.data!.baa_signed], ['Service agreement signed', onboarding.data!.service_agreement_signed], ['Practice details', onboarding.data!.details_complete]] as const).map(([l, ok]) => (
              <span key={l} className="row" style={{ gap: 6 }}>{ok ? <CheckCircle2 size={16} color="var(--green-700)" /> : <XCircle size={16} color="var(--text-3)" />}{l}</span>
            ))}
          </div>
        </div>
      )}

      <div className="grid cols-2" style={{ gridTemplateColumns: 'minmax(0,1.6fr) minmax(0,1fr)', alignItems: 'start' }}>
        <div className="stack">
          <div
            className={`dropzone${over ? ' over' : ''}`}
            role="button" tabIndex={0} aria-disabled={!!locked}
            style={locked ? { opacity: 0.5, pointerEvents: 'none' } : undefined}
            onClick={() => input.current?.click()}
            onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && input.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setOver(true) }}
            onDragLeave={() => setOver(false)}
            onDrop={(e) => { e.preventDefault(); setOver(false); if (e.dataTransfer.files.length) add(e.dataTransfer.files) }}
          >
            <div className="ico"><UploadCloud size={26} /></div>
            <h3>Drag & drop your claims here</h3>
            <p className="muted" style={{ margin: '4px 0 14px' }}>CSV exports, 835 remittance files, or EOB PDFs — or click to browse</p>
            <span className="btn primary">Choose files</span>
            <input ref={input} type="file" multiple accept={ACCEPT} hidden onChange={(e) => { if (e.target.files) add(e.target.files); e.target.value = '' }} />
          </div>

          {items.map((it) => <FileRow key={it.key} it={it} onView={() => nav('/claims')} />)}
        </div>

        <div className="stack">
          <div className="card">
            <div className="card-head"><h3>What happens next</h3></div>
            <div className="card-body stack">
              {[
                ['Diagnose', 'We read the denial codes and pinpoint the real root cause.'],
                ['Triage', 'Unwinnable claims (e.g. past filing limit) are declined up front — with the reason.'],
                ['Draft', 'AI writes a payer-specific appeal and lists the documents to attach.'],
                ['Review', 'An appeals specialist approves every letter before it’s sent.'],
              ].map(([t, d], i) => (
                <div key={t} className="row" style={{ alignItems: 'flex-start', gap: 12 }}>
                  <span className="avatar" style={{ width: 26, height: 26, fontSize: 12, background: 'var(--blue-100)', color: 'var(--blue-600)' }}>{i + 1}</span>
                  <div><b>{t}</b><div className="muted" style={{ fontSize: 13 }}>{d}</div></div>
                </div>
              ))}
            </div>
          </div>
          <div className="card card-body stack">
            <div className="row"><FileSpreadsheet size={18} color="var(--blue-600)" /><b>Using a spreadsheet?</b></div>
            <p className="muted" style={{ fontSize: 13 }}>Required columns: claim_number, patient_ref, dos, cpt, icd10, billed_amt, payer, carc, denial_date. Dates as YYYY-MM-DD.</p>
            <button className="btn" onClick={downloadTemplate}>Download CSV template</button>
          </div>
        </div>
      </div>

      <h3 style={{ margin: '28px 0 12px' }}>Upload history</h3>
      <div className="card">
        <Async state={batches}>
          {(rows) => rows.length === 0 ? <Empty title="No uploads yet" icon={<FileText size={24} />}>Your uploaded batches will be listed here.</Empty> : (
            <div className="table-wrap"><table className="tbl">
              <thead><tr><th>File</th><th>Uploaded</th><th className="num">Claims</th><th className="num">Not appealable</th><th className="num">In progress</th><th className="num">Paid</th></tr></thead>
              <tbody>
                {rows.map((b) => (
                  <tr key={b.id} className="clickable" onClick={() => nav('/claims')}>
                    <td className="primary">{b.filename ?? `Batch ${b.id}`}</td>
                    <td className="muted">{date(b.uploaded_at)}</td>
                    <td className="num">{b.total}</td><td className="num">{b.declined}</td>
                    <td className="num">{b.in_progress + b.analyzing}</td><td className="num">{b.paid}</td>
                  </tr>
                ))}
              </tbody></table></div>
          )}
        </Async>
      </div>
    </>
  )
}

function FileRow({ it, onView }: { it: Item; onView: () => void }) {
  const b = it.batch
  const analyzed = b ? b.total - b.analyzing : 0
  const steps: [string, Phase[]][] = [['Upload', ['uploading']], ['AI analysis', ['analyzing']], ['Done', ['done']]]
  const order: Phase[] = ['queued', 'uploading', 'analyzing', 'done']
  const idx = order.indexOf(it.phase)
  return (
    <div className="card card-body stack">
      <div className="row">
        <FileText size={20} color="var(--blue-600)" />
        <div style={{ minWidth: 0 }}><div className="primary" style={{ fontWeight: 600 }}>{it.file.name}</div>
          <div className="faint" style={{ fontSize: 12 }}>{(it.file.size / 1024).toFixed(1)} KB</div></div>
        <div className="spacer" />
        {it.phase === 'done' && <button className="btn sm primary" onClick={onView}>View claims</button>}
      </div>

      {it.phase === 'error' ? <Alert kind="error">{it.error}</Alert> : (
        <>
          <div className="steps">
            {steps.map(([label, ph], i) => {
              const state = it.phase === 'done' || idx > order.indexOf(ph[0]) ? 'done' : it.phase === ph[0] ? 'active' : ''
              return (
                <span key={label} style={{ display: 'contents' }}>
                  {i > 0 && <span className="step-line" />}
                  <span className={`step ${state}`}>
                    <span className="dot">{state === 'done' ? '✓' : state === 'active' ? <Spinner /> : i + 1}</span>{label}
                  </span>
                </span>
              )
            })}
          </div>
          {it.phase === 'analyzing' && b && (
            <div>
              <div className="progress"><i style={{ width: `${b.total ? (analyzed / b.total) * 100 : 0}%` }} /></div>
              <div className="faint" style={{ fontSize: 12, marginTop: 5 }}><Sparkles size={12} style={{ verticalAlign: -1 }} /> Analyzed {analyzed} of {b.total} claims…</div>
            </div>
          )}
          {it.phase === 'done' && b && (
            <div className="row wrap" style={{ gap: 20 }}>
              <span><b>{b.total}</b> <span className="muted">claims received</span></span>
              <span style={{ color: 'var(--amber-700)' }}><b>{b.in_progress}</b> appeals drafted</span>
              <span style={{ color: 'var(--red-700)' }}><b>{b.declined}</b> <span className="muted">not appealable</span></span>
            </div>
          )}
        </>
      )}
      {it.warnings && it.warnings.length > 0 && it.phase !== 'error' && (
        <Alert kind="warn"><b>{it.warnings.length} row(s) skipped:</b> {it.warnings.slice(0, 3).join(' · ')}{it.warnings.length > 3 ? ' …' : ''}</Alert>
      )}
    </div>
  )
}
