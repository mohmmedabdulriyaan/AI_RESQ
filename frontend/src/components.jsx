import { MapContainer, TileLayer, CircleMarker, Popup, useMapEvents } from 'react-leaflet'
import { PRIORITY_COLOR } from './api'

export const Badge = ({ p }) => (
  <span className="badge" style={{ background: PRIORITY_COLOR[p] || '#667085' }}>{p}</span>
)

export const StatusPill = ({ s }) => <span className={`pill s-${s}`}>{s.replace('_', ' ')}</span>

export function AnalysisCard({ a, label }) {
  if (!a) return null
  return (
    <div className="analysis">
      <div className="row between">
        <strong>AI analysis</strong>
        <span className="muted small">{a.source === 'llm' ? 'LLM' : 'Rule engine (fallback)'} · score {a.priority_score}/100</span>
      </div>
      <p>{a.summary}</p>
      <div className="grid2">
        <div><span className="muted">Category</span><br />{a.category.replace('_', ' ')}</div>
        <div><span className="muted">Suggested priority</span><br /><Badge p={a.priority} /></div>
        <div><span className="muted">People affected</span><br />{a.people_affected ?? 'unknown'}</div>
        <div><span className="muted">Recommended resource</span><br />{label}</div>
      </div>
      {a.vulnerable?.length > 0 && <p className="small">Vulnerable: {a.vulnerable.join(', ')}</p>}
      {a.hazards?.length > 0 && <p className="small">Risk signals: {a.hazards.join(', ')}</p>}
      <p className="next">Next step: {a.next_step}</p>
    </div>
  )
}

function ClickToPin({ onPick }) {
  useMapEvents({ click: (e) => onPick && onPick(e.latlng) })
  return null
}

export function ResqMap({ center, reports = [], teams = [], pin, onPick, onSelect, height = 380 }) {
  if (!center) return null
  return (
    <MapContainer center={center} zoom={13} style={{ height, borderRadius: 12 }}>
      <TileLayer attribution="&copy; OpenStreetMap" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      <ClickToPin onPick={onPick} />
      {reports.filter((r) => r.lat != null).map((r) => (
        <CircleMarker key={'r' + r.id} center={[r.lat, r.lng]} radius={r.status === 'resolved' ? 6 : 11}
          pathOptions={{ color: PRIORITY_COLOR[r.priority], fillOpacity: r.status === 'resolved' ? 0.2 : 0.7 }}
          eventHandlers={{ click: () => onSelect && onSelect(r.id) }}>
          <Popup><b>#{r.id} {r.priority}</b><br />{r.analysis.summary}<br /><i>{r.status}</i></Popup>
        </CircleMarker>
      ))}
      {teams.map((t) => (
        <CircleMarker key={'t' + t.id} center={[t.lat, t.lng]} radius={6}
          pathOptions={{ color: t.status === 'available' ? '#1570ef' : '#98a2b3', fillOpacity: 1 }}>
          <Popup>{t.name}<br />{t.status}</Popup>
        </CircleMarker>
      ))}
      {pin && <CircleMarker center={[pin.lat, pin.lng]} radius={10} pathOptions={{ color: '#7a5af8', fillOpacity: 0.8 }} />}
    </MapContainer>
  )
}
