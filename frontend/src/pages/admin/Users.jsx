import { useEffect, useState } from 'react'
import { api } from '../../api'
import { ROLE_LABELS, useAuth } from '../../auth'
import { ErrorAlert, Field, Spinner } from '../../components/ui'
import { useTaxonomy } from '../../taxonomy'

const EMPTY = { full_name: '', email: '', password: '', role: 'reporter', designation: '', base_station: '' }

function UserRow({ u, isMe, onChanged, onMessage }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [confirming, setConfirming] = useState(false)
  const [resetOpen, setResetOpen] = useState(false)
  const [newPassword, setNewPassword] = useState('')

  async function act(fn, message) {
    setBusy(true); setError(null)
    try {
      await fn()
      onMessage(message)
      await onChanged()
      return true
    } catch (err) {
      setError(err)
      return false
    } finally {
      setBusy(false)
    }
  }

  const changeRole = (role) => act(
    () => api(`/admin/users/${u.id}`, { method: 'PATCH', body: { role } }),
    `${u.full_name} is now ${ROLE_LABELS[role]}.`,
  )
  const setActive = (is_active) => act(
    () => api(`/admin/users/${u.id}`, { method: 'PATCH', body: { is_active } }),
    `${u.full_name} ${is_active ? 'reactivated' : 'deactivated'}.`,
  ).then(() => setConfirming(false))
  const resetPassword = () => act(
    () => api(`/admin/users/${u.id}/reset-password`, { method: 'POST', body: { password: newPassword } }),
    `Password reset for ${u.full_name}. Give them the new password securely.`,
  ).then((ok) => { if (ok) { setResetOpen(false); setNewPassword('') } })

  return (
    <>
      <tr className={u.is_active ? '' : 'table-light'}>
        <td>
          <div className={u.is_active ? '' : 'text-muted'}>{u.full_name}</div>
          <div className="small muted">{u.email}</div>
          {isMe && <span className="badge text-bg-primary me-1">You</span>}
          {!u.is_active && <span className="badge badge-soft">Inactive</span>}
        </td>
        <td style={{ minWidth: 150 }}>
          <select className="form-select form-select-sm" value={u.role} aria-label={`Role for ${u.full_name}`}
                  disabled={busy || isMe || !u.is_active} onChange={(e) => changeRole(e.target.value)}
                  title={isMe ? 'You cannot change your own role' : undefined}>
            {Object.entries(ROLE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </td>
        <td className="small">{u.designation || '—'}{u.base_station && <div className="muted">{u.base_station}</div>}</td>
        <td className="text-end text-nowrap">
          {confirming ? (
            <span className="d-inline-flex align-items-center gap-2">
              <span className="small">Deactivate?</span>
              <button className="btn btn-sm btn-danger" disabled={busy} onClick={() => setActive(false)}>Yes</button>
              <button className="btn btn-sm btn-outline-secondary" onClick={() => setConfirming(false)}>No</button>
            </span>
          ) : (
            <div className="btn-group btn-group-sm">
              <button className="btn btn-outline-secondary" disabled={busy || !u.is_active}
                      onClick={() => setResetOpen((o) => !o)}>
                <i className="bi bi-key me-1" aria-hidden="true" />Reset password
              </button>
              {u.is_active ? (
                <button className="btn btn-outline-danger" disabled={busy || isMe}
                        title={isMe ? 'You cannot deactivate yourself' : undefined}
                        onClick={() => setConfirming(true)}>Deactivate</button>
              ) : (
                <button className="btn btn-outline-success" disabled={busy} onClick={() => setActive(true)}>Reactivate</button>
              )}
            </div>
          )}
        </td>
      </tr>
      {(resetOpen || error) && (
        <tr className="table-light">
          <td colSpan={4}>
            {error && <div className="text-danger small mb-2">{error.message}</div>}
            {resetOpen && (
              <form className="d-flex gap-2 align-items-center flex-wrap" onSubmit={(e) => { e.preventDefault(); resetPassword() }}>
                <span className="small">New temporary password for {u.full_name}:</span>
                <input type="password" className="form-control form-control-sm" style={{ maxWidth: 240 }} autoFocus
                       autoComplete="new-password" placeholder="At least 8 characters" value={newPassword}
                       onChange={(e) => setNewPassword(e.target.value)} />
                <button className="btn btn-sm btn-primary" disabled={busy || newPassword.length < 8}>Set password</button>
                <button type="button" className="btn btn-sm btn-outline-secondary" onClick={() => setResetOpen(false)}>Cancel</button>
              </form>
            )}
          </td>
        </tr>
      )}
    </>
  )
}

export default function Users() {
  const { user: me } = useAuth()
  const { tax } = useTaxonomy()
  const [users, setUsers] = useState(null)
  const [showInactive, setShowInactive] = useState(true)
  const [form, setForm] = useState(EMPTY)
  const [errors, setErrors] = useState({})
  const [error, setError] = useState(null)
  const [message, setMessage] = useState(null)
  const [busy, setBusy] = useState(false)
  const [formOpen, setFormOpen] = useState(false)

  const load = () => api('/admin/users').then(setUsers).catch(setError)
  useEffect(() => { load() }, [])
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  async function submit(e) {
    e.preventDefault()
    setBusy(true); setError(null); setErrors({}); setMessage(null)
    try {
      const u = await api('/admin/users', {
        method: 'POST',
        body: { ...form, designation: form.designation || null, base_station: form.base_station || null },
      })
      setMessage(`Created ${u.email}.`)
      setForm(EMPTY)
      setFormOpen(false)
      load()
    } catch (err) {
      setErrors(err.fields || {}); setError(err)
    } finally {
      setBusy(false)
    }
  }

  const visible = users?.filter((u) => showInactive || u.is_active) || []
  const inactiveCount = users?.filter((u) => !u.is_active).length || 0

  return (
    <>
      <div className="d-flex justify-content-between align-items-center mb-2 flex-wrap gap-2">
        <h1 className="page-title">Users</h1>
        <div className="d-flex align-items-center gap-3">
          <div className="form-check form-switch m-0">
            <input className="form-check-input" type="checkbox" id="showInactive" checked={showInactive}
                   onChange={(e) => setShowInactive(e.target.checked)} />
            <label className="form-check-label small" htmlFor="showInactive">Show inactive ({inactiveCount})</label>
          </div>
          <button className="btn btn-primary btn-sm" onClick={() => setFormOpen((o) => !o)} aria-expanded={formOpen}>
            <i className={`bi ${formOpen ? 'bi-x-lg' : 'bi-person-plus'} me-1`} aria-hidden="true" />{formOpen ? 'Cancel' : 'Add user'}
          </button>
        </div>
      </div>
      <p className="muted small mb-3">
        Users are deactivated rather than deleted, so every report, decision and measure keeps a record of who made it.
        A deactivated user cannot sign in.
      </p>
      {message && (
        <div className="alert alert-success py-2 d-flex justify-content-between align-items-center">
          <span>{message}</span>
          <button type="button" className="btn-close" aria-label="Close" onClick={() => setMessage(null)} />
        </div>
      )}
      {formOpen && (
        <form className="card mb-3" onSubmit={submit} noValidate>
          <div className="card-header">Add user</div>
          <div className="card-body">
            <ErrorAlert error={error} />
            <div className="row">
              <div className="col-md-4">
                <Field label="Full name" error={errors.full_name}>
                  <input className="form-control" value={form.full_name} onChange={set('full_name')} />
                </Field>
              </div>
              <div className="col-md-4">
                <Field label="Email" error={errors.email}>
                  <input type="email" className="form-control" value={form.email} onChange={set('email')} />
                </Field>
              </div>
              <div className="col-md-4">
                <Field label="Temporary password" error={errors.password} hint="At least 8 characters.">
                  <input type="password" className="form-control" autoComplete="new-password" value={form.password} onChange={set('password')} />
                </Field>
              </div>
              <div className="col-md-4">
                <Field label="Role" error={errors.role}>
                  <select className="form-select" value={form.role} onChange={set('role')}>
                    {Object.entries(ROLE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                  </select>
                </Field>
              </div>
              <div className="col-md-4">
                <Field label="Designation" error={errors.designation}>
                  <input className="form-control" placeholder="e.g. First Officer" value={form.designation} onChange={set('designation')} />
                </Field>
              </div>
              <div className="col-md-4">
                <Field label="Base station" error={errors.base_station}>
                  <select className="form-select" value={form.base_station} onChange={set('base_station')}>
                    <option value="">—</option>
                    {tax?.airports?.map((a) => <option key={a.code} value={a.code}>{a.city} ({a.code})</option>)}
                  </select>
                </Field>
              </div>
            </div>
            <button className="btn btn-primary" disabled={busy}>{busy ? 'Creating…' : 'Create user'}</button>
          </div>
        </form>
      )}
      {!users ? <Spinner /> : (
        <div className="card">
          <div className="table-responsive">
            <table className="table align-middle mb-0">
              <thead className="table-light"><tr><th>User</th><th>Role</th><th>Designation</th><th className="text-end">Actions</th></tr></thead>
              <tbody>
                {visible.map((u) => (
                  <UserRow key={u.id} u={u} isMe={u.id === me.id} onChanged={load} onMessage={setMessage} />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  )
}
