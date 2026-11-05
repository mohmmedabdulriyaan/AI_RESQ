import { useState } from 'react'
import { api, TYPES } from './api'
import { AnalysisCard, ResqMap } from './components'

export default function ReportPage({ meta }) {
  const [f, setF] = useState({ type: 'flood', description: '', address: '', reporter: '', phone: '' })
  const [pin, setPin] = useState(null)
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })

  const locate = () => {
    if (!navigator.geolocation) return setErr('Geolocation not available; click the map instead.')
    navigator.geolocation.getCurrentPosition(
      (p) => setPin({ lat: p.coords.latitude, lng: p.coords.longitude }),
      () => setErr('Location denied; click the map to drop a pin.'),
    )
  }

  const fillDemo = (d) => {
    setF({ ...f, type: d.type, description: d.description, address: d.address })
    setPin({ lat: d.lat, lng: d.lng })
  }

  const submit = async (e) => {
    e.preventDefault()
    setErr(''); setBusy(true)
    try {
      setResult(await api.create({ ...f, lat: pin?.lat, lng: pin?.lng }))
    } catch (e) { setErr(String(e.message)) } finally { setBusy(false) }
  }

  return (
    <div className="two-col">
      <form className="card" onSubmit={submit}>
        <h2>Report an emergency</h2>
        <div className="demo-row">
          <span className="muted small">Demo scenarios:</span>
          {meta?.demo_reports.map((d, i) => (
            <button type="button" key={i} className="ghost" onClick={() => fillDemo(d)}>{'ABC'[i]}</button>
          ))}
        </div>
        <label>Emergency type
          <select value={f.type} onChange={set('type')}>{TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
        </label>
        <label>What is happening?
          <textarea rows={4} required value={f.description} onChange={set('description')}
            placeholder="e.g. Water is rising, 3 people stuck on the roof including a child" />
        </label>
        <label>Landmark / address
          <input value={f.address} onChange={set('address')} placeholder="Near ... " />
        </label>
        <div className="row">
          <button type="button" className="ghost" onClick={locate}>📍 Use my location</button>
          <span className="muted small">{pin ? `${pin.lat.toFixed(4)}, ${pin.lng.toFixed(4)}` : 'or tap the map'}</span>
        </div>
        <div className="row">
          <input placeholder="Your name (optional)" value={f.reporter} onChange={set('reporter')} />
          <input placeholder="Phone (optional)" value={f.phone} onChange={set('phone')} />
        </div>
        {err && <p className="err">{err}</p>}
        <button className="primary" disabled={busy}>{busy ? 'Analyzing…' : 'Submit report'}</button>
      </form>
      <div>
        <ResqMap center={meta?.center} pin={pin} onPick={setPin} height={300} />
        {result && (
          <div className="card">
            <h3>Report #{result.id} received</h3>
            <p className="muted small">A human coordinator will review it. Status: {result.status}</p>
            <AnalysisCard a={result.analysis} label={result.recommended_team_label} />
          </div>
        )}
      </div>
    </div>
  )
}
