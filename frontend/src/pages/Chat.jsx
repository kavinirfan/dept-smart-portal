import { browserSupportsWebAuthn, platformAuthenticatorIsAvailable, startAuthentication, startRegistration } from '@simplewebauthn/browser'
import { useCallback, useEffect, useRef, useState } from 'react'
import { api, fmtTime, getToken, upload } from '../api'
import { ROLE_LABELS, useAuth } from '../auth.jsx'

function defaultDeviceName() {
  const ua = navigator.userAgent
  if (/Mac/.test(ua)) return 'MacBook (Touch ID)'
  if (/iPhone|iPad/.test(ua)) return 'iPhone (Face ID)'
  if (/Android/.test(ua)) return 'Android phone'
  if (/Windows/.test(ua)) return 'Windows PC (Hello)'
  return 'This device'
}

// Step 1 of 2: upload the college ID card for an admin to approve.
function IdCardStep({ status, onDone }) {
  const [file, setFile] = useState(null)
  const [idNumber, setIdNumber] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const { user } = useAuth()

  useEffect(() => { setIdNumber(user.roll_no ?? '') }, [user.roll_no])

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    const fd = new FormData()
    fd.append('id_number', idNumber)
    fd.append('image', file)
    try {
      await upload('/chat/id-card', fd)
      onDone()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  if (status.id_status === 'pending') {
    return (
      <section className="card gate">
        <Steps at={1} />
        <h2>Your ID card is with the department</h2>
        <p className="muted-text">An admin will check it against college records. You'll get a notification as soon as it's approved.</p>
      </section>
    )
  }

  return (
    <form className="card gate form-grid" onSubmit={submit}>
      <Steps at={1} />
      <h2>Verify your college ID</h2>
      <p className="muted-text">Campus chat is only for verified students and staff. Upload a clear photo of your college ID card; an admin approves it once.</p>
      {status.id_status === 'rejected' && (
        <p className="error">Your last upload was not approved: {status.id_review_note}. Please try again.</p>
      )}
      <label>ID / roll number<input value={idNumber} onChange={(e) => setIdNumber(e.target.value)} required minLength={3} /></label>
      <label>Photo of ID card (PNG, JPEG or WebP, under 5 MB)
        <input type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => setFile(e.target.files[0])} required />
      </label>
      <button className="btn" disabled={busy}>{busy ? 'Uploading…' : 'Submit for approval'}</button>
      {error && <p className="error">{error}</p>}
    </form>
  )
}

// Step 2 of 2: unlock with the device's own biometric (WebAuthn).
function UnlockStep({ status, onUnlocked }) {
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [platform, setPlatform] = useState(null)
  const [showPassword, setShowPassword] = useState(false)
  const [password, setPassword] = useState('')
  const [label, setLabel] = useState(defaultDeviceName())
  const hasDevice = status.devices.length > 0
  const supported = browserSupportsWebAuthn()

  useEffect(() => { platformAuthenticatorIsAvailable().then(setPlatform) }, [])

  async function run(fn) {
    setBusy(true)
    setError('')
    try {
      await fn()
      onUnlocked()
    } catch (err) {
      setError(err.name === 'NotAllowedError' ? 'Cancelled or timed out. Try again.' : err.message)
    } finally {
      setBusy(false)
    }
  }

  const register = () => run(async () => {
    const optionsJSON = await api('/chat/webauthn/register/options', { method: 'POST' })
    const credential = await startRegistration({ optionsJSON })
    await api('/chat/webauthn/register/verify', { method: 'POST', body: { credential, device_label: label } })
  })

  const unlock = () => run(async () => {
    const optionsJSON = await api('/chat/webauthn/unlock/options', { method: 'POST' })
    const credential = await startAuthentication({ optionsJSON })
    await api('/chat/webauthn/unlock/verify', { method: 'POST', body: { credential } })
  })

  const unlockPassword = (e) => {
    e.preventDefault()
    run(() => api('/chat/unlock/password', { method: 'POST', body: { password } }))
  }

  return (
    <section className="card gate">
      <Steps at={2} />
      <div className="fingerprint" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="56" height="56" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
          <path d="M12 11c0 3.5-1 6.5-2.5 8.5" /><path d="M8.5 5.3A7 7 0 0 1 19 11c0 1.4-.1 2.8-.4 4.1" />
          <path d="M5 8.5A7 7 0 0 0 5 11c0 2.3-.5 4-1.2 5.2" /><path d="M15.5 11a3.5 3.5 0 0 0-7 0c0 2.2-.4 4.3-1.2 6.2" />
          <path d="M12 7.5A3.5 3.5 0 0 1 15.5 11c0 3-.6 5.8-1.7 8.2" /><path d="M18.4 18.5c.3-1 .5-2 .6-3" />
        </svg>
      </div>
      {!status.verified && status.id_required ? null : hasDevice ? (
        <>
          <h2>Unlock campus chat</h2>
          <p className="muted-text">Use your fingerprint, face or device PIN. Chat stays open for {status.session_minutes} minutes.</p>
          <button className="btn big" onClick={unlock} disabled={busy || !supported}>{busy ? 'Waiting for your device…' : 'Unlock with fingerprint'}</button>
          <details className="devices">
            <summary>Registered devices ({status.devices.length})</summary>
            <ul>{status.devices.map((d) => <li key={d.credential_id}>{d.device_label}</li>)}</ul>
            <div className="pair">
              <input value={label} onChange={(e) => setLabel(e.target.value)} aria-label="Device name" />
              <button className="btn ghost" onClick={register} disabled={busy || !supported}>Add this device</button>
            </div>
          </details>
        </>
      ) : (
        <>
          <h2>Set up fingerprint unlock</h2>
          <p className="muted-text">
            Your device checks your fingerprint or face itself; the portal only stores a public key, never biometric data.
            {platform === false && ' This browser did not report a built-in fingerprint or face sensor; a phone or security key may still work.'}
          </p>
          <label>Name this device<input value={label} onChange={(e) => setLabel(e.target.value)} maxLength={80} /></label>
          <button className="btn big" onClick={register} disabled={busy || !supported}>{busy ? 'Waiting for your device…' : 'Register this device'}</button>
        </>
      )}
      {!supported && <p className="error">This browser does not support fingerprint unlock (WebAuthn). Open the portal at http://localhost:8000 in Chrome, Safari or Edge.</p>}
      {error && <p className="error">{error}</p>}
      {status.password_fallback && (
        showPassword ? (
          <form className="pair" onSubmit={unlockPassword}>
            <input type="password" placeholder="Your portal password" value={password} onChange={(e) => setPassword(e.target.value)} required />
            <button className="btn ghost" disabled={busy}>Unlock</button>
          </form>
        ) : (
          <button className="link-btn" onClick={() => setShowPassword(true)}>No fingerprint sensor? Unlock with your password</button>
        )
      )}
    </section>
  )
}

function Steps({ at }) {
  return (
    <ol className="steps">
      <li className={at > 1 ? 'done' : 'current'}>ID card approved</li>
      <li className={at === 2 ? 'current' : ''}>Device unlock</li>
    </ol>
  )
}

function Room({ status, onLocked }) {
  const { user } = useAuth()
  const [messages, setMessages] = useState([])
  const [text, setText] = useState('')
  const [online, setOnline] = useState(0)
  const [conn, setConn] = useState('connecting')
  const [error, setError] = useState('')
  const [left, setLeft] = useState('')
  const ws = useRef(null)
  const bottom = useRef(null)

  useEffect(() => {
    api('/chat/messages').then(setMessages)
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const sock = new WebSocket(`${proto}://${window.location.host}/api/chat/ws?token=${getToken()}`)
    ws.current = sock
    sock.onopen = () => setConn('open')
    sock.onclose = (e) => {
      setConn('closed')
      if (e.code === 4403) onLocked()
    }
    sock.onmessage = (e) => {
      const evt = JSON.parse(e.data)
      if (evt.type === 'message') setMessages((ms) => [...ms, evt])
      else if (evt.type === 'hidden') setMessages((ms) => ms.filter((m) => m.message_id !== evt.message_id))
      else if (evt.type === 'presence') setOnline(evt.online)
      else if (evt.type === 'error') setError(evt.detail)
      else if (evt.type === 'expired') onLocked()
    }
    return () => sock.close()
  }, [onLocked])

  useEffect(() => { bottom.current?.scrollIntoView({ block: 'end' }) }, [messages])

  useEffect(() => {
    const tick = () => {
      const mins = Math.max(0, Math.round((new Date(status.session_expires) - Date.now()) / 60000))
      setLeft(mins >= 60 ? `${Math.floor(mins / 60)} h ${mins % 60} min` : `${mins} min`)
      if (mins <= 0) onLocked()
    }
    tick()
    const id = setInterval(tick, 30000)
    return () => clearInterval(id)
  }, [status.session_expires, onLocked])

  function send(e) {
    e.preventDefault()
    if (!text.trim() || ws.current?.readyState !== WebSocket.OPEN) return
    setError('')
    ws.current.send(JSON.stringify({ text }))
    setText('')
  }

  async function report(m) {
    if (!window.confirm(`Report this message from ${m.sender_name} to the department?`)) return
    try {
      await api(`/chat/messages/${m.message_id}/report`, { method: 'POST' })
      setMessages((ms) => ms.map((x) => (x.message_id === m.message_id ? { ...x, reported: true } : x)))
    } catch (err) {
      setError(err.message)
    }
  }

  async function lock() {
    await api('/chat/lock', { method: 'POST' })
    onLocked()
  }

  const dayOf = (m) => new Date(m.sent_at).toDateString()
  return (
    <section className="card chat">
      <div className="chat-head">
        <div>
          <strong>Campus chat</strong>
          <small className="muted-text"> · {conn === 'open' ? `${online} online` : conn === 'connecting' ? 'connecting…' : 'disconnected'} · verified members only</small>
        </div>
        <div className="toolbar-actions">
          <small className="muted-text">Unlocked · {left} left</small>
          <button className="btn small ghost" onClick={lock}>Lock</button>
        </div>
      </div>
      <div className="chat-body">
        {messages.map((m, i) => {
          const showDay = i === 0 || dayOf(messages[i - 1]) !== dayOf(m)
          const mine = m.sender_id === user.user_id
          return (
            <div key={m.message_id}>
              {showDay && <div className="day-sep">{new Date(m.sent_at).toLocaleDateString([], { weekday: 'long', day: 'numeric', month: 'short' })}</div>}
              <div className={`msg ${mine ? 'mine' : ''}`}>
                {!mine && <div className="msg-from">{m.sender_name} <span className="muted-text">· {ROLE_LABELS[m.sender_role]}</span></div>}
                <div className="bubble">{m.text}</div>
                <div className="msg-meta">
                  {fmtTime(m.sent_at)}
                  {!mine && (m.reported ? <span> · reported</span> : <button className="link-btn" onClick={() => report(m)}>Report</button>)}
                </div>
              </div>
            </div>
          )
        })}
        <div ref={bottom} />
      </div>
      {error && <p className="error chat-error">{error}</p>}
      <form className="chat-input" onSubmit={send}>
        <input placeholder="Write a message" value={text} onChange={(e) => setText(e.target.value)} maxLength={1000} disabled={conn !== 'open'} />
        <button className="btn" disabled={conn !== 'open' || !text.trim()}>Send</button>
      </form>
    </section>
  )
}

export default function Chat() {
  const [status, setStatus] = useState(null)
  const load = useCallback(() => api('/chat/status').then(setStatus), [])
  useEffect(() => { load() }, [load])

  if (!status) return <p className="card muted-text">Loading…</p>
  if (status.session_expires && new Date(status.session_expires) > new Date()) return <Room status={status} onLocked={load} />
  if (status.id_required && !status.verified) return <IdCardStep status={status} onDone={load} />
  return <UnlockStep status={status} onUnlocked={load} />
}
