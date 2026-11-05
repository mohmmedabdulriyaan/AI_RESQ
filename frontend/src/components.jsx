import { useEffect, useRef, useState } from 'react'
import { divIcon, DomEvent } from 'leaflet'
import { MapContainer, Marker, Popup, TileLayer, useMap, useMapEvents } from 'react-leaflet'
import { TEAM_TYPES } from './api'

const icons = {
  shield: <><path d="M12 22s7-3.2 7-9V5l-7-3-7 3v8c0 5.8 7 9 7 9Z" /><path d="M8.5 11.5h7m-3.5-3.5v7" /></>,
  alert: <><path d="M10.3 4.5 2.5 18a1 1 0 0 0 .9 1.5h17.2a1 1 0 0 0 .9-1.5L13.7 4.5a2 2 0 0 0-3.4 0Z" /><path d="M12 9v4m0 3h.01" /></>,
  plus: <path d="M12 5v14M5 12h14" />,
  queue: <><rect x="4" y="5" width="16" height="14" rx="2" /><path d="M8 9h8m-8 3h8m-8 3h5" /></>,
  teams: <><circle cx="9" cy="8" r="3" /><path d="M3 20v-2a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v2m2-15a3 3 0 0 1 0 6m4 9v-2a4 4 0 0 0-3-3.9" /></>,
  pin: <><path d="M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 1 1 14 0Z" /><circle cx="12" cy="10" r="2.3" /></>,
  locate: <><circle cx="12" cy="12" r="6" /><circle cx="12" cy="12" r="2" /><path d="M12 2v4m0 12v4M2 12h4m12 0h4" /></>,
  arrow: <path d="M4 12h15m-6-6 6 6-6 6" />,
  check: <path d="m5 12 4 4L19 6" />,
  external: <path d="M13 5h6v6m0-6-9 9m8 0v5H5V6h5" />,
  close: <path d="m6 6 12 12M18 6 6 18" />,
}

export function Icon({ name }) {
  return <svg className="icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{icons[name]}</svg>
}

const statusLabels = {
  new: 'New', assigned: 'Assigned', accepted: 'Accepted', in_progress: 'In progress',
  resolved: 'Resolved', available: 'Available', busy: 'Busy', off_duty: 'Off duty',
}
export const statusLabel = (status) => statusLabels[status] ?? status
export const teamTypeLabel = (type) => TEAM_TYPES.find(([value]) => value === type)?.[1] ?? type

export const Badge = ({ p }) => <span className={`badge priority-${p?.toLowerCase()}`}>{p}</span>
export const StatusPill = ({ s }) => <span className={`badge status-${s}`}>{statusLabel(s)}</span>

export function PageHeading({ title, description, children }) {
  return (
    <div className="page-heading">
      <div><h1>{title}</h1><p>{description}</p></div>
      {children}
    </div>
  )
}

export function PanelHeading({ title, description, children }) {
  return (
    <div className="panel-heading">
      <div><h2>{title}</h2>{description && <p>{description}</p>}</div>
      {children}
    </div>
  )
}

export function EmptyState({ icon = 'queue', title, children, loading = false }) {
  return (
    <div className="empty-state" role={loading ? 'status' : undefined}>
      <Icon name={icon} /><strong>{title}</strong>
      {children && <p>{children}</p>}
    </div>
  )
}

export const ErrorBar = ({ msg }) => msg ? (
  <div className="notice notice-error" role="alert"><Icon name="alert" /><div>{msg}</div></div>
) : null

export const SuccessBar = ({ msg }) => msg ? (
  <div className="notice notice-success" role="status"><Icon name="check" /><div>{msg}</div></div>
) : null

const analysisSources = { ml: 'Local ML + rules', rules: 'Rule engine', llm: 'LLM' }

export function AnalysisCard({ a, label, secondaryLabel }) {
  if (!a) return null
  return (
    <section className="analysis" aria-label="AI analysis">
      <div className="row between">
        <h3>AI analysis</h3>
        <span className="muted small">{analysisSources[a.source] ?? 'Rule engine'} · {a.priority_score}/100</span>
      </div>
      <p>{a.summary}</p>
      <dl className="facts">
        <div><dt>Category</dt><dd className="capitalize">{a.category.replaceAll('_', ' ')}</dd></div>
        <div><dt>Suggested priority</dt><dd><Badge p={a.priority} /></dd></div>
        <div><dt>People affected</dt><dd>{a.people_affected ?? 'Unknown'}</dd></div>
        <div><dt>Recommended resource</dt><dd>{label}</dd></div>
      </dl>
      {secondaryLabel && <p className="small"><strong>Secondary resource</strong> {secondaryLabel}</p>}
      {a.vulnerable?.length > 0 && <p className="small"><strong>Vulnerable groups</strong> {a.vulnerable.join(', ')}</p>}
      {a.hazards?.length > 0 && <p className="small"><strong>Risk signals</strong> {a.hazards.join(', ')}</p>}
      {a.reasons?.length > 0 && (
        <details className="small"><summary>Why this priority?</summary><ul>{a.reasons.map((reason, index) => <li key={index}>{reason}</li>)}</ul></details>
      )}
      <p className="next-step"><strong>Suggested next step</strong> {a.next_step}</p>
      <p className="muted small">A human coordinator reviews every AI suggestion.</p>
    </section>
  )
}

const mapIcon = (kind, size) => divIcon({ className: `map-marker ${kind}`, html: '<span></span>', iconSize: [size, size] })
const pinIcon = mapIcon('marker-pin', 24)
const incidentIcons = Object.fromEntries(['Critical', 'High', 'Moderate', 'Low'].map((priority) =>
  [priority, mapIcon(`marker-incident marker-${priority.toLowerCase()}`, 18)]))
const resolvedIcon = mapIcon('marker-incident marker-resolved', 14)
const teamIcon = mapIcon('marker-team', 16)
const unavailableIcon = mapIcon('marker-team marker-unavailable', 16)

function fitLocations(map, locations) {
  map.fitBounds(locations, { maxZoom: 15, padding: [26, 26], animate: false })
}

function MapInteraction({ pin, onPick, locations, fitReady }) {
  const map = useMap()
  const fitted = useRef(false)
  const lat = pin?.lat
  const lng = pin?.lng
  useEffect(() => {
    if (lat != null && lng != null) map.setView([lat, lng], Math.max(map.getZoom(), 15), { animate: false })
  }, [map, lat, lng])
  useEffect(() => {
    if (!fitted.current && fitReady && locations.length) {
      fitLocations(map, locations)
      fitted.current = true
    }
  }, [map, locations, fitReady])
  useMapEvents({ click: (event) => onPick?.(event.latlng) })
  if (!onPick && locations.length === 0) return null
  return (
    <button className="map-center-control" type="button" ref={(element) => { if (element) DomEvent.disableClickPropagation(element) }}
      onClick={() => onPick ? onPick(map.getCenter()) : fitLocations(map, locations)}>
      <Icon name={onPick ? 'locate' : 'pin'} />{onPick ? 'Use map center' : 'Fit markers'}
    </button>
  )
}

export function ResqMap({ center, error, reports = [], teams = [], pin, onPick, onSelect, label, fitReady = false }) {
  const [tileError, setTileError] = useState(false)
  const mappedReports = reports.filter((report) => report.lat != null && report.lng != null)
  const mappedTeams = teams.filter((team) => team.lat != null && team.lng != null)
  const locations = [...mappedReports, ...mappedTeams].map(({ lat, lng }) => [lat, lng])

  if (!center) return (
    <div className="map-placeholder">
      <EmptyState icon="pin" title={error ? 'Map unavailable' : 'Loading map…'} loading={!error}>
        {error && (onPick ? 'You can still enter a landmark or use your device location.' : 'The map will retry automatically.')}
      </EmptyState>
    </div>
  )

  return (
    <div className="map-frame" role="region" aria-label={label}>
      <MapContainer center={center} zoom={13} scrollWheelZoom={false} className="resq-map">
        <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          eventHandlers={{ loading: () => setTileError(false), tileerror: () => setTileError(true) }} />
        <MapInteraction pin={pin} onPick={onPick} locations={locations} fitReady={fitReady} />
        {mappedReports.map((report) => (
          <Marker key={`report-${report.id}`} position={[report.lat, report.lng]}
            title={`Incident #${report.id} · ${report.priority}`}
            icon={report.status === 'resolved' ? resolvedIcon : incidentIcons[report.priority] ?? resolvedIcon}
            zIndexOffset={100}
            eventHandlers={{ click: () => onSelect?.(report.id) }}>
            <Popup><strong>Incident #{report.id} · {report.priority}</strong><br />{report.analysis?.summary}<br />{statusLabel(report.status)}</Popup>
          </Marker>
        ))}
        {mappedTeams.map((team) => (
          <Marker key={`team-${team.id}`} position={[team.lat, team.lng]} title={team.name}
            icon={team.status === 'available' ? teamIcon : unavailableIcon}>
            <Popup><strong>{team.name}</strong><br />{statusLabel(team.status)}</Popup>
          </Marker>
        ))}
        {pin && <Marker position={[pin.lat, pin.lng]} title="Selected report location" icon={pinIcon} keyboard={false} interactive={false} />}
      </MapContainer>
      {tileError && (
        <p className="map-message" role="status">The street map may be incomplete. {onPick ? 'Use GPS or a landmark if you can’t verify the pin.' : 'Incident and team markers are still shown.'}</p>
      )}
    </div>
  )
}
