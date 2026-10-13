import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth.jsx'

const DEMO = [
  ['HOD / Admin', 'hod@dept.edu'],
  ['Teacher', 'arjun@dept.edu'],
  ['Lab In-charge', 'labincharge@dept.edu'],
  ['Student', 'kavin@dept.edu'],
]

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await login(email, password)
      navigate('/')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="center-screen">
      <form className="card login" onSubmit={submit}>
        <div className="brand big">
          <span className="brand-mark">DSP</span>
          <span>Department Smart Portal</span>
        </div>
        <label>
          Email
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus />
        </label>
        <label>
          Password
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </label>
        {error && <p className="error">{error}</p>}
        <button className="btn" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
        <div className="demo">
          <p>Demo accounts (password <code>portal123</code>):</p>
          <div className="chips">
            {DEMO.map(([label, mail]) => (
              <button type="button" key={mail} className="chip" onClick={() => { setEmail(mail); setPassword('portal123') }}>
                {label}
              </button>
            ))}
          </div>
        </div>
      </form>
    </div>
  )
}
