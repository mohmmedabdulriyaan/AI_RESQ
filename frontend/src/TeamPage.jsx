import { useState } from 'react'
import { api, usePoll } from './api'
import { Badge, StatusPill } from './components'

const NEXT = { assigned: ['accepted', 'Accept'], accepted: ['in_progress', 'Start / on the way'], in_progress: ['resolved', 'Mark resolved'] }

export default function TeamPage() {
  const [teams] = usePoll(api.teams, 5000)
  const [teamId, setTeamId] = useState('')
  const [jobs, setJobs] = usePoll(() => (teamId ? api.reports(`?team_id=${teamId}`) : Promise.resolve([])), 3000, [teamId])

  const advance = async (r) => {
    await api.status(r.id, NEXT[r.status][0], `${NEXT[r.status][1]} by team`)
    setJobs(await api.reports(`?team_id=${teamId}`))
  }

  return (
    <div className="card narrow">
      <h2>Response team console</h2>
      <label>I am
        <select value={teamId} onChange={(e) => setTeamId(e.target.value)}>
          <option value="">Select your team…</option>
          {teams?.map((t) => <option key={t.id} value={t.id}>{t.name} ({t.status})</option>)}
        </select>
      </label>
      {teamId && jobs?.length === 0 && <p className="muted">No assignments yet. Waiting for coordinator…</p>}
      {jobs?.map((r) => (
        <div key={r.id} className="job">
          <div className="row between"><b>#{r.id} <Badge p={r.priority} /></b><StatusPill s={r.status} /></div>
          <p>{r.analysis.summary}</p>
          <p className="small">“{r.description}”</p>
          <p className="muted small">
            {r.address}{' '}
            {r.lat != null && <a target="_blank" rel="noreferrer" href={`https://www.openstreetmap.org/?mlat=${r.lat}&mlon=${r.lng}#map=17/${r.lat}/${r.lng}`}>Open map</a>}
          </p>
          {NEXT[r.status] && <button className="primary" onClick={() => advance(r)}>{NEXT[r.status][1]}</button>}
        </div>
      ))}
    </div>
  )
}
