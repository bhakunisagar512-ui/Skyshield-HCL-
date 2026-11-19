import { useEffect, useState } from 'react'
import { api } from '../../api'
import { ErrorAlert, Spinner } from '../../components/ui'
import { useTaxonomy } from '../../taxonomy'

export default function Policies() {
  const { categoryLabel } = useTaxonomy()
  const [policies, setPolicies] = useState(null)
  const [q, setQ] = useState('')
  const [hits, setHits] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => { api('/policies').then(setPolicies).catch(setError) }, [])

  async function search(e) {
    e.preventDefault()
    if (q.trim().length < 3) return
    setBusy(true); setError(null)
    try { setHits(await api('/policies/search', { query: { q: q.trim(), k: 5 } })) } catch (err) { setError(err) } finally { setBusy(false) }
  }

  return (
    <>
      <h1 className="page-title mb-1">Policy library</h1>
      <p className="muted">The documents the AI reads when it suggests measures. Search to see which sections it would pick for an incident.</p>
      <ErrorAlert error={error} />
      <form className="card mb-3" onSubmit={search}>
        <div className="card-body d-flex gap-2">
          <input className="form-control" placeholder="e.g. laser beam in the cockpit on final approach" value={q}
                 onChange={(e) => setQ(e.target.value)} aria-label="Search policies" />
          <button className="btn btn-primary" disabled={busy || q.trim().length < 3}>Search</button>
        </div>
        {hits && (
          <div className="card-body pt-0">
            {hits.map((h) => (
              <div key={h.key} className="border rounded p-2 mb-2">
                <div className="d-flex justify-content-between small">
                  <span className="fw-semibold">{h.section_ref}</span>
                  <span className="muted">score {h.score.toFixed(2)}</span>
                </div>
                <div className="small" style={{ whiteSpace: 'pre-wrap' }}>{h.content}</div>
              </div>
            ))}
          </div>
        )}
      </form>
      {!policies ? <Spinner /> : (
        <div className="card">
          <div className="table-responsive">
            <table className="table mb-0 align-middle">
              <thead className="table-light"><tr><th>Code</th><th>Title</th><th>Category</th><th className="text-end">Sections</th></tr></thead>
              <tbody>
                {policies.map((p) => (
                  <tr key={p.id}>
                    <td className="text-nowrap fw-semibold">{p.code}</td>
                    <td>{p.title}<div className="small muted">{p.source}</div></td>
                    <td className="small">{p.category ? categoryLabel(p.category) : 'General'}</td>
                    <td className="text-end">{p.chunk_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  )
}
