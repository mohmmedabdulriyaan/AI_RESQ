import { useEffect, useState } from 'react'
import { api, usePoll } from './api'
import { AnalysisCard, Badge, ResqMap, StatusPill } from './components'

export default function AdminPage({ meta }) {
  const [reports, setReports] = usePoll(api.reports, 3000)
  const [teams] = usePoll(api.teams, 3000)
  const [stats] = usePoll(api.stats, 3000)
  const [sel, setSel] = useState(null)
  const [detail, setDetail] = useState(null)
  const [teamId, setTeamId] = useState('')

  useEffect(() => {
    if (!sel) return setDetail(null)
    api.report(sel).then((d) => { setDetail(d); setTeamId(d.team_id || d.suggested_teams[0]?.id || '') })
  }, [sel, reports])

  const assign = async () => {
    if (!teamId) return
    setDetail(await api.assign(sel, Number(teamId)))
    api.reports().then(setReports)
  }
  const reset = async () => { if (confirm('Reset demo data and load scenarios A, B, C?')) { await api.reset(true); setSel(null) } }

  return (
    <div>
      <div className="stats">
        <Stat n={stats?.open} l="Open requests" />
        <Stat n={stats?.by_priority?.Critical || 0} l="Critical" c="#d92d20" />
        <Stat n={stats?.by_priority?.High || 0} l="High" c="#f79009" />
        <Stat n={`${stats?.teams_available ?? '-'}/${stats?.teams_total ?? '-'}`} l="Teams available" />
        <button className="ghost" onClick={reset}>Reset demo</button>
      </div>
      <div className="two-col">
        <div className="card">
          <h2>Priority queue <span className="live">● live</span></h2>
          <table>
            <thead><tr><th>#</th><th>Priority</th><th>Summary</th><th>Status</th><th>Team</th></tr></thead>
            <tbody>
              {reports?.map((r) => (
                <tr key={r.id} className={sel === r.id ? 'sel' : ''} onClick={() => setSel(r.id)}>
                  <td>{r.id}</td><td><Badge p={r.priority} /></td>
                  <td className="small">{r.analysis.summary}<br /><span className="muted">{r.address}</span></td>
                  <td><StatusPill s={r.status} /></td><td className="small">{r.team?.name || '-'}</td>
                </tr>
              ))}
              {reports?.length === 0 && <tr><td colSpan={5} className="muted">No requests yet. Click “Reset demo”.</td></tr>}
            </tbody>
          </table>
        </div>
        <div>
          <ResqMap center={meta?.center} reports={reports || []} teams={teams || []} onSelect={setSel} height={320} />
          {detail && (
            <div className="card">
              <div className="row between"><h3>Request #{detail.id}</h3><StatusPill s={detail.status} /></div>
              <p>“{detail.description}”</p>
              <p className="muted small">{detail.address} · {detail.reporter || 'anonymous'} {detail.phone}</p>
              <AnalysisCard a={detail.analysis} label={detail.recommended_team_label} />
              <h4>Assign a team (your decision)</h4>
              <div className="row">
                <select value={teamId} onChange={(e) => setTeamId(e.target.value)}>
                  {detail.suggested_teams.map((t, i) => (
                    <option key={t.id} value={t.id}>
                      {i === 0 ? '★ ' : ''}{t.name} · {t.status} · {t.distance_km ?? '?'} km{t.type_match ? ' · match' : ''}
                    </option>
                  ))}
                </select>
                <button className="primary" onClick={assign} disabled={detail.status === 'resolved'}>Assign</button>
              </div>
              <h4>Timeline</h4>
              <ul className="timeline">
                {detail.history.map((h, i) => <li key={i}><b>{h.status}</b> · {new Date(h.at).toLocaleTimeString()} · {h.note}</li>)}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

const Stat = ({ n, l, c }) => (
  <div className="stat"><div className="n" style={{ color: c }}>{n ?? '-'}</div><div className="muted small">{l}</div></div>
)
