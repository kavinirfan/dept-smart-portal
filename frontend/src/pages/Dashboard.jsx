import { useCallback, useState } from 'react'
import { Link } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ago, api, fmtDate } from '../api'
import usePolling from '../usePolling.js'

function Tile({ label, value, sub, to, tone }) {
  const body = (
    <>
      <span className="tile-label">{label}</span>
      <span className={`tile-value ${tone ?? ''}`}>{value}</span>
      {sub && <span className="muted-text tile-sub">{sub}</span>}
    </>
  )
  return to ? <Link to={to} className="card stat">{body}</Link> : <div className="card stat">{body}</div>
}

function SimpleTip({ active, payload, label, unit }) {
  if (!active || !payload?.length) return null
  const p = payload[0]
  return (
    <div className="chart-tip">
      <strong>{p.payload.full ?? label}</strong>
      <div>{p.value == null ? 'No marks yet' : `${p.value}${unit}`}</div>
      {p.payload.extra && <div className="muted-text">{p.payload.extra}</div>}
    </div>
  )
}

const axisTick = { fill: 'var(--muted)', fontSize: 12 }

export default function Dashboard() {
  const [d, setD] = useState(null)
  const load = useCallback(() => api('/dashboard').then(setD), [])
  usePolling(load, 30000)

  if (!d) return <p className="card muted-text">Loading overview…</p>

  const subjects = d.subjects.map((s) => ({
    name: s.subject_code, full: `${s.subject_code} ${s.subject_name}`, value: s.average_percent,
    extra: `${s.tests_entered} of ${s.tests_total} tests marked`,
  }))
  const labs = d.labs.map((l) => ({ name: l.lab_name, value: l.utilisation_week, extra: `${l.booked_hours_week} h booked this week` }))
  const present = (d.faculty['Available'] ?? 0) + (d.faculty['In Class'] ?? 0)
  const facultyTotal = Object.values(d.faculty).reduce((a, b) => a + b, 0)

  return (
    <>
      <p className="muted-text refresh-note">Live view · refreshes every 30 seconds · last updated {new Date(d.generated_at).toLocaleTimeString()}</p>
      <div className="stat-grid">
        <Tile label="Students" value={d.people.student ?? 0} sub={`${(d.people.teacher ?? 0) + (d.people.lab_incharge ?? 0)} staff`} to="/admin/users" />
        <Tile label="Faculty in department" value={`${present}/${facultyTotal}`} sub={`${d.faculty['On Leave'] ?? 0} on leave`} to="/faculty" />
        <Tile label="Labs free now" value={`${d.lab_status.free ?? 0}/${d.labs.length}`} sub={`${d.bookings_today} bookings today${d.lab_status.maintenance ? ` · ${d.lab_status.maintenance} in maintenance` : ''}`} to="/labs" />
        <Tile label="Students at risk" value={d.at_risk.length} sub={`internal below ${d.at_risk_threshold}%`} tone={d.at_risk.length ? 'warn' : ''} />
        <Tile label="Open opportunities" value={d.notices_active} sub={`${d.notices_closing.length} closing this week`} to="/notices" />
        <Tile label="Needs your review" value={d.chat.pending_ids + d.chat.reported} sub={`${d.chat.pending_ids} ID cards · ${d.chat.reported} reported messages`} to="/admin/verification" tone={d.chat.pending_ids + d.chat.reported ? 'warn' : ''} />
      </div>

      <div className="two-col">
        <section className="card">
          <h2>Average internal by subject</h2>
          <p className="muted-text">Class average of the internal marks assessed so far.</p>
          <div className="chart" role="img" aria-label="Average internal percentage per subject">
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={subjects} margin={{ top: 18, right: 8, left: -12, bottom: 0 }}>
                <CartesianGrid vertical={false} stroke="var(--grid)" />
                <XAxis dataKey="name" tick={axisTick} axisLine={{ stroke: 'var(--border)' }} tickLine={false} />
                <YAxis domain={[0, 100]} unit="%" tick={axisTick} axisLine={false} tickLine={false} />
                <Tooltip content={<SimpleTip unit="%" />} cursor={{ fill: 'var(--hover)' }} />
                <Bar dataKey="value" fill="var(--series-1)" radius={[4, 4, 0, 0]} maxBarSize={44} isAnimationActive={false}>
                  <LabelList dataKey="value" position="top" formatter={(v) => (v == null ? '' : `${v}%`)} style={{ fill: 'var(--muted)', fontSize: 12 }} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
        <section className="card">
          <h2>Lab use this week</h2>
          <p className="muted-text">Booked hours as a share of a 6-day, 8-hour week.</p>
          <div className="chart" role="img" aria-label="Lab utilisation this week">
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={labs} layout="vertical" margin={{ top: 4, right: 40, left: 8, bottom: 0 }}>
                <CartesianGrid horizontal={false} stroke="var(--grid)" />
                <XAxis type="number" domain={[0, 100]} unit="%" tick={axisTick} axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey="name" width={120} tick={axisTick} axisLine={{ stroke: 'var(--border)' }} tickLine={false} />
                <Tooltip content={<SimpleTip unit="%" />} cursor={{ fill: 'var(--hover)' }} />
                <Bar dataKey="value" fill="var(--series-1)" radius={[0, 4, 4, 0]} maxBarSize={28} isAnimationActive={false}>
                  <LabelList dataKey="value" position="right" formatter={(v) => `${v}%`} style={{ fill: 'var(--muted)', fontSize: 12 }} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      </div>

      <div className="two-col">
        <section className="card">
          <h2>Students needing attention</h2>
          {d.at_risk.length === 0 ? (
            <p className="muted-text">Nobody is below {d.at_risk_threshold}% in any subject.</p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead><tr><th>Roll no</th><th>Name</th><th>Subject</th><th>Internal so far</th></tr></thead>
                <tbody>
                  {d.at_risk.map((r) => (
                    <tr key={`${r.student_id}-${r.subject_code}`}>
                      <td>{r.roll_no}</td><td>{r.name}</td><td>{r.subject_code}</td>
                      <td><span className="pill busy">{r.percent}%</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
        <section className="card">
          <h2>Labs and opportunities</h2>
          <ul className="plain-list">
            {d.labs.map((l) => (
              <li key={l.lab_id} className="row-between">
                <span>{l.lab_name}</span>
                <span className={`pill ${l.status === 'free' ? 'ok' : l.status === 'occupied' ? 'busy' : 'off'}`}><span className="dot" />{l.status[0].toUpperCase() + l.status.slice(1)}</span>
              </li>
            ))}
          </ul>
          <h3 className="sub-head">Closing within a week</h3>
          {d.notices_closing.length === 0 ? <p className="muted-text">None.</p> : (
            <ul className="plain-list">
              {d.notices_closing.map((n) => (
                <li key={n.notice_id} className="row-between"><span>{n.title} · {n.company}</span><small className="muted-text">{fmtDate(n.deadline)}</small></li>
              ))}
            </ul>
          )}
          <h3 className="sub-head">Campus chat</h3>
          <p className="muted-text">{d.chat.messages_today} messages today · {d.chat.online} online now</p>
        </section>
      </div>

      <section className="card">
        <div className="row-between"><h2>Recent activity</h2><Link to="/admin/audit" className="link-btn">Full audit log</Link></div>
        {d.recent.length === 0 && <p className="muted-text">No changes recorded yet.</p>}
        <ul className="plain-list activity">
          {d.recent.map((r, i) => (
            <li key={i}>
              <strong>{r.who ?? 'System'}</strong> {r.action.replace('_', ' ')} {r.entity.replace(/_/g, ' ')}
              {r.details ? <span className="muted-text"> · {r.details}</span> : null}
              <small className="muted-text"> · {ago(r.when)}</small>
            </li>
          ))}
        </ul>
      </section>
    </>
  )
}
