import { useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { ROLE_LABELS, useAuth } from '../auth.jsx'
import { navFor } from '../nav.js'
import NotificationBell from './NotificationBell.jsx'

export default function Layout() {
  const { user, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const location = useLocation()
  const items = navFor(user.role)
  const current = items.find((i) => i.path === location.pathname)

  return (
    <div className="shell">
      <aside className={`sidebar ${open ? 'open' : ''}`}>
        <div className="brand">
          <span className="brand-mark">DSP</span>
          <span>Department Smart Portal</span>
        </div>
        <nav>
          {items.map((item) => (
            <NavLink key={item.path} to={item.path} end onClick={() => setOpen(false)}>
              {item.label}
              {!item.ready && <span className="soon">soon</span>}
            </NavLink>
          ))}
        </nav>
      </aside>
      {open && <div className="scrim" onClick={() => setOpen(false)} />}
      <div className="main">
        <header className="topbar">
          <button className="menu-btn" onClick={() => setOpen(true)} aria-label="Open menu">☰</button>
          <h1>{current?.label ?? 'Portal'}</h1>
          <NotificationBell />
          <div className="who">
            <div>
              <strong>{user.name}</strong>
              <small>{ROLE_LABELS[user.role]}{user.roll_no ? ` · ${user.roll_no}` : ''}</small>
            </div>
            <button className="btn ghost" onClick={logout}>Log out</button>
          </div>
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
