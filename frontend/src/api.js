import { useEffect, useState } from 'react'
// Turn FastAPI errors ({detail: "..."} or 422 [{msg}]) into readable messages.
const j = async (r) => {
  if (!r.ok) {
    let msg = r.statusText
    try {
      const d = (await r.json()).detail
      msg = Array.isArray(d) ? d.map((e) => String(e.msg).replace(/^Value error, /, '')).join(' ') : d || msg
    } catch {
      if (r.status >= 500) msg = `Server unreachable or crashed (HTTP ${r.status}). Is the backend running?`
    }
    throw new Error(msg)
  }
  return r.json()
}
const send = (method) => (url, body) =>
  fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body ?? {}) })
    .catch(() => { throw new Error('Cannot reach the server. Is the backend running on port 8000?') })
    .then(j)
const post = send('POST')
const patch = send('PATCH')
const get = (url) => fetch(url).catch(() => { throw new Error('Cannot reach the server.') }).then(j)

export const api = {
  meta: () => get('/api/meta'),
  reports: (q = '') => get('/api/reports' + q),
  report: (id) => get(`/api/reports/${id}`),
  create: (body) => post('/api/reports', body),
  analyze: (body) => post('/api/analyze', body),
  assign: (id, team_id) => post(`/api/reports/${id}/assign`, { team_id }),
  status: (id, status, team_id, note = '') => post(`/api/reports/${id}/status`, { status, team_id, note }),
  decline: (id, team_id, reason = '') => post(`/api/reports/${id}/decline`, { team_id, reason }),
  teams: () => get('/api/teams'),
  addTeam: (body) => post('/api/teams', body),
  patchTeam: (id, body) => patch(`/api/teams/${id}`, body),
  stats: () => get('/api/stats'),
  reset: (seed = true) => post(`/api/demo/reset?seed=${seed}`),
}

export const TYPES = [
  ['flood', 'Flood'], ['fire', 'Fire'], ['medical', 'Medical'], ['accident', 'Road accident'],
  ['road', 'Road blocked'], ['supplies', 'Food / water / supplies'], ['other', 'Other'],
]

export const TEAM_TYPES = [
  ['flood_rescue', 'Flood rescue'], ['fire_response', 'Fire response'], ['medical_response', 'Medical response'],
  ['road_clearance', 'Road clearance'], ['relief_supply', 'Relief supply'], ['general', 'General'],
]

// Keep snapshots tied to their query and avoid overlapping requests on slow connections.
export function usePoll(fn, ms = 3000, deps = []) {
  const key = JSON.stringify(deps)
  const [snapshot, setSnapshot] = useState(null)
  const [revision, setRevision] = useState(0)
  useEffect(() => {
    let alive = true
    let timer
    async function tick() {
      try {
        const data = await fn()
        if (alive) setSnapshot({ key, data, error: '' })
      } catch (failure) {
        if (alive) setSnapshot((current) => ({
          key,
          data: current?.key === key ? current.data : null,
          error: failure.message || 'Connection problem',
        }))
      } finally {
        if (alive) timer = setTimeout(tick, ms)
      }
    }
    tick()
    return () => { alive = false; clearTimeout(timer) }
  }, [key, revision, ms])

  const current = snapshot?.key === key ? snapshot : null
  const setData = (data) => setSnapshot({ key, data, error: '' })
  const refresh = () => setRevision((value) => value + 1)
  return [current?.data ?? null, setData, current?.error ?? '', refresh]
}
