const j = async (r) => {
  if (!r.ok) throw new Error((await r.text()) || r.statusText)
  return r.json()
}
const post = (url, body) =>
  fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body ?? {}) }).then(j)

export const api = {
  meta: () => fetch('/api/meta').then(j),
  reports: (q = '') => fetch('/api/reports' + q).then(j),
  report: (id) => fetch(`/api/reports/${id}`).then(j),
  create: (body) => post('/api/reports', body),
  analyze: (body) => post('/api/analyze', body),
  assign: (id, team_id) => post(`/api/reports/${id}/assign`, { team_id }),
  status: (id, status, note = '') => post(`/api/reports/${id}/status`, { status, note }),
  teams: () => fetch('/api/teams').then(j),
  stats: () => fetch('/api/stats').then(j),
  reset: (seed = true) => post(`/api/demo/reset?seed=${seed}`),
}

export const PRIORITY_COLOR = { Critical: '#d92d20', High: '#f79009', Moderate: '#eaaa08', Low: '#12b76a' }
export const TYPES = [
  ['flood', 'Flood'], ['fire', 'Fire'], ['medical', 'Medical'], ['accident', 'Road accident'],
  ['road', 'Road blocked'], ['supplies', 'Food / water / supplies'], ['other', 'Other'],
]

// Poll for "live" updates. Simple and demo-proof (no websockets to break).
import { useEffect, useState } from 'react'
export function usePoll(fn, ms = 3000, deps = []) {
  const [data, setData] = useState(null)
  useEffect(() => {
    let alive = true
    const tick = () => fn().then((d) => alive && setData(d)).catch(() => {})
    tick()
    const t = setInterval(tick, ms)
    return () => { alive = false; clearInterval(t) }
  }, deps)
  return [data, setData]
}
