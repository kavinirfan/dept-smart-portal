import { useEffect, useState } from 'react'
import { api } from '../api'

export default function Subjects() {
  const [subjects, setSubjects] = useState([])
  const [teachers, setTeachers] = useState([])
  const [creds, setCreds] = useState([])
  const [subjectForm, setSubjectForm] = useState({ subject_code: '', subject_name: '', semester: 5 })
  const [grant, setGrant] = useState({ user_id: '', subject_id: '' })
  const [msg, setMsg] = useState(null)

  const load = () =>
    Promise.all([api('/subjects'), api('/users?role=teacher'), api('/credentials')]).then(([s, t, c]) => {
      setSubjects(s)
      setTeachers(t)
      setCreds(c)
    })
  useEffect(() => { load() }, [])

  const run = async (fn, ok) => {
    setMsg(null)
    try {
      await fn()
      setMsg({ ok: true, text: ok })
      load()
    } catch (err) {
      setMsg({ ok: false, text: err.message })
    }
  }

  const addSubject = (e) => {
    e.preventDefault()
    run(async () => {
      await api('/subjects', { method: 'POST', body: { ...subjectForm, semester: Number(subjectForm.semester) } })
      setSubjectForm({ subject_code: '', subject_name: '', semester: 5 })
    }, 'Subject added.')
  }

  const addGrant = (e) => {
    e.preventDefault()
    run(() => api('/credentials', { method: 'POST', body: { user_id: Number(grant.user_id), subject_id: Number(grant.subject_id) } }), 'Credential granted.')
  }

  const revoke = (id) => run(() => api(`/credentials/${id}`, { method: 'DELETE' }), 'Credential revoked.')
  const teacherName = (id) => teachers.find((t) => t.user_id === id)?.name ?? `User ${id}`

  return (
    <>
      {msg && <p className={`card ${msg.ok ? 'success' : 'error'}`}>{msg.text}</p>}
      <div className="two-col">
        <form className="card form-grid" onSubmit={addSubject}>
          <h2>Add a subject</h2>
          <input placeholder="Code (e.g. CS505)" value={subjectForm.subject_code} onChange={(e) => setSubjectForm({ ...subjectForm, subject_code: e.target.value })} required />
          <input placeholder="Subject name" value={subjectForm.subject_name} onChange={(e) => setSubjectForm({ ...subjectForm, subject_name: e.target.value })} required />
          <input type="number" min={1} max={10} value={subjectForm.semester} onChange={(e) => setSubjectForm({ ...subjectForm, semester: e.target.value })} />
          <button className="btn">Add subject</button>
        </form>
        <form className="card form-grid" onSubmit={addGrant}>
          <h2>Grant marks credential</h2>
          <p className="muted-text">Only teachers holding a subject's credential can enter or confirm its marks.</p>
          <select value={grant.user_id} onChange={(e) => setGrant({ ...grant, user_id: e.target.value })} required>
            <option value="">Choose teacher…</option>
            {teachers.map((t) => <option key={t.user_id} value={t.user_id}>{t.name}</option>)}
          </select>
          <select value={grant.subject_id} onChange={(e) => setGrant({ ...grant, subject_id: e.target.value })} required>
            <option value="">Choose subject…</option>
            {subjects.map((s) => <option key={s.subject_id} value={s.subject_id}>{s.subject_code} {s.subject_name}</option>)}
          </select>
          <button className="btn">Grant</button>
        </form>
      </div>

      <section className="card">
        <h2>Subjects</h2>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Code</th><th>Name</th><th>Sem</th><th>Teachers with credential</th></tr></thead>
            <tbody>
              {subjects.map((s) => (
                <tr key={s.subject_id}>
                  <td>{s.subject_code}</td>
                  <td>{s.subject_name}</td>
                  <td>{s.semester}</td>
                  <td>
                    {creds.filter((c) => c.subject_id === s.subject_id).map((c) => (
                      <span key={c.credential_id} className="chip static">
                        {teacherName(c.user_id)}
                        <button className="x" title="Revoke" onClick={() => revoke(c.credential_id)}>×</button>
                      </span>
                    ))}
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
