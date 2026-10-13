import { useCallback, useEffect, useState } from 'react'
import { api, download, fmtDate, todayISO } from '../api'
import { ROLE_LABELS, useAuth } from '../auth.jsx'

const EMPTY = { title: '', company: '', type: 'internship', deadline: '', link: '', description: '' }

const daysLeft = (d) => Math.ceil((new Date(d + 'T23:59:59') - Date.now()) / 86400000)

export default function Notices() {
  const { user } = useAuth()
  const [notices, setNotices] = useState([])
  const [filters, setFilters] = useState({ type: '', q: '', expired: false })
  const [posting, setPosting] = useState(false)
  const [form, setForm] = useState(EMPTY)
  const [msg, setMsg] = useState(null)

  const load = useCallback(() => {
    const p = new URLSearchParams()
    if (filters.type) p.set('type', filters.type)
    if (filters.q.trim()) p.set('q', filters.q.trim())
    if (filters.expired) p.set('include_expired', 'true')
    return api(`/notices?${p}`).then(setNotices)
  }, [filters])
  useEffect(() => {
    const t = setTimeout(load, 200)
    return () => clearTimeout(t)
  }, [load])

  async function post(e) {
    e.preventDefault()
    setMsg(null)
    try {
      await api('/notices', { method: 'POST', body: { ...form, deadline: form.deadline || null, link: form.link || null } })
      setForm(EMPTY)
      setPosting(false)
      setMsg({ ok: true, text: 'Notice posted.' })
      load()
    } catch (err) {
      setMsg({ ok: false, text: err.message })
    }
  }

  async function remove(n) {
    if (!window.confirm(`Remove "${n.title}"?`)) return
    await api(`/notices/${n.notice_id}`, { method: 'DELETE' })
    load()
  }

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  return (
    <>
      <section className="card toolbar">
        <input placeholder="Search title, company or description" value={filters.q} onChange={(e) => setFilters({ ...filters, q: e.target.value })} />
        <select value={filters.type} onChange={(e) => setFilters({ ...filters, type: e.target.value })}>
          <option value="">Jobs and internships</option>
          <option value="job">Jobs only</option>
          <option value="internship">Internships only</option>
        </select>
        <label className="check"><input type="checkbox" checked={filters.expired} onChange={(e) => setFilters({ ...filters, expired: e.target.checked })} /> Show expired</label>
        <div className="toolbar-actions">
          <button className="btn ghost" onClick={() => download('/export/notices', 'notices.xlsx')}>Export Excel</button>
          <button className="btn" onClick={() => setPosting(!posting)}>{posting ? 'Close' : 'Post an opening'}</button>
        </div>
      </section>

      {msg && <p className={`card ${msg.ok ? 'success' : 'error'}`}>{msg.text}</p>}

      {posting && (
        <form className="card form-grid" onSubmit={post}>
          <h2>Post an opening</h2>
          <div className="pair">
            <input placeholder="Title (e.g. Backend Intern)" value={form.title} onChange={set('title')} required />
            <input placeholder="Company / organisation" value={form.company} onChange={set('company')} required />
          </div>
          <div className="pair">
            <select value={form.type} onChange={set('type')}>
              <option value="internship">Internship</option>
              <option value="job">Job</option>
            </select>
            <label>Apply by<input type="date" min={todayISO()} value={form.deadline} onChange={set('deadline')} /></label>
          </div>
          <input type="url" placeholder="Link to apply (https://…)" value={form.link} onChange={set('link')} />
          <textarea rows={4} placeholder="Details: eligibility, stipend, how to apply" value={form.description} onChange={set('description')} required />
          <button className="btn">Post</button>
        </form>
      )}

      {notices.length === 0 ? (
        <p className="card muted-text">No openings match.</p>
      ) : (
        <div className="notice-grid">
          {notices.map((n) => {
            const left = n.deadline ? daysLeft(n.deadline) : null
            return (
              <article key={n.notice_id} className={`card notice ${n.expired ? 'expired' : ''}`}>
                <div className="row-between">
                  <span className={`badge ${n.type === 'job' ? 'teacher' : 'student'}`}>{n.type === 'job' ? 'Job' : 'Internship'}</span>
                  {n.deadline && (
                    <span className={`deadline ${!n.expired && left <= 7 ? 'soon-due' : ''}`}>
                      {n.expired ? 'Closed' : left === 0 ? 'Closes today' : `${left} day${left === 1 ? '' : 's'} left`}
                    </span>
                  )}
                </div>
                <h3>{n.title}</h3>
                <p className="company">{n.company}</p>
                <p className="desc">{n.description}</p>
                <div className="row-between notice-foot">
                  <small className="muted-text">
                    {n.posted_by_name} ({ROLE_LABELS[n.posted_by_role]}) · {fmtDate(n.posted_on)}
                    {n.deadline && ` · apply by ${fmtDate(n.deadline)}`}
                  </small>
                  <div className="toolbar-actions">
                    {n.link && <a className="btn small" href={n.link} target="_blank" rel="noreferrer">Apply</a>}
                    {(user.role === 'admin' || n.posted_by === user.user_id) && (
                      <button className="btn small ghost" onClick={() => remove(n)}>Remove</button>
                    )}
                  </div>
                </div>
              </article>
            )
          })}
        </div>
      )}
    </>
  )
}
