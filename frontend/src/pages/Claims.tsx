import { useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { ArrowDown, ArrowUp, FolderOpen, Upload } from 'lucide-react'
import { listCases } from '../api'
import { useAuth } from '../auth'
import { FILTER_GROUPS, statusMeta } from '../lib/caseStatus'
import { date, money, pct, rootCause } from '../lib/format'
import { Async, Empty, PageHead, StatusBadge, useAsync } from '../components/ui'
import type { ClinicCaseSummary } from '../types'

type SortKey = 'updated_at' | 'billed_amt' | 'payer' | 'denial_date' | 'winnability_score'

export function Claims() {
  const { isOps } = useAuth()
  const nav = useNavigate()
  const [params, setParams] = useSearchParams()
  const q = params.get('q') ?? ''
  const [group, setGroup] = useState('all')
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: 'updated_at', dir: -1 })
  const cases = useAsync(() => listCases(), [])

  const rows = useMemo(() => {
    const all = cases.data ?? []
    const needle = q.trim().toLowerCase()
    const g = FILTER_GROUPS.find((f) => f.key === group)!
    return all
      .filter((c) => g.match(c.state))
      .filter((c) =>
        !needle ||
        [c.patient_ref, c.payer, c.cpt, c.carc, c.practice_name, rootCause(c.root_cause), statusMeta(c.state).label, String(c.id)]
          .some((v) => (v ?? '').toLowerCase().includes(needle)),
      )
      .sort((a, b) => {
        const av = a[sort.key] ?? ''
        const bv = b[sort.key] ?? ''
        return (av < bv ? -1 : av > bv ? 1 : 0) * sort.dir
      })
  }, [cases.data, q, group, sort])

  const counts = useMemo(
    () => Object.fromEntries(FILTER_GROUPS.map((f) => [f.key, (cases.data ?? []).filter((c) => f.match(c.state)).length])),
    [cases.data],
  )

  const th = (key: SortKey, label: string, cls = '') => (
    <th className={`sortable ${cls}`} onClick={() => setSort((s) => ({ key, dir: s.key === key ? (-s.dir as 1 | -1) : -1 }))}>
      {label} {sort.key === key && (sort.dir === 1 ? <ArrowUp size={12} /> : <ArrowDown size={12} />)}
    </th>
  )

  return (
    <>
      <PageHead
        title={isOps ? 'All claims' : 'Claims'}
        sub={cases.data ? `${cases.data.length} denied claims` : undefined}
        actions={!isOps && <button className="btn primary" onClick={() => nav('/upload')}><Upload size={16} /> Upload denials</button>}
      />
      <div className="card">
        <div className="toolbar">
          <div className="chips">
            {FILTER_GROUPS.map((f) => (
              <button key={f.key} className={`chip${group === f.key ? ' on' : ''}`} onClick={() => setGroup(f.key)}>
                {f.label}<span className="n">{counts[f.key]}</span>
              </button>
            ))}
          </div>
          <div className="spacer" />
          <input type="search" placeholder="Filter by patient, payer, CPT, code…" value={q} aria-label="Filter claims"
            onChange={(e) => setParams(e.target.value ? { q: e.target.value } : {}, { replace: true })} />
        </div>
        <Async state={cases}>
          {() => rows.length === 0 ? (
            <Empty title={q || group !== 'all' ? 'No claims match' : 'No claims yet'} icon={<FolderOpen size={24} />}
              action={!isOps && !q && group === 'all' && <button className="btn primary" onClick={() => nav('/upload')}>Upload your first batch</button>}>
              {q || group !== 'all' ? 'Try a different filter or search.' : 'Upload denied claims and we’ll start working them.'}
            </Empty>
          ) : (
            <div className="table-wrap">
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Patient / Claim</th>
                    {isOps && <th>Practice</th>}
                    {th('payer', 'Payer')}
                    <th>CPT</th>
                    <th>Denial reason</th>
                    {th('billed_amt', 'Billed', 'num')}
                    {th('winnability_score', 'Win odds')}
                    <th>Status</th>
                    {th('updated_at', 'Updated')}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((c) => <Row key={c.id} c={c} ops={isOps} onOpen={() => nav(`/claims/${c.id}`)} />)}
                </tbody>
              </table>
            </div>
          )}
        </Async>
      </div>
    </>
  )
}

function Row({ c, ops, onOpen }: { c: ClinicCaseSummary; ops: boolean; onOpen: () => void }) {
  const score = c.winnability_score
  const color = score == null ? 'var(--border-strong)' : score >= 0.6 ? 'var(--green-700)' : score >= 0.35 ? '#d9930d' : 'var(--red-700)'
  return (
    <tr className="clickable" onClick={onOpen} tabIndex={0} onKeyDown={(e) => e.key === 'Enter' && onOpen()}>
      <td><div className="primary">{c.patient_ref ?? `Claim #${c.id}`}</div><div className="secondary">DOS {date(c.dos)}</div></td>
      {ops && <td>{c.practice_name ?? '—'}</td>}
      <td>{c.payer}</td>
      <td className="mono">{c.cpt}</td>
      <td><div>{rootCause(c.root_cause)}</div><div className="secondary">CARC {c.carc}</div></td>
      <td className="num">{money(c.billed_amt)}</td>
      <td style={{ minWidth: 110 }}>
        {score == null ? <span className="faint">—</span> : (
          <div className="row" style={{ gap: 8 }}>
            <div className="meter" style={{ width: 54 }}><i style={{ width: pct(score), background: color }} /></div>
            <span style={{ fontWeight: 600, fontSize: 12.5 }}>{pct(score)}</span>
          </div>
        )}
      </td>
      <td><StatusBadge state={c.state} /></td>
      <td className="muted nowrap">{date(c.updated_at)}</td>
    </tr>
  )
}
