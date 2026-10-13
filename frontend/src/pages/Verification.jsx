import { useCallback, useEffect, useState } from 'react'
import { ago, api, blobUrl, fmtDate } from '../api'
import { ROLE_LABELS } from '../auth.jsx'

function IdCardImage({ id }) {
  const [src, setSrc] = useState(null)
  useEffect(() => {
    let url
    blobUrl(`/chat/id-cards/${id}/image`).then((u) => { url = u; setSrc(u) }).catch(() => setSrc(''))
    return () => url && URL.revokeObjectURL(url)
  }, [id])
  if (src === null) return <div className="id-img placeholder">Loading…</div>
  if (!src) return <div className="id-img placeholder">Image missing</div>
  return <a href={src} target="_blank" rel="noreferrer"><img className="id-img" src={src} alt="Uploaded ID card" /></a>
}

function Registration({ r, onDone }) {
  const [note, setNote] = useState('')
  const [error, setError] = useState('')
  async function review(approve) {
    setError('')
    try {
      await api(`/chat/id-cards/${r.registration_id}/review`, { method: 'POST', body: { approve, note } })
      onDone()
    } catch (err) {
      setError(err.message)
    }
  }
  return (
    <article className="card id-review">
      <IdCardImage id={r.registration_id} />
      <div className="id-info">
        <h3>{r.name}</h3>
        <dl className="details">
          <dt>Role</dt><dd>{ROLE_LABELS[r.role]}</dd>
          {r.roll_no && (<><dt>Roll no on record</dt><dd>{r.roll_no}</dd></>)}
          <dt>ID number given</dt><dd>{r.id_number} {r.roll_no && r.roll_no !== r.id_number && <span className="pill busy">does not match</span>}</dd>
          <dt>Email</dt><dd>{r.email}</dd>
          <dt>Submitted</dt><dd>{ago(r.submitted_on)}</dd>
        </dl>
        <input placeholder="Reason (required to reject)" value={note} onChange={(e) => setNote(e.target.value)} maxLength={200} />
        <div className="toolbar-actions left">
          <button className="btn" onClick={() => review(true)}>Approve</button>
          <button className="btn ghost danger" onClick={() => review(false)}>Reject</button>
        </div>
        {error && <p className="error">{error}</p>}
      </div>
    </article>
  )
}

export default function Verification() {
  const [pending, setPending] = useState([])
  const [history, setHistory] = useState([])
  const [reported, setReported] = useState([])

  const load = useCallback(() => {
    api('/chat/id-cards?status=pending').then(setPending)
    api('/chat/id-cards').then((all) => setHistory(all.filter((r) => r.status !== 'pending').slice(0, 20)))
    api('/chat/reported').then(setReported)
  }, [])
  useEffect(() => { load() }, [load])

  async function moderate(m, hide) {
    await api(`/chat/messages/${m.message_id}/moderate`, { method: 'POST', body: { hide } })
    load()
  }

  return (
    <>
      <section>
        <h2 className="section-title">ID cards waiting for approval ({pending.length})</h2>
        {pending.length === 0 ? <p className="card muted-text">Nothing to review.</p> : (
          <div className="id-grid">{pending.map((r) => <Registration key={r.registration_id} r={r} onDone={load} />)}</div>
        )}
      </section>

      <section className="card">
        <h2>Reported chat messages ({reported.length})</h2>
        {reported.length === 0 ? <p className="muted-text">No open reports.</p> : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>From</th><th>Message</th><th>Sent</th><th /></tr></thead>
              <tbody>
                {reported.map((m) => (
                  <tr key={m.message_id}>
                    <td>{m.sender_name}</td>
                    <td>{m.text}</td>
                    <td className="nowrap">{ago(m.sent_at)}</td>
                    <td className="nowrap">
                      <button className="btn small danger" onClick={() => moderate(m, true)}>Remove message</button>{' '}
                      <button className="btn small ghost" onClick={() => moderate(m, false)}>Dismiss report</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="card">
        <h2>Recently reviewed</h2>
        {history.length === 0 ? <p className="muted-text">None yet.</p> : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Name</th><th>ID number</th><th>Decision</th><th>Note</th><th>When</th></tr></thead>
              <tbody>
                {history.map((r) => (
                  <tr key={r.registration_id}>
                    <td>{r.name}</td><td>{r.id_number}</td>
                    <td><span className={`pill ${r.status === 'approved' ? 'ok' : 'off'}`}>{r.status}</span></td>
                    <td>{r.review_note ?? '–'}</td>
                    <td>{r.reviewed_on ? fmtDate(r.reviewed_on) : '–'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  )
}
