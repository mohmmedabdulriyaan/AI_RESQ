import { useRef, useState } from 'react'
import { api, TYPES } from './api'
import { AnalysisCard, ErrorBar, Icon, PageHeading, PanelHeading, ResqMap, StatusPill, SuccessBar } from './components'

const scenarioNames = {
  flood: 'People trapped by floodwater',
  road: 'Fallen tree blocking a road',
  supplies: 'Relief camp needs food and water',
}

export default function ReportPage({ meta, metaError }) {
  const [form, setForm] = useState({ type: 'flood', description: '', address: '', reporter: '', phone: '' })
  const [pin, setPin] = useState(null)
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [locating, setLocating] = useState(false)
  const [error, setError] = useState('')
  const [fieldError, setFieldError] = useState(null)
  const [gpsError, setGpsError] = useState('')
  const descriptionRef = useRef(null)
  const addressRef = useRef(null)
  const mapHeadingRef = useRef(null)
  const resultRef = useRef(null)
  const locationRequest = useRef(0)

  const change = (field) => (event) => {
    setForm({ ...form, [field]: event.target.value })
    if (fieldError?.field === field) setFieldError(null)
  }

  function pickLocation(position, source) {
    locationRequest.current += 1
    setLocating(false)
    setPin(position && { lat: position.lat, lng: position.lng, source })
    setGpsError('')
    setFieldError((current) => current?.field === 'address' ? null : current)
  }

  function locate() {
    setGpsError('')
    if (!navigator.geolocation) {
      setGpsError('Device location is unavailable. Choose a map point or enter a landmark.')
      return
    }
    const request = ++locationRequest.current
    setLocating(true)
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        if (request === locationRequest.current) pickLocation({ lat: coords.latitude, lng: coords.longitude }, 'GPS location')
      },
      ({ code }) => {
        if (request !== locationRequest.current) return
        setLocating(false)
        setGpsError(code === 1 ? 'Location permission was denied. Choose a map point or enter a landmark.'
          : 'Could not get your location. Try again or enter a landmark.')
      },
      { enableHighAccuracy: true, timeout: 10000 },
    )
  }

  function fillDemo(scenario) {
    setForm({ ...form, type: scenario.type, description: scenario.description, address: scenario.address })
    pickLocation(scenario, 'Sample location')
    setFieldError(null)
    setError('')
    setResult(null)
    descriptionRef.current.focus()
  }

  function invalidate(field, message, ref) {
    setFieldError({ field, message })
    ref.current.focus()
  }

  async function submit(event) {
    event.preventDefault()
    if (busy) return
    setError('')
    setResult(null)
    const address = form.address.trim()
    if (form.description.trim().length < 10) {
      return invalidate('description', 'Describe what is happening in at least 10 characters.', descriptionRef)
    }
    if (!pin && (address.length < 5 || (address.match(/[A-Za-z]/g) || []).length < 3)) {
      return invalidate('address', 'Enter a recognizable landmark or address, or select a point on the map.', addressRef)
    }
    setFieldError(null)
    setBusy(true)
    locationRequest.current += 1
    setLocating(false)
    try {
      const report = await api.create({ ...form, lat: pin?.lat, lng: pin?.lng })
      setResult(report)
      setForm({ ...form, description: '', address: '' })
      setPin(null)
      requestAnimationFrame(() => resultRef.current?.focus())
    } catch (failure) {
      setError(failure.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <PageHeading title="Report an emergency" description="Send an incident report for simulated triage and coordinator review." />
      <div className="report-layout">
        <form className="panel panel-pad report-form" onSubmit={submit} noValidate aria-busy={busy}>
          <PanelHeading title="Incident details" description="Tell the coordinator what happened and where." />
          <fieldset disabled={busy} className="form-fields">
            <div className="field">
              <label htmlFor="emergency-type">Emergency type</label>
              <select id="emergency-type" value={form.type} onChange={change('type')}>
                {TYPES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </div>
            <div className="field">
              <label htmlFor="description">What is happening?</label>
              <textarea id="description" ref={descriptionRef} rows={3} required minLength={10}
                value={form.description} onChange={change('description')}
                placeholder="Describe the danger, who is affected and what help is needed."
                aria-describedby="description-help" aria-invalid={fieldError?.field === 'description' || undefined} />
              <p id="description-help" className={fieldError?.field === 'description' ? 'field-error' : 'help'}
                role={fieldError?.field === 'description' ? 'alert' : undefined}>
                {fieldError?.field === 'description' ? fieldError.message : 'Use at least 10 characters. Include immediate hazards if you know them.'}
              </p>
            </div>
            <div className="field">
              <label htmlFor="address">Landmark or address</label>
              <input id="address" ref={addressRef} value={form.address} onChange={change('address')}
                placeholder="e.g. Near Hanamkonda bus stand" aria-describedby="address-help"
                aria-invalid={fieldError?.field === 'address' || undefined} />
              <p id="address-help" className={fieldError?.field === 'address' ? 'field-error' : 'help'}
                role={fieldError?.field === 'address' ? 'alert' : undefined}>
                {fieldError?.field === 'address' ? fieldError.message : pin ? `Location set from ${pin.source.toLowerCase()}.` : (
                  <>Enter a landmark or <button type="button" className="text-button" onClick={() => mapHeadingRef.current.focus()}>choose on the map</button>.</>
                )}
              </p>
            </div>
            <div className="form-divider">
              <h3>Contact details <span className="optional">Optional</span></h3>
              <div className="field-pair">
                <div className="field">
                  <label htmlFor="reporter">Your name</label>
                  <input id="reporter" autoComplete="name" value={form.reporter} onChange={change('reporter')} />
                </div>
                <div className="field">
                  <label htmlFor="phone">Phone</label>
                  <input id="phone" type="tel" autoComplete="tel" value={form.phone} onChange={change('phone')} />
                </div>
              </div>
            </div>
          </fieldset>
          <ErrorBar msg={error} />
          <div className="report-submit">
            <button type="submit" className="button danger" disabled={busy}>
              {busy ? 'Analyzing report…' : 'Submit report'}{!busy && <Icon name="arrow" />}
            </button>
            <p className="help" role="status">{busy ? 'Submitting your report and analyzing its priority.' : 'Submitted reports appear in the coordinator’s queue.'}</p>
          </div>
        </form>

        <div className="stack">
          {result && (
            <section className="panel panel-pad report-receipt" tabIndex={-1} ref={resultRef} aria-label="Report receipt">
              <SuccessBar msg={`Report #${result.id} received`} />
              <p className="row muted small"><StatusPill s={result.status} /> A coordinator will review the report.</p>
              {result.duplicate_of && <p className="notice notice-warning">Possible duplicate of report #{result.duplicate_of}. The coordinator will check.</p>}
              <AnalysisCard a={result.analysis} label={result.recommended_team_label} secondaryLabel={result.secondary_team_label} />
            </section>
          )}
          <section className="panel location-panel">
            <div className="panel-pad">
              <div className="panel-heading">
                <div><h2 ref={mapHeadingRef} tabIndex={-1}>Incident location</h2><p>Share GPS, place a pin, or enter a landmark in the form.</p></div>
              </div>
              <button type="button" className="button" disabled={locating || busy} onClick={locate}>
                <Icon name="locate" />{locating ? 'Finding location…' : 'Use my location'}
              </button>
              <ErrorBar msg={gpsError} />
            </div>
            <ResqMap center={meta?.center} error={metaError} pin={pin} label="Select an incident location on the map"
              onPick={busy ? undefined : (position) => pickLocation(position, 'Map pin')} />
            <div className="location-feedback">
              <Icon name="pin" />
              <div role="status">
                <strong>{pin ? pin.source : 'No map pin selected'}</strong>
                <p>{pin ? `${pin.lat.toFixed(4)}, ${pin.lng.toFixed(4)}` : 'Tap the map or pan and choose “Use map center”.'}</p>
              </div>
              {pin && <button className="text-button" type="button" disabled={busy} onClick={() => pickLocation(null)}>Clear pin</button>}
            </div>
          </section>
          <section className="panel panel-pad demo-scenarios">
            <PanelHeading title="Sample scenarios" description="Load a sample into the form to try the simulation." />
            {meta?.demo_reports?.length > 0 ? (
              <div className="sample-list">
                {meta.demo_reports.map((scenario) => (
                  <button key={scenario.type} className="button" type="button" disabled={busy} onClick={() => fillDemo(scenario)}>
                    {scenarioNames[scenario.type] ?? scenario.address}<Icon name="arrow" />
                  </button>
                ))}
              </div>
            ) : <p className="help" role="status">{metaError ? 'Sample scenarios are temporarily unavailable.' : 'Loading sample scenarios…'}</p>}
          </section>
        </div>
      </div>
    </>
  )
}
