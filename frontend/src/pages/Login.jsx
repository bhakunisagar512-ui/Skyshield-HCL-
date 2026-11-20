import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { homeFor, useAuth } from '../auth'
import { ErrorAlert } from '../components/ui'

// Development only: matches the seeded demo users.
const DEMO = [
  ['Reporter', 'ananya.iyer@skyshield.example'],
  ['Safety Officer', 'arjun.mehta@skyshield.example'],
  ['Admin', 'admin@skyshield.example'],
]

export default function Login() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  if (user) return <Navigate to={homeFor(user.role)} replace />

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const u = await login(email.trim(), password)
      navigate(location.state?.from || homeFor(u.role), { replace: true })
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-wrap px-3">
      <div className="card login-card shadow">
        <div className="card-body p-4">
          <div className="text-center mb-4">
            <i className="bi bi-shield-fill-check text-primary" style={{ fontSize: '2.4rem' }} aria-hidden="true" />
            <h1 className="h4 mt-2 mb-0">SkyShield</h1>
            <div className="muted small">Aviation safety and incident reporting</div>
          </div>
          <ErrorAlert error={error} />
          <form onSubmit={submit} noValidate>
            <div className="mb-3">
              <label className="form-label fw-semibold" htmlFor="email">Email</label>
              <input id="email" type="email" className="form-control" autoComplete="username" required
                     value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
            <div className="mb-3">
              <label className="form-label fw-semibold" htmlFor="password">Password</label>
              <input id="password" type="password" className="form-control" autoComplete="current-password" required
                     value={password} onChange={(e) => setPassword(e.target.value)} />
            </div>
            <button className="btn btn-primary w-100" disabled={busy || !email || !password}>
              {busy ? 'Signing in…' : 'Sign in'}
            </button>
          </form>
          <hr />
          <div className="small muted mb-2">Demo accounts (password <code>Password@123</code>)</div>
          <div className="d-flex flex-wrap gap-2">
            {DEMO.map(([label, mail]) => (
              <button key={mail} type="button" className="btn btn-sm btn-outline-secondary"
                      onClick={() => { setEmail(mail); setPassword('Password@123') }}>
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
