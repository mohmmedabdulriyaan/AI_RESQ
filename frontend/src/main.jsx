import { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import 'leaflet/dist/leaflet.css'
import './styles.css'
import { api, usePoll } from './api'
import { Icon } from './components'
import ReportPage from './ReportPage'
import AdminPage from './AdminPage'
import TeamPage from './TeamPage'

const pages = {
  report: ['Report emergency', 'plus'],
  admin: ['Coordinator dashboard', 'queue'],
  team: ['Response team console', 'teams'],
}

function currentPage() {
  const hash = location.hash.slice(1)
  return Object.hasOwn(pages, hash) ? hash : 'report'
}

function App() {
  const [tab, setTab] = useState(currentPage)
  const [meta, , metaError] = usePoll(api.meta, 15000)
  useEffect(() => {
    const handleHashChange = () => setTab(currentPage())
    addEventListener('hashchange', handleHashChange)
    return () => removeEventListener('hashchange', handleHashChange)
  }, [])

  return (
    <>
      <a className="skip-link" href="#main-content" onClick={(event) => {
        event.preventDefault()
        document.getElementById('main-content').focus()
      }}>Skip to content</a>
      <header className="app-header">
        <div className="frame app-nav">
          <a className="brand" href="#report" aria-label="AI RESQ home">
            <span className="brand-mark"><Icon name="shield" /></span>
            <span>AI RESQ<small>Emergency coordination</small></span>
          </a>
          <nav aria-label="Operations navigation">
            {['admin', 'team'].map((page) => (
              <a key={page} href={'#' + page} aria-current={tab === page ? 'page' : undefined} className="nav-link">
                <Icon name={pages[page][1]} />{pages[page][0]}
              </a>
            ))}
          </nav>
          <a href="#report" aria-current={tab === 'report' ? 'page' : undefined} className="nav-emergency">
            <Icon name={pages.report[1]} />{pages.report[0]}
          </a>
        </div>
      </header>
      <aside className="safety-bar" aria-label="Simulation safety notice">
        <div className="frame safety-inner">
          <Icon name="alert" />
          <p><strong>Simulation only.</strong> This platform does not dispatch emergency services. In a real emergency, <a href="tel:112">call 112 immediately</a>. AI suggests priorities and a human coordinator decides.</p>
        </div>
      </aside>
      <main id="main-content" className="frame main-frame" tabIndex={-1}>
        {tab === 'report' && <ReportPage meta={meta} metaError={metaError} />}
        {tab === 'admin' && <AdminPage meta={meta} metaError={metaError} />}
        {tab === 'team' && <TeamPage />}
      </main>
    </>
  )
}

createRoot(document.getElementById('root')).render(<App />)
