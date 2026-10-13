import { useEffect, useState } from 'react'
import { api } from '../api'

export default function Audit() {
  const [rows, setRows] = useState([])
  const [users, setUsers] = useState({})

  useEffect(() => {
    Promise.all([api('/audit'), api('/users')]).then(([log, us]) => {
      setRows(log)
      setUsers(Object.fromEntries(us.map((u) => [u.user_id, u.name])))
    })
  }, [])

  return (
    <section className="card">
      <h2>Recent changes</h2>
      {rows.length === 0 ? (
        <p className="muted-text">Nothing recorded yet.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead><tr><th>When</th><th>Who</th><th>Action</th><th>What</th><th>Details</th></tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.log_id}>
                  <td>{new Date(r.created_at).toLocaleString()}</td>
                  <td>{users[r.user_id] ?? '–'}</td>
                  <td>{r.action}</td>
                  <td>{r.entity}{r.entity_id ? ` #${r.entity_id}` : ''}</td>
                  <td>{r.details}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
