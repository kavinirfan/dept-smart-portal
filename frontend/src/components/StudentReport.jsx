import { useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api'

const pct = (v, max) => (v == null ? null : Math.round((v / max) * 1000) / 10)

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="chart-tip">
      <strong>{label}</strong>
      {payload.map((p) => (
        <div key={p.dataKey}>
          <span className="swatch" style={{ background: p.color }} />
          {p.name}: {p.value == null ? 'not yet' : `${p.value}%`}
        </div>
      ))}
    </div>
  )
}

function SubjectCard({ s }) {
  const data = s.components.map((c) => ({
    name: c.name,
    you: c.absent ? 0 : pct(c.marks_obtained, c.max_marks),
    avg: pct(c.class_average, c.max_marks),
  }))
  const maxQ = Math.max(...s.components.map((c) => c.question_max.length))
  const hasAny = s.components.some((c) => c.marks_obtained != null)

  return (
    <section className="card">
      <div className="row-between">
        <h2>{s.subject.subject_code} · {s.subject.subject_name}</h2>
        <div className="internal">
          <span className="big-number">{s.internal}</span>
          <span className="muted-text"> / {s.assessed_out_of} so far · {s.internal_out_of} total internal</span>
        </div>
      </div>
      {hasAny && (
        <div className="chart viz-root" role="img" aria-label={`Score per test for ${s.subject.subject_name} compared with class average`}>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={data} barGap={2} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
              <CartesianGrid vertical={false} stroke="var(--grid)" />
              <XAxis dataKey="name" tick={{ fill: 'var(--muted)', fontSize: 12 }} axisLine={{ stroke: 'var(--border)' }} tickLine={false} />
              <YAxis domain={[0, 100]} unit="%" tick={{ fill: 'var(--muted)', fontSize: 12 }} axisLine={false} tickLine={false} />
              <Tooltip content={<ChartTooltip />} cursor={{ fill: 'var(--hover)' }} />
              <Legend
                wrapperStyle={{ fontSize: 12 }}
                itemSorter={(item) => (item.dataKey === 'you' ? 0 : 1)}
                formatter={(value) => <span style={{ color: 'var(--muted)' }}>{value}</span>}
              />
              <Bar dataKey="you" name="You" fill="var(--series-1)" radius={[4, 4, 0, 0]} maxBarSize={36} animationDuration={400} />
              <Bar dataKey="avg" name="Class average" fill="var(--series-2)" radius={[4, 4, 0, 0]} maxBarSize={36} animationDuration={400} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
      <div className="table-wrap">
        <table className="marks-table">
          <thead>
            <tr>
              <th>Test</th>
              {Array.from({ length: maxQ }, (_, i) => <th key={i}>Q{i + 1}</th>)}
              <th>Total</th>
              <th>Weighted</th>
              <th>Class avg</th>
            </tr>
          </thead>
          <tbody>
            {s.components.map((c) => (
              <tr key={c.component_id}>
                <td>{c.name} <small className="muted-text">({c.weightage}%)</small></td>
                {Array.from({ length: maxQ }, (_, i) => (
                  <td key={i}>
                    {i < c.question_max.length
                      ? c.question_marks && !c.absent
                        ? <>{c.question_marks[i] ?? '–'}<small className="muted-text">/{c.question_max[i]}</small></>
                        : '–'
                      : ''}
                  </td>
                ))}
                <td><strong>{c.absent ? 'Absent' : c.marks_obtained ?? 'Not yet'}</strong>{c.marks_obtained != null && !c.absent && <small className="muted-text">/{c.max_marks}</small>}</td>
                <td>{c.weighted ?? '–'}{c.weighted != null && <small className="muted-text">/{c.weightage}</small>}</td>
                <td>{c.class_average ?? '–'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

export default function StudentReport({ studentId }) {
  const [report, setReport] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    setReport(null)
    setError('')
    api(`/marks/student/${studentId}`).then(setReport).catch((e) => setError(e.message))
  }, [studentId])

  if (error) return <p className="card error">{error}</p>
  if (!report) return <p className="card muted-text">Loading marks…</p>
  if (!report.subjects.length) return <p className="card muted-text">No marks recorded yet.</p>
  return (
    <>
      {report.subjects.map((s) => <SubjectCard key={s.subject.subject_id} s={s} />)}
    </>
  )
}
