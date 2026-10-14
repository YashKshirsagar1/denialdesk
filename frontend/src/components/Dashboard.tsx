import { useEffect, useState } from 'react';
import { getKpiOverview, getPipeline, getScoreAccuracy, getWinRates } from '../api';
import type { OverviewKPIs, PipelineView, ScoreAccuracy, WinRateTable } from '../types';

function fmt$$(n: number) {
  return '$' + n.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

function fmtPct(n: number) {
  return (n * 100).toFixed(1) + '%';
}

function winRateColor(rate: number): string {
  if (rate >= 0.6) return '#198754';
  if (rate >= 0.3) return '#fd7e14';
  return '#dc3545';
}

function scoreColor(score: number): string {
  if (score >= 0.6) return '#198754';
  if (score >= 0.3) return '#fd7e14';
  return '#dc3545';
}

const card: React.CSSProperties = {
  background: '#fff',
  border: '1px solid #dee2e6',
  borderRadius: 6,
  padding: '16px 20px',
  flex: 1,
  minWidth: 160,
};

const sectionTitle: React.CSSProperties = {
  fontSize: 13,
  fontWeight: 600,
  color: '#6c757d',
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
  marginBottom: 12,
};

const pill = (color: string): React.CSSProperties => ({
  display: 'inline-block',
  padding: '2px 8px',
  borderRadius: 12,
  background: color,
  color: '#fff',
  fontSize: 12,
  fontWeight: 600,
});

export function Dashboard() {
  const [overview, setOverview] = useState<OverviewKPIs | null>(null);
  const [winRates, setWinRates] = useState<WinRateTable | null>(null);
  const [scoreAccuracy, setScoreAccuracy] = useState<ScoreAccuracy | null>(null);
  const [pipeline, setPipeline] = useState<PipelineView | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      getKpiOverview(),
      getWinRates(1),
      getScoreAccuracy(),
      getPipeline(),
    ]).then(([ov, wr, sa, pl]) => {
      setOverview(ov);
      setWinRates(wr);
      setScoreAccuracy(sa);
      setPipeline(pl);
    }).catch(e => setError(String(e)));
  }, []);

  if (error) return <div style={{ color: '#dc3545', padding: 24 }}>Error loading KPIs: {error}</div>;
  if (!overview) return <div style={{ color: '#6c757d', padding: 24 }}>Loading dashboard…</div>;

  return (
    <div style={{ padding: 24, maxWidth: 1100 }}>
      <h2 style={{ margin: '0 0 20px', fontSize: 20 }}>KPI Dashboard</h2>

      {/* Top stat cards */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 28, flexWrap: 'wrap' }}>
        <div style={card}>
          <div style={sectionTitle}>Recovery Rate</div>
          <div style={{ fontSize: 32, fontWeight: 700, color: overview.recovery_rate >= 0.5 ? '#198754' : '#dc3545' }}>
            {fmtPct(overview.recovery_rate)}
          </div>
          <div style={{ fontSize: 12, color: '#6c757d', marginTop: 4 }}>
            {overview.total_paid} paid / {overview.total_attempted} attempted
          </div>
        </div>

        <div style={card}>
          <div style={sectionTitle}>Total Recovered</div>
          <div style={{ fontSize: 32, fontWeight: 700, color: '#212529' }}>
            {fmt$$(overview.total_amount_recovered)}
          </div>
          <div style={{ fontSize: 12, color: '#6c757d', marginTop: 4 }}>
            of {fmt$$(overview.total_amount_billed)} billed
          </div>
        </div>

        <div style={card}>
          <div style={sectionTitle}>Cases in Pipeline</div>
          <div style={{ fontSize: 32, fontWeight: 700, color: '#212529' }}>
            {overview.total_cases}
          </div>
          <div style={{ fontSize: 12, color: '#6c757d', marginTop: 4 }}>
            {overview.total_declined} declined at triage
          </div>
        </div>

        <div style={card}>
          <div style={sectionTitle}>Avg Winnability Score</div>
          <div style={{ fontSize: 32, fontWeight: 700, color: scoreColor(overview.avg_winnability_score) }}>
            {overview.avg_winnability_score.toFixed(2)}
          </div>
          <div style={{ marginTop: 6, height: 6, background: '#e9ecef', borderRadius: 3, overflow: 'hidden' }}>
            <div style={{ width: `${overview.avg_winnability_score * 100}%`, height: '100%', background: scoreColor(overview.avg_winnability_score), borderRadius: 3 }} />
          </div>
        </div>
      </div>

      {/* Pipeline breakdown */}
      {pipeline && pipeline.total > 0 && (
        <div style={{ ...card, flex: 'none', marginBottom: 24 }}>
          <div style={sectionTitle}>Pipeline by State</div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: '2px solid #dee2e6' }}>
                <th style={{ textAlign: 'left', padding: '4px 8px', color: '#6c757d', fontWeight: 600 }}>State</th>
                <th style={{ textAlign: 'right', padding: '4px 8px', color: '#6c757d', fontWeight: 600 }}>Cases</th>
                <th style={{ textAlign: 'right', padding: '4px 8px', color: '#6c757d', fontWeight: 600 }}>%</th>
              </tr>
            </thead>
            <tbody>
              {pipeline.stages.map(s => (
                <tr key={s.state} style={{ borderBottom: '1px solid #f1f3f5' }}>
                  <td style={{ padding: '5px 8px' }}>{s.state.replace(/_/g, ' ')}</td>
                  <td style={{ padding: '5px 8px', textAlign: 'right', fontWeight: 600 }}>{s.count}</td>
                  <td style={{ padding: '5px 8px', textAlign: 'right', color: '#6c757d' }}>{fmtPct(s.pct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Win rates table */}
      <div style={{ ...card, flex: 'none', marginBottom: 24 }}>
        <div style={sectionTitle}>Win Rates by Payer × CARC</div>
        {winRates && winRates.rows.length > 0 ? (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: '2px solid #dee2e6' }}>
                {['Payer', 'CARC', 'Specialty', 'Attempts', 'Wins', 'Win Rate'].map(h => (
                  <th key={h} style={{ textAlign: h === 'Payer' || h === 'Specialty' ? 'left' : 'right', padding: '4px 8px', color: '#6c757d', fontWeight: 600 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {winRates.rows.map((row, i) => (
                <tr key={i} style={{ borderBottom: '1px solid #f1f3f5' }}>
                  <td style={{ padding: '5px 8px' }}>{row.payer}</td>
                  <td style={{ padding: '5px 8px', textAlign: 'right' }}>{row.reason_code}</td>
                  <td style={{ padding: '5px 8px' }}>{row.specialty}</td>
                  <td style={{ padding: '5px 8px', textAlign: 'right' }}>{row.attempts}</td>
                  <td style={{ padding: '5px 8px', textAlign: 'right' }}>{row.wins}</td>
                  <td style={{ padding: '5px 8px', textAlign: 'right' }}>
                    <span style={pill(winRateColor(row.win_rate))}>{fmtPct(row.win_rate)}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div style={{ color: '#6c757d', fontSize: 13 }}>No playbook data yet — record outcomes to see win rates.</div>
        )}
      </div>

      {/* Score accuracy */}
      <div style={{ ...card, flex: 'none', marginBottom: 24 }}>
        <div style={sectionTitle}>Score Accuracy</div>
        {scoreAccuracy && scoreAccuracy.rows.length > 0 ? (
          <>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, marginBottom: 8 }}>
              <thead>
                <tr style={{ borderBottom: '2px solid #dee2e6' }}>
                  {['Score Bucket', 'Cases', 'Actual Win Rate', 'Avg Predicted Score'].map(h => (
                    <th key={h} style={{ textAlign: h === 'Score Bucket' ? 'left' : 'right', padding: '4px 8px', color: '#6c757d', fontWeight: 600 }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {scoreAccuracy.rows.map((row, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid #f1f3f5' }}>
                    <td style={{ padding: '5px 8px', fontFamily: 'monospace' }}>{row.score_bucket}</td>
                    <td style={{ padding: '5px 8px', textAlign: 'right' }}>{row.count}</td>
                    <td style={{ padding: '5px 8px', textAlign: 'right' }}>
                      <span style={pill(winRateColor(row.actual_win_rate))}>{fmtPct(row.actual_win_rate)}</span>
                    </td>
                    <td style={{ padding: '5px 8px', textAlign: 'right' }}>{row.avg_predicted_score.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div style={{ fontSize: 12, color: '#6c757d' }}>{scoreAccuracy.correlation_note}</div>
          </>
        ) : (
          <div style={{ color: '#6c757d', fontSize: 13 }}>No scored cases with outcomes yet.</div>
        )}
      </div>

      {/* Triage stats */}
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
        <div style={{ ...card, background: '#fff3cd', borderColor: '#ffc107' }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: '#856404', marginBottom: 4 }}>Decline Rate at Triage</div>
          <div style={{ fontSize: 24, fontWeight: 700, color: '#856404' }}>{fmtPct(overview.decline_rate)}</div>
          <div style={{ fontSize: 12, color: '#856404', marginTop: 4 }}>{overview.total_declined} cases declined</div>
        </div>
        <div style={{ ...card }}>
          <div style={sectionTitle}>Avg Days to Payment</div>
          <div style={{ fontSize: 24, fontWeight: 700, color: '#212529' }}>{overview.avg_days_to_payment.toFixed(0)}</div>
          <div style={{ fontSize: 12, color: '#6c757d', marginTop: 4 }}>days from upload</div>
        </div>
        <div style={{ ...card }}>
          <div style={sectionTitle}>Avg Recovery per Paid Case</div>
          <div style={{ fontSize: 24, fontWeight: 700, color: '#212529' }}>{fmt$$(overview.avg_amount_recovered)}</div>
        </div>
      </div>
    </div>
  );
}
