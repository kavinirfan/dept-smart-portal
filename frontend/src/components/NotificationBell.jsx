import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ago, api } from '../api'
import usePolling from '../usePolling.js'

export default function NotificationBell() {
  const [data, setData] = useState({ unread: 0, items: [] })
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  const navigate = useNavigate()

  const load = useCallback(() => api('/notifications').then(setData).catch(() => {}), [])
  usePolling(load, 20000)

  useEffect(() => {
    if (!open) return
    const close = (e) => ref.current && !ref.current.contains(e.target) && setOpen(false)
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  async function openItem(n) {
    if (!n.is_read) await api(`/notifications/${n.notification_id}/read`, { method: 'POST' })
    setOpen(false)
    load()
    if (n.link) navigate(n.link)
  }

  async function readAll() {
    await api('/notifications/read-all', { method: 'POST' })
    load()
  }

  return (
    <div className="bell-wrap" ref={ref}>
      <button className="bell" onClick={() => setOpen(!open)} aria-label={`Notifications, ${data.unread} unread`}>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.73 21a2 2 0 0 1-3.46 0" />
        </svg>
        {data.unread > 0 && <span className="bell-count">{data.unread > 9 ? '9+' : data.unread}</span>}
      </button>
      {open && (
        <div className="bell-panel">
          <div className="row-between">
            <strong>Notifications</strong>
            {data.unread > 0 && <button className="link-btn" onClick={readAll}>Mark all read</button>}
          </div>
          {data.items.length === 0 ? (
            <p className="muted-text">Nothing yet.</p>
          ) : (
            <ul>
              {data.items.map((n) => (
                <li key={n.notification_id} className={n.is_read ? '' : 'unread'}>
                  <button onClick={() => openItem(n)}>
                    <span>{n.message}</span>
                    <small className="muted-text">{ago(n.created_at)}</small>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
