import { useEffect, useMemo, useState } from 'react'
import { api, download } from '../api'
import { useAuth } from '../auth.jsx'
import StudentReport from '../components/StudentReport.jsx'

function NewComponent({ subjectId, onCreated }) {
  const [form, setForm] = useState({ name: '', questions: '10,10,10,10,10', weightage: 15 })
  const [error, setError] = useState('')

  async function submit(e) {
    e.preventDefault()
    setError('')
    const question_max = form.questions.split(',').map((q) => Number(q.trim())).filter((q) => !Number.isNaN(q))
    try {
      const c = await api('/marks/components', {
        method: 'POST',
        body: { subject_id: subjectId, name: form.name, question_max, weightage: Number(form.weightage) },
      })
      onCreated(c)
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <form className="inline-form" onSubmit={submit}>
      <input placeholder="Test name (e.g. CAT-3)" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
      <input placeholder="Max per question, comma separated" value={form.questions} onChange={(e) => setForm({ ...form, questions: e.target.value })} required title="Max marks per question, e.g. 10,10,15" />
      <input type="number" min="1" max="100" value={form.weightage} onChange={(e) => setForm({ ...form, weightage: e.target.value })} title="Weightage (%)" />
      <button className="btn">Add test</button>
      {error && <p className="error">{error}</p>}
    </form>
  )
}

function MarkEntry() {
  const [subjects, setSubjects] = useState([])
  const [subjectId, setSubjectId] = useState('')
  const [components, setComponents] = useState([])
  const [componentId, setComponentId] = useState('')
  const [rows, setRows] = useState([])
  const [dirty, setDirty] = useState(false)
  const [adding, setAdding] = useState(false)
  const [msg, setMsg] = useState(null)

  useEffect(() => {
    api('/marks/my-subjects').then((s) => {
      setSubjects(s)
      if (s.length) setSubjectId(String(s[0].subject_id))
    })
  }, [])

  useEffect(() => {
    if (!subjectId) return
    api(`/marks/components?subject_id=${subjectId}`).then((c) => {
      setComponents(c)
      setComponentId(c.length ? String(c[0].component_id) : '')
    })
  }, [subjectId])

  useEffect(() => {
    setRows([])
    setDirty(false)
    setMsg(null)
    if (componentId) api(`/marks/sheet/${componentId}`).then(setRows)
  }, [componentId])

  const comp = components.find((c) => String(c.component_id) === componentId)

  function setQ(studentIdx, qIdx, value) {
    setRows((rs) => rs.map((r, i) => {
      if (i !== studentIdx) return r
      const qm = r.question_marks ? [...r.question_marks] : Array(comp.question_max.length).fill(null)
      qm[qIdx] = value === '' ? null : Number(value)
      return { ...r, question_marks: qm }
    }))
    setDirty(true)
  }

  function setAbsent(idx, absent) {
    setRows((rs) => rs.map((r, i) => (i === idx ? { ...r, absent } : r)))
    setDirty(true)
  }

  async function save() {
    setMsg(null)
    try {
      const entries = rows
        .filter((r) => r.absent || r.question_marks)
        .map((r) => ({ student_id: r.student_id, absent: r.absent, question_marks: r.question_marks ?? Array(comp.question_max.length).fill(null) }))
      const { saved } = await api(`/marks/sheet/${componentId}`, { method: 'PUT', body: entries })
      setMsg({ ok: true, text: saved ? `Saved ${saved} student${saved === 1 ? '' : 's'}.` : 'No changes to save.' })
      setDirty(false)
      setRows(await api(`/marks/sheet/${componentId}`))
    } catch (err) {
      setMsg({ ok: false, text: err.message })
    }
  }

  if (!subjects.length) {
    return <p className="card muted-text">You don't hold a marks credential for any subject yet. Ask the HOD to grant one.</p>
  }

  const total = (r) => (r.absent ? 'AB' : r.question_marks ? r.question_marks.reduce((a, b) => a + (b ?? 0), 0) : '–')
  const invalid = (v, max) => v != null && (v < 0 || v > max)

  return (
    <section className="card">
      <div className="toolbar">
        <label>Subject
          <select value={subjectId} onChange={(e) => setSubjectId(e.target.value)}>
            {subjects.map((s) => <option key={s.subject_id} value={s.subject_id}>{s.subject_code} {s.subject_name}</option>)}
          </select>
        </label>
        <label>Test
          <select value={componentId} onChange={(e) => setComponentId(e.target.value)}>
            {components.map((c) => <option key={c.component_id} value={c.component_id}>{c.name} ({c.max_marks} marks, {c.weightage}%)</option>)}
          </select>
        </label>
        <div className="toolbar-actions">
          <button className="btn ghost" onClick={() => setAdding(!adding)}>{adding ? 'Close' : 'New test'}</button>
          <button className="btn ghost" onClick={() => download(`/export/marks?subject_id=${subjectId}`, 'marks.xlsx')}>Export Excel</button>
        </div>
      </div>
      {adding && (
        <NewComponent subjectId={Number(subjectId)} onCreated={(c) => {
          setComponents((cs) => [...cs, c])
          setComponentId(String(c.component_id))
          setAdding(false)
        }} />
      )}
      {comp && (
        <>
          <div className="table-wrap">
            <table className="entry-table">
              <thead>
                <tr>
                  <th>Roll no</th><th>Name</th>
                  {comp.question_max.map((m, i) => <th key={i}>Q{i + 1}<small>/{m}</small></th>)}
                  <th>Total</th><th>Absent</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, si) => (
                  <tr key={r.student_id} className={r.absent ? 'inactive' : ''}>
                    <td>{r.roll_no}</td>
                    <td>{r.name}</td>
                    {comp.question_max.map((m, qi) => {
                      const v = r.question_marks?.[qi] ?? null
                      return (
                        <td key={qi}>
                          <input
                            className={`cell ${invalid(v, m) ? 'bad' : ''}`}
                            type="number" step="0.5" min="0" max={m} disabled={r.absent}
                            value={v ?? ''} onChange={(e) => setQ(si, qi, e.target.value)}
                            aria-label={`${r.name} Q${qi + 1}`}
                          />
                        </td>
                      )
                    })}
                    <td><strong>{total(r)}</strong></td>
                    <td><input type="checkbox" checked={r.absent} onChange={(e) => setAbsent(si, e.target.checked)} aria-label={`${r.name} absent`} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="row-between save-row">
            {msg ? <p className={msg.ok ? 'success' : 'error'}>{msg.text}</p> : <span className="muted-text">{dirty ? 'Unsaved changes' : 'Every save is recorded in the audit log.'}</span>}
            <button className="btn" onClick={save} disabled={!dirty}>Save marks</button>
          </div>
        </>
      )}
    </section>
  )
}

function StudentLookup() {
  const [students, setStudents] = useState([])
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState(null)

  useEffect(() => { api('/users?role=student').then(setStudents) }, [])
  const matches = useMemo(() => {
    const q = query.trim().toLowerCase()
    return q ? students.filter((s) => s.name.toLowerCase().includes(q) || (s.roll_no ?? '').toLowerCase().includes(q)) : students
  }, [students, query])

  return (
    <>
      <section className="card">
        <input placeholder="Search by name or roll number" value={query} onChange={(e) => setQuery(e.target.value)} />
        <div className="chips lookup">
          {matches.slice(0, 30).map((s) => (
            <button key={s.user_id} className={`chip ${selected?.user_id === s.user_id ? 'selected' : ''}`} onClick={() => setSelected(s)}>
              {s.roll_no} · {s.name}
            </button>
          ))}
        </div>
      </section>
      {selected && <StudentReport studentId={selected.user_id} />}
    </>
  )
}

export default function Marks() {
  const { user } = useAuth()
  const [tab, setTab] = useState('entry')

  if (user.role === 'student') return <StudentReport studentId={user.user_id} />

  return (
    <>
      <div className="tabs">
        <button className={tab === 'entry' ? 'active' : ''} onClick={() => setTab('entry')}>Enter marks</button>
        <button className={tab === 'lookup' ? 'active' : ''} onClick={() => setTab('lookup')}>Look up a student</button>
      </div>
      {tab === 'entry' ? <MarkEntry /> : <StudentLookup />}
    </>
  )
}
