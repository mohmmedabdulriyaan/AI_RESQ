import { useState } from 'react'
import { api, usePoll } from './api'
import {
  Badge, EmptyState, ErrorBar, Icon, PageHeading, PanelHeading, StatusPill, SuccessBar, teamTypeLabel,
} from './components'

const nextAction = {
  assigned: { status: 'accepted', label: 'Accept assignment', feedback: 'Assignment accepted.' },
  accepted: { status: 'in_progress', label: 'Start work', feedback: 'Work started.' },
  in_progress: { status: 'resolved', label: 'Mark resolved', feedback: 'Incident marked resolved.' },
}

export default function TeamPage() {
  const [teams, , teamError, refreshTeams] = usePoll(api.teams, 5000)
  const [teamId, setTeamId] = useState('')
  const [jobs, setJobs, jobError, refreshJobs] = usePoll(() => teamId ? api.reports(`?team_id=${teamId}`) : Promise.resolve([]), 3000, [teamId])
  const selected = teams?.find((team) => team.id === Number(teamId))
  const [message, setMessage] = useState(null)
  const [pending, setPending] = useState(null)

  async function update(report, decline = false) {
    if (!selected || !jobs || pending) return
    const next = nextAction[report.status]
    setMessage(null)
    setPending(report.id)
    try {
      if (decline) {
        await api.decline(report.id, selected.id, 'Team unavailable')
        setJobs(jobs.filter((job) => job.id !== report.id))
        setMessage({ success: `Incident #${report.id} was returned to the coordinator’s queue.` })
      } else {
        const updated = await api.status(report.id, next.status, selected.id)
        setJobs(jobs.map((job) => job.id === report.id ? updated : job))
        setMessage({ success: `Incident #${report.id}. ${next.feedback}` })
      }
    } catch (failure) {
      setMessage({ error: failure.message })
    } finally {
      refreshJobs()
      refreshTeams()
      setPending(null)
    }
  }

  const awaiting = jobs?.filter((report) => report.status === 'assigned') ?? []
  const active = jobs?.filter((report) => ['accepted', 'in_progress'].includes(report.status)) ?? []
  const resolved = jobs?.filter((report) => report.status === 'resolved') ?? []

  return (
    <>
      <PageHeading title="Response team console" description="Review dispatches, acknowledge assignments, and report progress to the coordinator." />
      <div className="team-layout">
        <section className="panel panel-pad team-selector">
          <PanelHeading title="Select your team" description="Choose a response unit to view its assignments." />
          <label className="field">
            <span>Response team</span>
            <select value={teamId} disabled={!teams?.length || Boolean(pending)} onChange={(event) => {
              setTeamId(event.target.value)
              setMessage(null)
            }}>
              <option value="">{teams?.length ? 'Choose a team…' : teamError ? 'Roster unavailable' : teams ? 'No teams available' : 'Loading teams…'}</option>
              {teamId && !selected && <option value={teamId}>Previously selected team</option>}
              {teams?.map((team) => <option key={team.id} value={team.id}>{team.name}</option>)}
            </select>
          </label>
          <ErrorBar msg={teamError && `The roster could not refresh. ${teamError}`} />
          {selected && (
            <div className="team-profile">
              <Icon name="teams" />
              <div><h3>{selected.name}</h3><p>{teamTypeLabel(selected.type)}</p><StatusPill s={selected.status} /></div>
            </div>
          )}
        </section>

        <section className="panel panel-pad assignment-workspace">
          <PanelHeading title="Assignments" description={selected ? `Dispatch activity for ${selected.name}.` : 'View new dispatches, work in progress, and resolved incidents.'} />
          <ErrorBar msg={jobError && `Assignments could not refresh. ${jobError}`} />
          <ErrorBar msg={message?.error} />
          <SuccessBar msg={message?.success} />
          {!teamId ? (
            <EmptyState icon="teams" title="Choose a team to get started">Its assignments will appear here.</EmptyState>
          ) : !selected && teams ? (
            <EmptyState icon="teams" title="This team is unavailable">Choose another team from the response roster.</EmptyState>
          ) : !jobs ? (
            !jobError && <EmptyState title="Loading assignments…" loading />
          ) : (
            <>
              {awaiting.length === 0 && active.length === 0 && (
                <EmptyState title="No current assignments">New dispatches will appear here as soon as the coordinator assigns them.</EmptyState>
              )}
              <AssignmentGroup title="Awaiting response" reports={awaiting} pending={pending} disabled={Boolean(jobError) || !selected} onUpdate={update} />
              <AssignmentGroup title="Active work" reports={active} pending={pending} disabled={Boolean(jobError) || !selected} onUpdate={update} />
              <AssignmentGroup title="Resolved incidents" reports={resolved} pending={pending} disabled={Boolean(jobError) || !selected} onUpdate={update} />
            </>
          )}
        </section>
      </div>
    </>
  )
}

function AssignmentGroup({ title, reports, pending, disabled, onUpdate }) {
  if (!reports.length) return null
  return (
    <section className="assignment-group">
      <h3>{title} <span className="count">{reports.length}</span></h3>
      {reports.map((report) => (
        <article className="assignment-card" key={report.id}>
          <div className="row">
            <strong className="incident-id">Incident #{report.id}</strong><Badge p={report.priority} /><StatusPill s={report.status} />
          </div>
          <h4>{report.analysis?.summary || report.description}</h4>
          {report.status !== 'resolved' && report.analysis?.summary && <p>{report.description}</p>}
          <div className="assignment-location">
            <Icon name="pin" /><span>{report.address || (report.lat != null ? 'Map pin provided' : 'Location unavailable')}</span>
            {report.lat != null && (
              <a target="_blank" rel="noreferrer" href={`https://www.openstreetmap.org/?mlat=${report.lat}&mlon=${report.lng}#map=17/${report.lat}/${report.lng}`}>
                Open map <Icon name="external" />
              </a>
            )}
          </div>
          {nextAction[report.status] && (
            <div className="row assignment-actions">
              <button type="button" className="button primary" disabled={disabled || Boolean(pending)} onClick={() => onUpdate(report)}>
                {pending === report.id ? 'Updating…' : nextAction[report.status].label}
              </button>
              {report.status === 'assigned' && (
                <button type="button" className="button" disabled={disabled || Boolean(pending)} onClick={() => onUpdate(report, true)}>Decline</button>
              )}
            </div>
          )}
        </article>
      ))}
    </section>
  )
}
