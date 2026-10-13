import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './auth.jsx'
import Layout from './components/Layout.jsx'
import { NAV } from './nav.js'
import Audit from './pages/Audit.jsx'
import Chat from './pages/Chat.jsx'
import ComingSoon from './pages/ComingSoon.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Faculty from './pages/Faculty.jsx'
import Home from './pages/Home.jsx'
import Labs from './pages/Labs.jsx'
import Login from './pages/Login.jsx'
import Marks from './pages/Marks.jsx'
import Notices from './pages/Notices.jsx'
import Profile from './pages/Profile.jsx'
import Subjects from './pages/Subjects.jsx'
import Users from './pages/Users.jsx'
import Verification from './pages/Verification.jsx'

const PAGES = {
  '/': Home,
  '/marks': Marks,
  '/labs': Labs,
  '/faculty': Faculty,
  '/notices': Notices,
  '/chat': Chat,
  '/dashboard': Dashboard,
  '/admin/verification': Verification,
  '/admin/users': Users,
  '/admin/subjects': Subjects,
  '/admin/audit': Audit,
  '/profile': Profile,
}

function RequireRole({ roles, children }) {
  const { user } = useAuth()
  if (!roles.includes(user.role)) return <Navigate to="/" replace />
  return children
}

export default function App() {
  const { user, loading } = useAuth()
  if (loading) return <div className="center-screen">Loading…</div>
  if (!user) {
    return (
      <Routes>
        <Route path="*" element={<Login />} />
      </Routes>
    )
  }
  return (
    <Routes>
      <Route element={<Layout />}>
        {NAV.map(({ path, label, roles, ready }) => {
          const Page = ready ? PAGES[path] : null
          return (
            <Route
              key={path}
              path={path}
              element={<RequireRole roles={roles}>{Page ? <Page /> : <ComingSoon title={label} />}</RequireRole>}
            />
          )
        })}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
