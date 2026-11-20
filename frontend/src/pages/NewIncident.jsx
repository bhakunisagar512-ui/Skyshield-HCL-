import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { ErrorAlert, Field, Spinner } from '../components/ui'
import { humanize, useTaxonomy } from '../taxonomy'

function localNow() {
  const d = new Date()
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset())
  return d.toISOString().slice(0, 16)
}

const EMPTY = {
  title: '', description: '', category: '', occurred_at: '', airport_code: '', flight_phase: '',
  aircraft_registration: '', aircraft_type: '', operator_code: '', flight_number: '',
}

export default function NewIncident() {
  const { tax } = useTaxonomy()
  const navigate = useNavigate()
  const [form, setForm] = useState(EMPTY)
  const [errors, setErrors] = useState({})
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const maxDate = useMemo(localNow, [])

  if (!tax) return <Spinner />

  const set = (k) => (e) => {
    setForm((f) => ({ ...f, [k]: e.target.value }))
    setErrors((er) => ({ ...er, [k]: undefined }))
  }

  function validate() {
    const er = {}
    if (form.title.trim().length < 5) er.title = 'At least 5 characters'
    if (form.description.trim().length < 20) er.description = 'Describe what happened (at least 20 characters)'
    for (const k of ['category', 'airport_code', 'flight_phase', 'occurred_at']) if (!form[k]) er[k] = 'Required'
    if (form.occurred_at && new Date(form.occurred_at) > new Date()) er.occurred_at = 'Cannot be in the future'
    setErrors(er)
    return Object.keys(er).length === 0
  }

  async function submit(e) {
    e.preventDefault()
    if (!validate()) return
    setBusy(true)
    setError(null)
    try {
      const body = { ...form, occurred_at: new Date(form.occurred_at).toISOString() }
      for (const k of ['aircraft_registration', 'aircraft_type', 'operator_code', 'flight_number']) {
        body[k] = body[k].trim() || null
      }
      body.title = body.title.trim()
      body.description = body.description.trim()
      const created = await api('/incidents', { method: 'POST', body })
      navigate(`/incidents/${created.id}`, { state: { justCreated: created.reference } })
    } catch (err) {
      setErrors(err.fields || {})
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  const cls = (k) => `form-control${errors[k] ? ' is-invalid' : ''}`
  const sel = (k) => `form-select${errors[k] ? ' is-invalid' : ''}`

  return (
    <div className="row justify-content-center">
      <div className="col-lg-9">
        <h1 className="page-title mb-1">Report an occurrence</h1>
        <p className="muted">Reports are used to prevent accidents, not to blame. Report anything that endangered, or could have endangered, safety.</p>
        <ErrorAlert error={error} onClose={() => setError(null)} />
        <form className="card" onSubmit={submit} noValidate>
          <div className="card-body">
            <Field label="Short title" error={errors.title}>
              <input className={cls('title')} maxLength={200} value={form.title} onChange={set('title')}
                     placeholder="e.g. Bird strike on take-off at Bengaluru" />
            </Field>
            <div className="row">
              <div className="col-md-6">
                <Field label="Category" error={errors.category}>
                  <select className={sel('category')} value={form.category} onChange={set('category')}>
                    <option value="">Choose…</option>
                    <optgroup label="DGCA high-risk categories">
                      {tax.categories.filter((c) => c.high_risk).map((c) => <option key={c.code} value={c.code}>{c.label}</option>)}
                    </optgroup>
                    <optgroup label="Other occurrences">
                      {tax.categories.filter((c) => !c.high_risk).map((c) => <option key={c.code} value={c.code}>{c.label}</option>)}
                    </optgroup>
                  </select>
                </Field>
              </div>
              <div className="col-md-6">
                <Field label="When did it happen?" error={errors.occurred_at}>
                  <input type="datetime-local" className={cls('occurred_at')} max={maxDate}
                         value={form.occurred_at} onChange={set('occurred_at')} />
                </Field>
              </div>
              <div className="col-md-6">
                <Field label="Airport" error={errors.airport_code}>
                  <select className={sel('airport_code')} value={form.airport_code} onChange={set('airport_code')}>
                    <option value="">Choose…</option>
                    {tax.airports.map((a) => <option key={a.code} value={a.code}>{a.city} ({a.code}) – {a.name}</option>)}
                  </select>
                </Field>
              </div>
              <div className="col-md-6">
                <Field label="Phase of flight" error={errors.flight_phase}>
                  <select className={sel('flight_phase')} value={form.flight_phase} onChange={set('flight_phase')}>
                    <option value="">Choose…</option>
                    {tax.flight_phases.map((p) => <option key={p} value={p}>{humanize(p)}</option>)}
                  </select>
                </Field>
              </div>
            </div>
            <Field label="What happened?" error={errors.description}
                   hint="Facts in order: what you saw, heard and did. Include times, altitudes and any warnings.">
              <textarea className={cls('description')} rows={6} maxLength={10000}
                        value={form.description} onChange={set('description')} />
            </Field>
            <div className="small-label mb-2">Aircraft and flight (optional)</div>
            <div className="row">
              <div className="col-md-3">
                <Field label="Registration" error={errors.aircraft_registration}>
                  <input className={cls('aircraft_registration')} maxLength={10} placeholder="VT-ABC"
                         value={form.aircraft_registration} onChange={set('aircraft_registration')} />
                </Field>
              </div>
              <div className="col-md-3">
                <Field label="Aircraft type" error={errors.aircraft_type}>
                  <select className="form-select" value={form.aircraft_type} onChange={set('aircraft_type')}>
                    <option value="">—</option>
                    {tax.aircraft_types.map((t) => <option key={t} value={t}>{t}</option>)}
                  </select>
                </Field>
              </div>
              <div className="col-md-3">
                <Field label="Operator" error={errors.operator_code}>
                  <select className="form-select" value={form.operator_code} onChange={set('operator_code')}>
                    <option value="">—</option>
                    {tax.operators.map((o) => <option key={o.code} value={o.code}>{o.name}</option>)}
                  </select>
                </Field>
              </div>
              <div className="col-md-3">
                <Field label="Flight number" error={errors.flight_number}>
                  <input className={cls('flight_number')} maxLength={10} placeholder="SHA321"
                         value={form.flight_number} onChange={set('flight_number')} />
                </Field>
              </div>
            </div>
          </div>
          <div className="card-footer bg-white d-flex justify-content-end gap-2">
            <button type="button" className="btn btn-outline-secondary" onClick={() => navigate(-1)}>Cancel</button>
            <button className="btn btn-primary" disabled={busy}>{busy ? 'Submitting…' : 'Submit report'}</button>
          </div>
        </form>
      </div>
    </div>
  )
}
