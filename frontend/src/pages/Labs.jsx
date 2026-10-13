import { useCallback, useEffect, useState } from 'react'
import { api, download, fmtTime, ago, todayISO } from '../api'
import { useAuth } from '../auth.jsx'
import usePolling from '../usePolling.js'

const STATUS = {
  free: { label: 'Free', cls: 'ok' },
  occupied: { label: 'Occupied', cls: 'busy' },
  maintenance: { label: 'Maintenance', cls: 'off' },
}

// What a viewer should believe right now: maintenance wins, then a live booking, then the in-charge's flag.
const effective = (lab) => (lab.current_status === 'maintenance' ? 'maintenance' : lab.current_booking ? 'occupied' : lab.current_status)

function LabCard({ lab, canSetStatus, onStatus }) {
  const st = STATUS[effective(lab)]
  return (
    <section className="card lab-card">
      <div className="row-between">
        <h3>{lab.lab_name}</h3>
        <span className={`pill ${st.cls}`}><span className="dot" />{st.label}</span>
      </div>
      <p className="muted-text">{lab.capacity} seats · In-charge: {lab.incharge_name ?? '–'}</p>
      {lab.current_booking ? (
        <p>In use by <strong>{lab.current_booking.booked_by_name}</strong> until {fmtTime(lab.current_booking.end_time)} · {lab.current_booking.purpose}</p>
      ) : lab.next_booking ? (
        <p>Next: {fmtTime(lab.next_booking.start_time)}–{fmtTime(lab.next_booking.end_time)} · {lab.next_booking.booked_by_name}</p>
      ) : (
        <p className="muted-text">No more bookings today.</p>
      )}
      {canSetStatus && (
        <div className="seg">
          {Object.entries(STATUS).map(([k, v]) => (
            <button key={k} className={lab.current_status === k ? 'active' : ''} onClick={() => onStatus(lab, k)}>{v.label}</button>
          ))}
          <small className="muted-text">updated {ago(lab.status_updated_at)}</small>
        </div>
      )}
    </section>
  )
}

export default function Labs() {
  const { user } = useAuth()
  const [labs, setLabs] = useState([])
  const [day, setDay] = useState(todayISO())
  const [bookings, setBookings] = useState([])
  const [form, setForm] = useState({ lab_id: '', date: todayISO(), start: '', end: '', purpose: '' })
  const [msg, setMsg] = useState(null)

  const load = useCallback(async () => {
    const [l, b] = await Promise.all([api('/labs'), api(`/labs/bookings?day=${day}`)])
    setLabs(l)
    setBookings(b)
  }, [day])
  usePolling(load, 20000)

  useEffect(() => {
    if (!form.lab_id && labs.length) setForm((f) => ({ ...f, lab_id: String(labs[0].lab_id) }))
  }, [labs, form.lab_id])

  const canSetStatus = (lab) => user.role === 'admin' || (user.role === 'lab_incharge' && lab.incharge_id === user.user_id)
  const canCancel = (b) => user.role === 'admin' || b.booked_by === user.user_id || labs.find((l) => l.lab_id === b.lab_id)?.incharge_id === user.user_id

  async function setStatus(lab, status) {
    try {
      await api(`/labs/${lab.lab_id}/status`, { method: 'PATCH', body: { status } })
      load()
    } catch (err) {
      setMsg({ ok: false, text: err.message })
    }
  }

  async function book(e) {
    e.preventDefault()
    setMsg(null)
    try {
      const b = await api('/labs/bookings', {
        method: 'POST',
        body: { lab_id: Number(form.lab_id), start_time: `${form.date}T${form.start}`, end_time: `${form.date}T${form.end}`, purpose: form.purpose },
      })
      setMsg({ ok: true, text: `Booked ${b.lab_name}, ${fmtTime(b.start_time)}–${fmtTime(b.end_time)}.` })
      setForm({ ...form, start: '', end: '', purpose: '' })
      setDay(form.date)
      load()
    } catch (err) {
      setMsg({ ok: false, text: err.message })
    }
  }

  async function cancel(b) {
    if (!window.confirm(`Cancel ${b.lab_name} ${fmtTime(b.start_time)}–${fmtTime(b.end_time)}?`)) return
    try {
      await api(`/labs/bookings/${b.booking_id}`, { method: 'DELETE' })
      load()
    } catch (err) {
      setMsg({ ok: false, text: err.message })
    }
  }

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  return (
    <>
      <div className="lab-grid">
        {labs.map((lab) => <LabCard key={lab.lab_id} lab={lab} canSetStatus={canSetStatus(lab)} onStatus={setStatus} />)}
      </div>

      <div className="two-col wide-left">
        <section className="card">
          <div className="row-between">
            <h2>Schedule</h2>
            <div className="toolbar-actions">
              <input type="date" value={day} onChange={(e) => setDay(e.target.value)} />
              <button className="btn ghost" onClick={() => download('/export/labs', 'lab_bookings.xlsx')}>Export Excel</button>
            </div>
          </div>
          {bookings.length === 0 ? (
            <p className="muted-text">No bookings on this day.</p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead><tr><th>Time</th><th>Lab</th><th>Booked by</th><th>Purpose</th><th /></tr></thead>
                <tbody>
                  {bookings.map((b) => (
                    <tr key={b.booking_id}>
                      <td className="nowrap">{fmtTime(b.start_time)}–{fmtTime(b.end_time)}</td>
                      <td>{b.lab_name}</td>
                      <td>{b.booked_by_name}</td>
                      <td>{b.purpose}</td>
                      <td>{canCancel(b) && <button className="btn small ghost" onClick={() => cancel(b)}>Cancel</button>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <form className="card form-grid" onSubmit={book}>
          <h2>Book a lab</h2>
          <p className="muted-text">First come, first served: if someone already holds an overlapping slot, the booking is refused and you'll see who has it.</p>
          <select value={form.lab_id} onChange={set('lab_id')} required>
            {labs.map((l) => <option key={l.lab_id} value={l.lab_id} disabled={l.current_status === 'maintenance'}>{l.lab_name}{l.current_status === 'maintenance' ? ' (maintenance)' : ''}</option>)}
          </select>
          <input type="date" value={form.date} min={todayISO()} onChange={set('date')} required />
          <div className="pair">
            <label>From<input type="time" value={form.start} onChange={set('start')} required /></label>
            <label>To<input type="time" value={form.end} onChange={set('end')} required /></label>
          </div>
          <input placeholder="Purpose (e.g. extra DBMS session)" value={form.purpose} onChange={set('purpose')} maxLength={200} required />
          <button className="btn">Book</button>
          {msg && <p className={msg.ok ? 'success' : 'error'}>{msg.text}</p>}
        </form>
      </div>
    </>
  )
}
