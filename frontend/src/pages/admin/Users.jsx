import { useEffect, useState } from 'react'
import { api } from '../../api'
import { ROLE_LABELS } from '../../auth'
import { ErrorAlert, Field, Spinner } from '../../components/ui'
import { useTaxonomy } from '../../taxonomy'

const EMPTY = { full_name: '', email: '', password: '', role: 'reporter', designation: '', base_station: '' }

export default function Users() {
  const { tax } = useTaxonomy()
  const [users, setUsers] = useState(null)
  const [form, setForm] = useState(EMPTY)
  const [errors, setErrors] = useState({})
  const [error, setError] = useState(null)
  const [saved, setSaved] = useState(null)
  const [busy, setBusy] = useState(false)

  const load = () => api('/admin/users').then(setUsers).catch(setError)
  useEffect(() => { load() }, [])
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  async function submit(e) {
    e.preventDefault()
    setBusy(true); setError(null); setErrors({}); setSaved(null)
    try {
      const u = await api('/admin/users', {
        method: 'POST',
        body: { ...form, designation: form.designation || null, base_station: form.base_station || null },
      })
      setSaved(u.email)
      setForm(EMPTY)
      load()
    } catch (err) {
      setErrors(err.fields || {}); setError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="row g-3">
      <div className="col-lg-8">
        <h1 className="page-title mb-3">Users</h1>
        {!users ? <Spinner /> : (
          <div className="card">
            <div className="table-responsive">
              <table className="table align-middle mb-0">
                <thead className="table-light"><tr><th>Name</th><th>Email</th><th>Role</th><th>Designation</th><th>Base</th></tr></thead>
                <tbody>
                  {users.map((u) => (
                    <tr key={u.id} className={u.is_active ? '' : 'text-muted'}>
                      <td>{u.full_name}{!u.is_active && <span className="badge badge-soft ms-2">Inactive</span>}</td>
                      <td className="small">{u.email}</td>
                      <td><span className="badge badge-soft">{ROLE_LABELS[u.role]}</span></td>
                      <td className="small">{u.designation || '—'}</td>
                      <td className="small">{u.base_station || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
      <div className="col-lg-4">
        <form className="card" onSubmit={submit} noValidate>
          <div className="card-header">Add user</div>
          <div className="card-body">
            {saved && <div className="alert alert-success py-2 small">Created {saved}</div>}
            <ErrorAlert error={error} />
            <Field label="Full name" error={errors.full_name}>
              <input className="form-control" value={form.full_name} onChange={set('full_name')} />
            </Field>
            <Field label="Email" error={errors.email}>
              <input type="email" className="form-control" value={form.email} onChange={set('email')} />
            </Field>
            <Field label="Temporary password" error={errors.password} hint="At least 8 characters.">
              <input type="password" className="form-control" autoComplete="new-password" value={form.password} onChange={set('password')} />
            </Field>
            <Field label="Role" error={errors.role}>
              <select className="form-select" value={form.role} onChange={set('role')}>
                {Object.entries(ROLE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </Field>
            <Field label="Designation" error={errors.designation}>
              <input className="form-control" placeholder="e.g. First Officer" value={form.designation} onChange={set('designation')} />
            </Field>
            <Field label="Base station" error={errors.base_station}>
              <select className="form-select" value={form.base_station} onChange={set('base_station')}>
                <option value="">—</option>
                {tax?.airports?.map((a) => <option key={a.code} value={a.code}>{a.city} ({a.code})</option>)}
              </select>
            </Field>
            <button className="btn btn-primary w-100" disabled={busy}>{busy ? 'Creating…' : 'Create user'}</button>
          </div>
        </form>
      </div>
    </div>
  )
}
