import { useEffect, useState } from 'react'
import { api } from '../api'
import { ROLE_LABELS, useAuth } from '../auth.jsx'

const EMPTY = { name: '', email: '', password: '', role: 'student', roll_no: '' }

export default function Users() {
  const { user: me } = useAuth()
  const [users, setUsers] = useState([])
  const [filter, setFilter] = useState('')
  const [form, setForm] = useState(EMPTY)
  const [msg, setMsg] = useState(null)

  const load = () => api('/users').then(setUsers)
  useEffect(() => { load() }, [])

  async function create(e) {
    e.preventDefault()
    setMsg(null)
    try {
      const u = await api('/users', { method: 'POST', body: { ...form, roll_no: form.roll_no || null } })
      setMsg({ ok: true, text: `Added ${u.name}.` })
      setForm(EMPTY)
      load()
    } catch (err) {
      setMsg({ ok: false, text: err.message })
    }
  }

  async function toggleActive(u) {
    try {
      await api(`/users/${u.user_id}`, { method: 'PATCH', body: { is_active: !u.is_active } })
      load()
    } catch (err) {
      setMsg({ ok: false, text: err.message })
    }
  }

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })
  const shown = users.filter((u) => !filter || u.role === filter)

  return (
    <>
      <form className="card form-grid" onSubmit={create}>
        <h2>Add a user</h2>
        <input placeholder="Full name" value={form.name} onChange={set('name')} required />
        <input placeholder="Email" type="email" value={form.email} onChange={set('email')} required />
        <input placeholder="Temporary password" value={form.password} onChange={set('password')} minLength={6} required />
        <select value={form.role} onChange={set('role')}>
          {Object.entries(ROLE_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
        {form.role === 'student' && (
          <input placeholder="Roll number" value={form.roll_no} onChange={set('roll_no')} required />
        )}
        <button className="btn">Add user</button>
        {msg && <p className={msg.ok ? 'success' : 'error'}>{msg.text}</p>}
      </form>

      <section className="card">
        <div className="row-between">
          <h2>All users ({shown.length})</h2>
          <select value={filter} onChange={(e) => setFilter(e.target.value)}>
            <option value="">All roles</option>
            {Object.entries(ROLE_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Name</th><th>Email</th><th>Role</th><th>Roll no</th><th>Status</th><th /></tr>
            </thead>
            <tbody>
              {shown.map((u) => (
                <tr key={u.user_id} className={u.is_active ? '' : 'inactive'}>
                  <td>{u.name}</td>
                  <td>{u.email}</td>
                  <td><span className={`badge ${u.role}`}>{ROLE_LABELS[u.role]}</span></td>
                  <td>{u.roll_no ?? '–'}</td>
                  <td>{u.is_active ? 'Active' : 'Disabled'}</td>
                  <td>
                    {u.user_id !== me.user_id && (
                      <button className="btn small ghost" onClick={() => toggleActive(u)}>
                        {u.is_active ? 'Disable' : 'Enable'}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  )
}
