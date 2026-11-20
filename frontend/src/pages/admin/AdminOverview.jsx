import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../../api'
import { ColourPill, ErrorAlert, MeasureIcon, Pagination, SeverityBadge, Spinner, StatusBadge } from '../../components/ui'
import { formatDate, useTaxonomy } from '../../taxonomy'

const CHIPS = [
  ['red', 'Red', 'Mandatory measure not applied'],
  ['yellow', 'Yellow', 'Recommended measure open'],
  ['grey', 'In progress', 'Measures still pending'],
  ['green', 'Green', 'All measures applied'],
]

export default function AdminOverview() {
  const { tax, categoryLabel, airportLabel } = useTaxonomy()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const colour = params.get('colour') || ''
  const status = params.get('status') || ''
  const category = params.get('category') || ''
  const late = params.get('late') === '1'
  const page = Number(params.get('page') || 1)

  useEffect(() => {
    setData(null)
    api('/admin/incidents', { query: { colour, status, category, completed_late: late || '', page, page_size: 15 } }).then(setData).catch(setError)
  }, [colour, status, category, late, page])

  const update = (changes) => {
    const next = new URLSearchParams(params)
    Object.entries(changes).forEach(([k, v]) => (v ? next.set(k, v) : next.delete(k)))
    if (!('page' in changes)) next.delete('page')
    setParams(next)
  }
  const totals = data?.colour_totals || {}
  const all = Object.values(totals).reduce((a, b) => a + b, 0)

  return (
    <>
      <div className="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
        <div>
          <h1 className="page-title">Safety overview</h1>
          <div className="muted small">Every incident, coloured by how its measures were handled. Red first.</div>
        </div>
      </div>

      <div className="row g-2 mb-3">
        <div className="col-6 col-md">
          <button className={`btn w-100 h-100 text-start filter-chip ${!colour ? 'active' : ''}`} onClick={() => update({ colour: '' })}>
            <div className="small-label">All incidents</div>
            <div className="fs-4 fw-semibold">{data ? all : '…'}</div>
          </button>
        </div>
        {CHIPS.map(([key, label, hint]) => (
          <div className="col-6 col-md" key={key}>
            <button className={`btn w-100 h-100 text-start filter-chip ${colour === key ? 'active' : ''}`}
                    onClick={() => update({ colour: colour === key ? '' : key })} title={hint} aria-pressed={colour === key}>
              <div className="d-flex justify-content-between align-items-center">
                <ColourPill colour={key} />
              </div>
              <div className="fs-4 fw-semibold mt-1">{data ? totals[key] ?? 0 : '…'}</div>
              <div className="small muted text-truncate">{hint}</div>
            </button>
          </div>
        ))}
      </div>

      <div className="d-flex gap-2 mb-3 flex-wrap">
        <select className="form-select w-auto" value={status} onChange={(e) => update({ status: e.target.value })} aria-label="Status">
          <option value="">All statuses</option>
          <option value="submitted">Submitted</option>
          <option value="under_review">Under review</option>
          <option value="measures_pending">Measures pending</option>
          <option value="closed">Closed</option>
        </select>
        <select className="form-select w-auto" value={category} onChange={(e) => update({ category: e.target.value })} aria-label="Category">
          <option value="">All categories</option>
          {tax?.categories?.map((c) => <option key={c.code} value={c.code}>{c.label}</option>)}
        </select>
        <div className="form-check form-switch d-flex align-items-center gap-2 ms-1">
          <input className="form-check-input" type="checkbox" id="lateOnly" checked={late}
                 onChange={(e) => update({ late: e.target.checked ? '1' : '' })} />
          <label className="form-check-label small" htmlFor="lateOnly">
            Completed after closing{data ? ` (${data.completed_late_total})` : ''}
          </label>
        </div>
      </div>

      <ErrorAlert error={error} />
      {!data ? <Spinner /> : data.items.length === 0 ? (
        <div className="card"><div className="card-body muted text-center py-5">No incidents match these filters.</div></div>
      ) : (
        <div className="d-flex flex-column gap-2">
          {data.items.map((i) => (
            <div key={i.id} role="button" tabIndex={0}
                 className={`card row-accent row-accent-${i.colour}`}
                 onClick={() => navigate(`/admin/incidents/${i.id}`)}
                 onKeyDown={(e) => e.key === 'Enter' && navigate(`/admin/incidents/${i.id}`)}>
              <div className="card-body py-3">
                <div className="d-flex flex-column flex-md-row justify-content-between gap-2">
                  <div className="me-md-3" style={{ minWidth: 0, flex: 1 }}>
                    <div className="small muted mb-1">
                      {[i.reference, categoryLabel(i.category), airportLabel(i.airport_code), formatDate(i.occurred_at, false)].join(' · ')}
                    </div>
                    <div className="fw-semibold">{i.title}</div>
                    {i.short_summary && <div className="small muted mt-1">{i.short_summary}</div>}
                  </div>
                  <div className="d-flex flex-md-column flex-wrap align-items-center align-items-md-end gap-2 flex-shrink-0">
                    <ColourPill colour={i.colour} />
                    <div className="d-flex gap-2 small">
                      <SeverityBadge severity={i.severity} />
                      <StatusBadge status={i.status} />
                    </div>
                    {i.counts.total > 0 && (
                      <div className="d-flex gap-3 small" aria-label="Measure counts">
                        <span title="Applied"><MeasureIcon icon="tick" /> {i.counts.applied}</span>
                        {i.counts.not_applied_should > 0 && <span title="Recommended, not applied"><MeasureIcon icon="exclamation" /> {i.counts.not_applied_should}</span>}
                        {i.counts.not_applied_must > 0 && <span title="Mandatory, not applied"><MeasureIcon icon="cross" /> {i.counts.not_applied_must}</span>}
                        {i.counts.pending > 0 && <span title="Pending"><MeasureIcon icon="pending" /> {i.counts.pending}</span>}
                        {i.counts.completed_late > 0 && <span className="badge text-bg-success" title="Completed after closing">{i.counts.completed_late} late fix</span>}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
      {data && <Pagination page={data.page} pageSize={data.page_size} total={data.total} onChange={(p) => update({ page: String(p) })} />}
    </>
  )
}
