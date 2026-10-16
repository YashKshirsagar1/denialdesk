import { getScoreAccuracy, getWinRates } from '../api'
import { pct } from '../lib/format'
import { Alert, Async, Empty, PageHead, useAsync } from '../components/ui'

export function Analytics() {
  const win = useAsync(() => getWinRates(1), [])
  const acc = useAsync(getScoreAccuracy, [])
  return (
    <>
      <PageHead title="Analytics" sub="The pattern data: which payer × denial code × specialty combinations actually get overturned." />
      <div className="stack">
        <div className="card">
          <div className="card-head"><h3>Win rate by payer, denial code and specialty</h3></div>
          <Async state={win}>
            {(t) => t.rows.length === 0 ? <Empty title="No outcomes yet">Win rates appear once appeals have results.</Empty> : (
              <div className="table-wrap"><table className="tbl">
                <thead><tr><th>Payer</th><th>CARC</th><th>Specialty</th><th className="num">Attempts</th><th className="num">Wins</th><th style={{ width: 200 }}>Win rate</th></tr></thead>
                <tbody>
                  {t.rows.map((r, i) => (
                    <tr key={i}><td className="primary">{r.payer}</td><td className="mono">{r.reason_code}</td><td>{r.specialty}</td>
                      <td className="num">{r.attempts}</td><td className="num">{r.wins}</td>
                      <td><div className="row"><div className="meter" style={{ flex: 1 }}><i style={{ width: pct(r.win_rate), background: 'var(--blue-500)' }} /></div><b style={{ width: 40 }}>{pct(r.win_rate)}</b></div></td></tr>
                  ))}
                </tbody></table></div>
            )}
          </Async>
        </div>
        <div className="card">
          <div className="card-head"><h3>Score accuracy — predicted vs actual</h3></div>
          <Async state={acc}>
            {(a) => (
              <div className="card-body stack">
                {a.rows.length === 0 ? <span className="muted">Not enough outcomes yet.</span> : (
                  <table className="tbl"><thead><tr><th>Predicted score</th><th className="num">Cases</th><th className="num">Avg predicted</th><th className="num">Actual win rate</th></tr></thead>
                    <tbody>{a.rows.map((r) => (
                      <tr key={r.score_bucket}><td className="primary">{r.score_bucket}</td><td className="num">{r.count}</td>
                        <td className="num">{pct(r.avg_predicted_score)}</td><td className="num">{pct(r.actual_win_rate)}</td></tr>))}</tbody></table>
                )}
                {a.correlation_note && <Alert kind="info">{a.correlation_note}</Alert>}
              </div>
            )}
          </Async>
        </div>
      </div>
    </>
  )
}
