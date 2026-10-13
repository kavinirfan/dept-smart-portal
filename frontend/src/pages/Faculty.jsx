import { useCallback, useState } from 'react'
import { ago, api, download } from '../api'
import { ROLE_LABELS, useAuth } from '../auth.jsx'
import usePolling from '../usePolling.js'

const STATES = [
  { value: 'Available', cls: 'ok' },
  { value: 'In Class', cls: 'busy' },
  { value: 'On Leave', cls: 'off' },
  { value: 'Unavailable', cls: 'off' },
]
const clsFor = (s) => STATES.find((x) => x.value === s)?.cls ?? 'unknown'

function MyStatus({ mine, onSaved }) {
  const [note, setNote] = useState('')
  const [error, setError] = useState('')

  async function save(status) {
    setError('')
    try {
      await api('/faculty/status', { method: 'POST', body: { status, note } })
      setNote('')
      onSaved()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <section className="card">
      <div className="row-between">
        <h2>My status</h2>
        {mine?.status && <span className="muted-text">Now: <strong>{mine.status}</strong>{mine.note ? ` · ${mine.note}` : ''} · {ago(mine.updated_at)}</span>}
      </div>
      <div className="status-bar">
        <input placeholder="Optional note, e.g. Staff room 2 or Back at 3 pm" value={note} onChange={(e) => setNote(e.target.value)} maxLength={200} />
        {STATES.map((s) => (
          <button key={s.value} className={`btn status-btn ${s.cls} ${mine?.status === s.value ? 'current' : ''}`} onClick={() => save(s.value)}>
            {s.value}
          </button>
        ))}
      </div>
      {error && <p className="error">{error}</p>}
    </section>
  )
}

export default function Faculty() {
  const { user } = useAuth()
  const [board, setBoard] = useState([])
  const [query, setQuery] = useState('')
  const load = useCallback(() => api('/faculty').then(setBoard), [])
  usePolling(load, 30000)

  const isStaff = user.role !== 'student'
  const mine = board.find((f) => f.faculty_id === user.user_id)
  const shown = board.filter((f) => f.name.toLowerCase().includes(query.trim().toLowerCase()))
  const counts = STATES.map((s) => [s.value, board.filter((f) => f.status === s.value).length])

  return (
    <>
      {isStaff && <MyStatus mine={mine} onSaved={load} />}
      <section className="card">
        <div className="row-between">
          <div className="counts">
            {counts.map(([label, n]) => <span key={label} className={`pill ${clsFor(label)}`}><span className="dot" />{n} {label}</span>)}
          </div>
          <div className="toolbar-actions">
            <input placeholder="Search faculty" value={query} onChange={(e) => setQuery(e.target.value)} />
            {user.role === 'admin' && <button className="btn ghost" onClick={() => download('/export/faculty', 'faculty_attendance.xlsx')}>Export attendance</button>}
          </div>
        </div>
        <div className="faculty-grid">
          {shown.map((f) => (
            <div key={f.faculty_id} className={`faculty-card ${clsFor(f.status)}`}>
              <div className="row-between">
                <strong>{f.name}</strong>
                <span className={`pill ${clsFor(f.status)}`}><span className="dot" />{f.status ?? 'Not reported'}</span>
              </div>
              <small className="muted-text">{ROLE_LABELS[f.role]}</small>
              {f.note && <p>{f.note}</p>}
              <small className="muted-text">{f.updated_at ? `Updated ${ago(f.updated_at)}` : 'No update yet'}</small>
            </div>
          ))}
        </div>
      </section>
    </>
  )
}
