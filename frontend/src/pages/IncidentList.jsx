import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import { ColourPill, ErrorAlert, Pagination, SeverityBadge, Spinner, StatusBadge } from '../components/ui'
import { formatDate, useTaxonomy } from '../taxonomy'

const STATUS_TABS = [
  ['', 'All'],
  ['submitted', 'Submitted'],
  ['under_review', 'Under review'],
  ['measures_pending', 'Measures pending'],
  ['closed', 'Closed'],
]

export default function IncidentList() {
  const { user } = useAuth()
  const { tax, categoryLabel, airportLabel } = useTaxonomy()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState(params.get('q') || '')
  const isReporter = user.role === 'reporter'

  const query = {
    status: params.get('status') || '',
    category: params.get('category') || '',
    colour: params.get('colour') || '',
    q: params.get('q') || '',
    page: params.get('page') || 1,
    page_size: 20,
  }

  useEffect(() => {
    setData(null)
    api('/incidents', { query }).then(setData).catch(setError)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.toString()])

  const update = (changes) => {
    const next = new URLSearchParams(params)
    Object.entries(changes).forEach(([k, v]) => (v ? next.set(k, v) : next.delete(k)))
    if (!('page' in changes)) next.delete('page')
    setParams(next)
  }

  return (
    <>
      <div className="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
        <h1 className="page-title">{isReporter ? 'My reports' : 'Incident queue'}</h1>
        <Link to="/report/new" className="btn btn-primary"><i className="bi bi-plus-lg me-1" aria-hidden="true" />New report</Link>
      </div>

      <ul className="nav nav-pills mb-3 flex-wrap">
        {STATUS_TABS.map(([value, label]) => (
          <li className="nav-item" key={value}>
            <button className={`nav-link ${query.status === value ? 'active' : ''}`} onClick={() => update({ status: value })}>
              {label}
            </button>
          </li>
        ))}
      </ul>

      <div className="card mb-3">
        <div className="card-body d-flex flex-wrap gap-2 align-items-center">
          <form className="d-flex gap-2 flex-grow-1" onSubmit={(e) => { e.preventDefault(); update({ q: search.trim() }) }}>
            <input className="form-control" placeholder="Search title, description, reference or registration"
                   value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Search incidents" />
            <button className="btn btn-outline-primary">Search</button>
          </form>
          <select className="form-select w-auto" value={query.category} aria-label="Category"
                  onChange={(e) => update({ category: e.target.value })}>
            <option value="">All categories</option>
            {tax?.categories?.map((c) => <option key={c.code} value={c.code}>{c.label}</option>)}
          </select>
          {!isReporter && (
            <select className="form-select w-auto" value={query.colour} aria-label="Colour"
                    onChange={(e) => update({ colour: e.target.value })}>
              <option value="">All colours</option>
              <option value="red">Red</option>
              <option value="yellow">Yellow</option>
              <option value="green">Green</option>
              <option value="grey">In progress</option>
            </select>
          )}
        </div>
      </div>

      <ErrorAlert error={error} />
      {!data ? <Spinner /> : data.items.length === 0 ? (
        <div className="card"><div className="card-body text-center muted py-5">
          {isReporter && !query.status && !query.q ? 'You have not filed any reports yet.' : 'No incidents match these filters.'}
        </div></div>
      ) : (
        <div className="card">
          <div className="table-responsive">
            <table className="table table-hover align-middle mb-0">
              <thead className="table-light">
                <tr>
                  <th>Reference</th><th>Title</th><th>Category</th><th>Airport</th><th>Occurred</th>
                  <th>Severity</th><th>Status</th>{!isReporter && <th>Measures</th>}
                </tr>
              </thead>
              <tbody>
                {data.items.map((i) => (
                  <tr key={i.id} onClick={() => navigate(`/incidents/${i.id}`)}>
                    <td className="text-nowrap"><Link to={`/incidents/${i.id}`} onClick={(e) => e.stopPropagation()}>{i.reference}</Link></td>
                    <td>{i.title}</td>
                    <td className="small">{categoryLabel(i.category)}</td>
                    <td className="small text-nowrap">{airportLabel(i.airport_code)}</td>
                    <td className="small text-nowrap">{formatDate(i.occurred_at, false)}</td>
                    <td><SeverityBadge severity={i.severity} /></td>
                    <td><StatusBadge status={i.status} /></td>
                    {!isReporter && <td><ColourPill colour={i.colour} /></td>}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      {data && <Pagination page={data.page} pageSize={data.page_size} total={data.total} onChange={(p) => update({ page: String(p) })} />}
    </>
  )
}
