import { useEffect, useRef, useState } from 'react'
import { api, TEAM_TYPES, usePoll } from './api'
import {
  AnalysisCard, Badge, EmptyState, ErrorBar, Icon, PageHeading, PanelHeading, ResqMap,
  StatusPill, SuccessBar, statusLabel, teamTypeLabel,
} from './components'

const priorities = ['Critical', 'High', 'Moderate', 'Low']
const statuses = ['new', 'assigned', 'accepted', 'in_progress', 'resolved']

export default function AdminPage({ meta, metaError }) {
  const [priority, setPriority] = useState('')
  const [status, setStatus] = useState('')
  const query = '?' + new URLSearchParams({ ...(priority && { priority }), ...(status && { status }) })
  const [reports, , reportError, refreshReports] = usePoll(() => api.reports(query), 3000, [query])
  const [teams, , teamError, refreshTeams] = usePoll(api.teams, 3000)
  const [stats, , statsError, refreshStats] = usePoll(api.stats, 3000)
  const [selected, setSelected] = useState(null)
  const [detail, setDetail, detailError, refreshDetail] = usePoll(
    () => selected ? api.report(selected) : Promise.resolve(null), 3000, [selected],
  )
  const [teamChoice, setTeamChoice] = useState(null)
  const [assignmentMessage, setAssignmentMessage] = useState(null)
  const [resetMessage, setResetMessage] = useState(null)
  const [assigning, setAssigning] = useState(false)
  const [resetting, setResetting] = useState(false)
  const [rosterPending, setRosterPending] = useState(null)
  const detailHeading = useRef(null)
  const focusedIncident = useRef(null)
  const queueHeading = useRef(null)
  const filtersApplied = Boolean(priority || status)
  const suggestedTeams = detail?.suggested_teams ?? []
  const availableTeams = suggestedTeams.filter((team) => team.assignable && team.id !== detail.team_id)
  const teamId = teamChoice ?? (detail?.status === 'new' ? availableTeams[0]?.id : '') ?? ''
  const canDispatch = availableTeams.some((team) => team.id === Number(teamId))

  useEffect(() => {
    if (selected && focusedIncident.current !== selected && detailHeading.current) {
      detailHeading.current.focus()
      focusedIncident.current = selected
    }
  }, [selected, detail, detailError])

  function selectIncident(id) {
    if (id === selected) {
      detailHeading.current?.focus()
      return
    }
    focusedIncident.current = null
    setSelected(id)
    setTeamChoice(null)
    setAssignmentMessage(null)
  }

  function refreshAll() {
    refreshReports()
    refreshTeams()
    refreshStats()
    refreshDetail()
  }

  function closeDetail() {
    selectIncident(null)
    queueHeading.current?.focus()
  }

  async function assign() {
    if (!canDispatch || detailError || assigning || resetting) return
    setAssigning(true)
    setAssignmentMessage(null)
    try {
      const updated = await api.assign(selected, Number(teamId))
      setDetail(updated)
      setTeamChoice(null)
      setAssignmentMessage({ success: `${detail.team ? 'Reassigned' : 'Assigned'} to ${updated.team.name}.` })
      refreshAll()
    } catch (failure) {
      setAssignmentMessage({ error: `Assignment failed. ${failure.message}` })
      refreshAll()
    } finally {
      setAssigning(false)
    }
  }

  async function reset() {
    if (assigning || resetting || rosterPending || !window.confirm('Reset the simulation? This deletes all existing incident reports and team changes, then reloads the sample scenarios and default teams.')) return
    setResetting(true)
    setResetMessage(null)
    try {
      await api.reset(true)
      selectIncident(null)
      setPriority('')
      setStatus('')
      setResetMessage({ success: 'Simulation reset. Sample incidents and default teams were restored.' })
      refreshAll()
    } catch (failure) {
      setResetMessage({ error: `Reset failed. ${failure.message}` })
    } finally {
      setResetting(false)
    }
  }

  return (
    <>
      <PageHeading title="Coordinator dashboard" description="Triage incoming reports, assign response teams, and follow incidents through resolution." />
      <div className="kpi-grid" aria-label="Incident and team totals">
        <Metric label="Open requests" value={stats?.open} caption="All unresolved reports" />
        <Metric label="Unassigned" value={stats?.unassigned} caption="Awaiting dispatch" />
        <Metric label="Critical" value={stats ? stats.by_priority.Critical ?? 0 : null} caption="Open critical incidents" tone="critical" />
        <Metric label="High priority" value={stats ? stats.by_priority.High ?? 0 : null} caption="Open high-priority incidents" tone="high" />
        <Metric label="Teams available" value={stats ? stats.teams_available : null} total={stats?.teams_total} caption="Ready for assignment" tone="available" />
      </div>
      <ErrorBar msg={statsError && `Totals could not refresh. ${statsError}`} />

      <div className="operations-layout">
        <section className="panel queue-panel">
          <div className="panel-pad">
            <div className="panel-heading">
              <div><h2 ref={queueHeading} tabIndex={-1}>Priority queue</h2><p>Highest priority first. Resolved incidents appear last.</p></div>
              <span className={`feed-state ${reportError ? 'feed-offline' : reports ? 'feed-live' : ''}`}>
                {reportError ? 'Updates paused' : reports ? 'Live updates' : 'Connecting'}
              </span>
            </div>
            <div className="queue-toolbar">
              <div className="row filters">
                <select aria-label="Filter by priority" value={priority} onChange={(event) => setPriority(event.target.value)}>
                  <option value="">All priorities</option>{priorities.map((item) => <option key={item}>{item}</option>)}
                </select>
                <select aria-label="Filter by status" value={status} onChange={(event) => setStatus(event.target.value)}>
                  <option value="">All statuses</option>{statuses.map((item) => <option key={item} value={item}>{statusLabel(item)}</option>)}
                </select>
              </div>
              {reports && <span className="muted small">{reports.length} {reports.length === 1 ? 'incident' : 'incidents'}</span>}
            </div>
            <ErrorBar msg={reportError && `The incident queue could not refresh. ${reportError}`} />
          </div>
          {reports?.length > 0 ? (
            <div className="queue-scroll">
              <table className="queue-table">
                <thead><tr><th scope="col">Incident</th><th scope="col">Priority</th><th scope="col">Status</th><th scope="col">Team</th></tr></thead>
                <tbody>
                  {reports.map((report) => (
                    <tr key={report.id} className={selected === report.id ? 'selected-row' : ''}>
                      <td>
                        <button type="button" className="incident-button" aria-pressed={selected === report.id} disabled={assigning || resetting}
                          onClick={() => selectIncident(report.id)}>
                          <span className="incident-id">#{report.id}</span>
                          <strong>{report.analysis?.summary || report.description}</strong>
                        </button>
                        <span className="incident-location"><Icon name="pin" />{report.address || (report.lat != null ? 'Map pin provided' : 'Location unavailable')}</span>
                        {report.duplicate_of && <span className="duplicate-label">Possible duplicate of #{report.duplicate_of}</span>}
                      </td>
                      <td><Badge p={report.priority} /></td>
                      <td><StatusPill s={report.status} /></td>
                      <td className="queue-team">{report.team?.name || 'Unassigned'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : reports ? (
            <EmptyState title={filtersApplied ? 'No incidents match these filters' : 'No incident reports yet'}>
              {filtersApplied ? <button className="text-button" onClick={() => { setPriority(''); setStatus('') }}>Clear filters</button> : 'New reports will appear here as they are submitted.'}
            </EmptyState>
          ) : !reportError && <EmptyState title="Loading incidents…" loading />}
        </section>

        <div className="stack operations-rail">
          {selected && (
            <section className="panel panel-pad incident-detail">
              <div className="panel-heading">
                <div><h2 ref={detailHeading} tabIndex={-1}>Incident #{selected}</h2><p>Report, dispatch, and activity</p></div>
                <button type="button" className="button icon-button" aria-label="Close incident details"
                  disabled={assigning || resetting} onClick={closeDetail}><Icon name="close" /></button>
              </div>
              <ErrorBar msg={detailError} />
              {!detail && !detailError && <EmptyState title="Loading incident…" loading />}
              {detail && (
                <IncidentDetail incident={detail} teamId={teamId} setTeamChoice={setTeamChoice} assign={assign}
                  canDispatch={canDispatch} hasAvailableTeam={availableTeams.length > 0} choiceUnavailable={teamChoice != null && !canDispatch}
                  assigning={assigning} disabled={assigning || resetting || Boolean(detailError)}
                  message={assignmentMessage} onSelect={selectIncident} />
              )}
            </section>
          )}
          <section className="panel operations-map">
            <div className="panel-pad">
              <PanelHeading title="Incident map" description="Report locations and response team positions." />
              <div className="map-legend" aria-label="Map legend">
                <span><i className="legend-incident" />Incident</span>
                <span><i className="legend-team" />Available team</span>
                <span><i className="legend-team legend-unavailable" />Busy or off duty</span>
              </div>
            </div>
            <ResqMap center={meta?.center} error={metaError} reports={reports ?? []} teams={teams ?? []}
              onSelect={assigning || resetting ? undefined : selectIncident} label="Incident and response team map"
              fitReady={Boolean(reports && teams)} />
          </section>
        </div>

        <TeamsPanel teams={teams} error={teamError} onChange={refreshAll} resetting={resetting}
          pending={rosterPending} setPending={setRosterPending} />
      </div>

      <section className="demo-tools" aria-label="Demo data controls">
        <div><h2>Demo data</h2><p>Resetting replaces all incident reports and team changes with the default simulation data.</p></div>
        <button type="button" className="button danger-outline" disabled={resetting || assigning || Boolean(rosterPending)} onClick={reset}>
          {resetting ? 'Resetting…' : 'Reset demo data'}
        </button>
        <ErrorBar msg={resetMessage?.error} />
        <SuccessBar msg={resetMessage?.success} />
      </section>
    </>
  )
}

function Metric({ label, value, total, caption, tone = '' }) {
  return (
    <div className={`metric ${tone}`}>
      <span>{label}</span>
      <strong aria-label={value == null ? `${label} unavailable` : undefined}>
        {value ?? '—'}{total != null && <small> / {total}</small>}
      </strong>
      <small>{caption}</small>
    </div>
  )
}

function IncidentDetail({
  incident, teamId, setTeamChoice, assign, assigning, disabled, message, onSelect,
  canDispatch, hasAvailableTeam, choiceUnavailable,
}) {
  const canAssign = ['new', 'assigned'].includes(incident.status)
  const selectedTeam = incident.suggested_teams.some((team) => team.id === Number(teamId)) ? teamId : ''
  return (
    <div className="detail-content">
      <div className="row"><Badge p={incident.priority} /><StatusPill s={incident.status} /></div>
      <p className="reported-description">{incident.description}</p>
      {incident.duplicate_of && (
        <div className="notice notice-warning">
          <Icon name="alert" /><div>Possible duplicate of <button className="text-button" disabled={disabled}
            onClick={() => onSelect(incident.duplicate_of)}>incident #{incident.duplicate_of}</button>.</div>
        </div>
      )}
      <dl className="facts">
        <div><dt>Landmark or address</dt><dd>{incident.address || 'Not provided'}</dd></div>
        <div><dt>Coordinates</dt><dd>{incident.lat == null ? 'No map pin' : `${incident.lat.toFixed(4)}, ${incident.lng.toFixed(4)}`}</dd></div>
        <div><dt>Reported by</dt><dd>{incident.reporter || 'Anonymous'}</dd></div>
        <div><dt>Phone</dt><dd>{incident.phone || 'Not provided'}</dd></div>
      </dl>
      <section className="dispatch-section" aria-label="Team assignment">
        <h3>Team assignment</h3>
        {canAssign ? (
          <>
            <p className="help">{incident.team ? `Currently assigned to ${incident.team.name}.` : 'Select an available team to send this assignment.'}</p>
            <label className="field dispatch-picker">
              <span>Response team</span>
              <select value={selectedTeam} disabled={disabled || !hasAvailableTeam} onChange={(event) => setTeamChoice(event.target.value)}>
                <option value="" disabled>{!hasAvailableTeam ? 'No assignable teams' : incident.team ? 'Choose a different team' : 'Choose a team'}</option>
                {incident.suggested_teams.map((team) => (
                  <option key={team.id} value={team.id} disabled={!team.assignable || team.id === incident.team_id}>
                    {team.name} · {team.type_match ? 'Type match · ' : ''}{team.id === incident.team_id ? 'Current team' : statusLabel(team.status)}
                    {team.distance_km != null && ` · ${team.distance_km} km`}
                  </option>
                ))}
              </select>
            </label>
            {choiceUnavailable && <p className="field-error" role="status">The selected team is no longer available.</p>}
            <button type="button" className="button primary" onClick={assign} disabled={disabled || !canDispatch}>
              {assigning ? 'Assigning…' : incident.status === 'assigned' ? 'Reassign team' : 'Assign team'}<Icon name="arrow" />
            </button>
          </>
        ) : <p className="help">{incident.team ? `${incident.team.name} · ${statusLabel(incident.status)}` : statusLabel(incident.status)}</p>}
        <ErrorBar msg={message?.error} />
        <SuccessBar msg={message?.success} />
      </section>
      <AnalysisCard a={incident.analysis} label={incident.recommended_team_label} secondaryLabel={incident.secondary_team_label} />
      <section>
        <h3>Activity timeline</h3>
        <ol className="timeline">
          {incident.history.map((event, index) => (
            <li key={index}><div><strong>{statusLabel(event.status)}</strong> <time dateTime={event.at}>{new Date(event.at).toLocaleString()}</time></div>
              <p>{event.note}</p></li>
          ))}
        </ol>
      </section>
    </div>
  )
}

function TeamsPanel({ teams, error, onChange, resetting, pending, setPending }) {
  const [form, setForm] = useState({ name: '', type: 'flood_rescue' })
  const [message, setMessage] = useState(null)

  async function update(action, key, success) {
    if (pending || resetting) return false
    setMessage(null)
    setPending(key)
    try {
      await action()
      setMessage({ success })
      onChange()
      return true
    } catch (failure) {
      setMessage({ error: failure.message })
      return false
    } finally {
      setPending(null)
    }
  }

  async function addTeam(event) {
    event.preventDefault()
    const name = form.name.trim()
    if (!name) return setMessage({ error: 'Enter a team name.' })
    if (await update(() => api.addTeam({ ...form, name }), 'new', `${name} was added.`)) {
      setForm((current) => ({ ...current, name: '' }))
    }
  }

  return (
    <section className="panel teams-panel">
      <div className="panel-pad">
        <PanelHeading title="Response teams" description="Manage the roster and mark teams on or off duty." />
        <ErrorBar msg={error && `The roster could not refresh. ${error}`} />
        {teams?.length > 0 ? (
          <ul className="team-roster">
            {teams.map((team) => (
              <li key={team.id}>
                <div><strong>{team.name}</strong><span className="muted small">{teamTypeLabel(team.type)}</span></div>
                <div className="roster-state"><StatusPill s={team.status} />{team.active_report_id != null && <span className="muted small">#{team.active_report_id}</span>}</div>
                <button type="button" className="button compact" disabled={Boolean(pending) || resetting || team.status === 'busy'}
                  aria-label={`${team.status === 'busy' ? 'On assignment' : team.status === 'off_duty' ? 'Set on duty' : 'Set off duty'}: ${team.name}`}
                  onClick={() => update(() => api.patchTeam(team.id, { on_duty: team.status === 'off_duty' }), team.id,
                    `${team.name} is now ${team.status === 'off_duty' ? 'on duty' : 'off duty'}.`)}>
                  {pending === team.id ? 'Updating…' : team.status === 'busy' ? 'On assignment' : team.status === 'off_duty' ? 'Set on duty' : 'Set off duty'}
                </button>
              </li>
            ))}
          </ul>
        ) : teams ? <EmptyState icon="teams" title="No response teams">Add a team to make it available for dispatch.</EmptyState>
          : !error && <EmptyState icon="teams" title="Loading teams…" loading />}
        <details className="add-team">
          <summary><Icon name="plus" /> Add response team</summary>
          <form className="add-team-form" onSubmit={addTeam}>
            <label className="field"><span>Team name</span>
              <input required value={form.name} placeholder="e.g. Medical Response 2" disabled={Boolean(pending) || resetting}
                onChange={(event) => setForm({ ...form, name: event.target.value })} />
            </label>
            <label className="field"><span>Team type</span>
              <select value={form.type} disabled={Boolean(pending) || resetting} onChange={(event) => setForm({ ...form, type: event.target.value })}>
                {TEAM_TYPES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </label>
            <button className="button primary" disabled={Boolean(pending) || resetting}>{pending === 'new' ? 'Adding…' : 'Add team'}</button>
          </form>
        </details>
        <ErrorBar msg={message?.error} />
        <SuccessBar msg={message?.success} />
      </div>
    </section>
  )
}
