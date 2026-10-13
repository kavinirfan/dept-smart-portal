import { useEffect, useState } from 'react'
import { api } from '../api'
import { ROLE_LABELS, useAuth } from '../auth.jsx'

export default function Profile() {
  const { user } = useAuth()
  const [creds, setCreds] = useState([])
  const [pw, setPw] = useState({ current_password: '', new_password: '' })
  const [msg, setMsg] = useState(null)

  useEffect(() => {
    if (user.role === 'teacher') api('/credentials').then(setCreds)
  }, [user.role])

  async function change(e) {
    e.preventDefault()
    setMsg(null)
    try {
      await api('/auth/change-password', { method: 'POST', body: pw })
      setPw({ current_password: '', new_password: '' })
      setMsg({ ok: true, text: 'Password changed.' })
    } catch (err) {
      setMsg({ ok: false, text: err.message })
    }
  }

  return (
    <div className="two-col">
      <section className="card">
        <h2>My details</h2>
        <dl className="details">
          <dt>Name</dt><dd>{user.name}</dd>
          <dt>Email</dt><dd>{user.email}</dd>
          <dt>Role</dt><dd>{ROLE_LABELS[user.role]}</dd>
          {user.roll_no && (<><dt>Roll no</dt><dd>{user.roll_no}</dd></>)}
          <dt>Department</dt><dd>{user.department}</dd>
          {user.role === 'teacher' && (
            <>
              <dt>Marks credentials</dt>
              <dd>{creds.length ? creds.map((c) => c.subject.subject_code).join(', ') : 'None yet'}</dd>
            </>
          )}
        </dl>
      </section>
      <form className="card form-grid" onSubmit={change}>
        <h2>Change password</h2>
        <input type="password" placeholder="Current password" value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} required />
        <input type="password" placeholder="New password (6+ characters)" minLength={6} value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} required />
        <button className="btn">Update password</button>
        {msg && <p className={msg.ok ? 'success' : 'error'}>{msg.text}</p>}
      </form>
    </div>
  )
}
