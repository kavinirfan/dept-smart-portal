import { Link } from 'react-router-dom'
import { ROLE_LABELS, useAuth } from '../auth.jsx'
import { navFor } from '../nav.js'

const BLURBS = {
  '/marks': 'Question-wise marks and charts for every test.',
  '/labs': 'See which labs are free and book a slot.',
  '/faculty': 'Check whether a teacher is in the department right now.',
  '/notices': 'Current job and internship openings.',
  '/chat': 'Campus-only chat for verified students and staff.',
  '/dashboard': 'Live overview of the whole department.',
  '/admin/users': 'Add students and staff, change roles.',
  '/admin/verification': 'Approve ID cards and review reported chat messages.',
  '/admin/subjects': 'Subjects and which teachers may enter marks.',
  '/admin/audit': 'Every change, who made it and when.',
  '/profile': 'Your details and password.',
}

export default function Home() {
  const { user } = useAuth()
  const tiles = navFor(user.role).filter((n) => n.path !== '/')
  return (
    <>
      <section className="card welcome">
        <h2>Welcome, {user.name}</h2>
        <p>
          Signed in as <strong>{ROLE_LABELS[user.role]}</strong>, {user.department}.
        </p>
      </section>
      <div className="tiles">
        {tiles.map((t) => (
          <Link key={t.path} to={t.path} className={`card tile ${t.ready ? '' : 'muted'}`}>
            <h3>
              {t.label} {!t.ready && <span className="soon">soon</span>}
            </h3>
            <p>{BLURBS[t.path]}</p>
          </Link>
        ))}
      </div>
    </>
  )
}
