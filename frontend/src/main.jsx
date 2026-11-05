import React, { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import 'leaflet/dist/leaflet.css'
import './styles.css'
import { api } from './api'
import ReportPage from './ReportPage'
import AdminPage from './AdminPage'
import TeamPage from './TeamPage'

const TABS = [['report', 'Report emergency'], ['admin', 'Coordinator dashboard'], ['team', 'Response team']]

function App() {
  const [tab, setTab] = useState(location.hash.slice(1) || 'report')
  const [meta, setMeta] = useState(null)
  useEffect(() => { api.meta().then(setMeta) }, [])
  useEffect(() => {
    const h = () => setTab(location.hash.slice(1) || 'report')
    addEventListener('hashchange', h)
    return () => removeEventListener('hashchange', h)
  }, [])

  return (
    <>
      <header>
        <div className="brand">🚨 AI RESQ <span className="muted small">Smart Emergency Response &amp; Resource Allocation</span></div>
        <nav>{TABS.map(([k, l]) => <a key={k} href={'#' + k} className={tab === k ? 'on' : ''}>{l}</a>)}</nav>
      </header>
      <div className="banner">
        Simulation / decision-support prototype only. Not a real dispatch service. In a real emergency, call 112 immediately.
        AI suggests; a human coordinator decides.
      </div>
      <main>
        {tab === 'report' && <ReportPage meta={meta} />}
        {tab === 'admin' && <AdminPage meta={meta} />}
        {tab === 'team' && <TeamPage />}
      </main>
    </>
  )
}

createRoot(document.getElementById('root')).render(<App />)
