import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../../api'
import { ColourPill, ErrorAlert, MeasureIcon, PriorityBadge, SeverityBadge, Spinner, StatusBadge } from '../../components/ui'
import { formatDate, useTaxonomy } from '../../taxonomy'
import { FollowUpInfo } from '../officer/Workflow'

function MeasureList({ items, empty, showReason, showFollowUp }) {
  if (!items.length) return <div className="muted small">{empty}</div>
  return items.map((m) => (
    <div key={m.id} className="measure-row d-flex gap-3">
      <div className="pt-1"><MeasureIcon icon={m.icon} /></div>
      <div>
        <div className="d-flex gap-2 align-items-center flex-wrap mb-1">
          <PriorityBadge priority={m.priority} />
          {m.source === 'officer' && <span className="badge badge-soft">Added by officer</span>}
          {m.completed_late && <span className="badge text-bg-success">Completed after closing</span>}
          {m.policy_reference && <span className="small muted">{m.policy_reference}</span>}
        </div>
        <div>{m.description}</div>
        {showReason && m.reason && <div className="small mt-1"><span className="fw-semibold">Reason:</span> {m.reason}</div>}
        {showFollowUp && <FollowUpInfo m={m} />}
      </div>
    </div>
  ))
}

export default function AdminIncident() {
  const { id } = useParams()
  const { categoryLabel, airportLabel } = useTaxonomy()
  const [d, setD] = useState(null)
  const [error, setError] = useState(null)
  useEffect(() => { api(`/admin/incidents/${id}`).then(setD).catch(setError) }, [id])

  if (error) return <ErrorAlert error={error} />
  if (!d) return <Spinner />

  return (
    <>
      <div className="mb-3"><Link to="/admin" className="small"><i className="bi bi-arrow-left me-1" aria-hidden="true" />Overview</Link></div>
      <div className={`card row-accent row-accent-${d.colour} mb-3`}>
        <div className="card-body d-flex justify-content-between flex-wrap gap-2">
          <div>
            <div className="small muted">{d.reference} · {categoryLabel(d.category)} · {airportLabel(d.airport_code)} · {formatDate(d.occurred_at)}</div>
            <h1 className="page-title">{d.title}</h1>
          </div>
          <div className="d-flex flex-column align-items-end gap-2">
            <ColourPill colour={d.colour} long />
            <div className="d-flex gap-2"><SeverityBadge severity={d.severity} /><StatusBadge status={d.status} /></div>
          </div>
        </div>
      </div>

      <div className="row g-3">
        <div className="col-lg-6">
          <div className="card mb-3">
            <div className="card-header">Issue</div>
            <div className="card-body" style={{ whiteSpace: 'pre-wrap' }}>{d.issue}</div>
          </div>
          <div className="card mb-3">
            <div className="card-header d-flex justify-content-between">
              <span>Short summary</span>
              {d.summary_status && <span className="badge badge-soft">{d.summary_status}</span>}
            </div>
            <div className="card-body">{d.short_summary || <span className="muted">No summary yet.</span>}</div>
          </div>
          <div className="card mb-3">
            <div className="card-header">Suggested measures <span className="muted fw-normal small">(from AI)</span></div>
            <div className="card-body pt-1"><MeasureList items={d.suggested_measures} empty="No AI suggestions." /></div>
          </div>
        </div>
        <div className="col-lg-6">
          <div className="card mb-3">
            <div className="card-header"><MeasureIcon icon="tick" /> Applied measures ({d.applied_measures.length})</div>
            <div className="card-body pt-1"><MeasureList items={d.applied_measures} empty="None applied yet." showFollowUp /></div>
          </div>
          <div className="card mb-3">
            <div className="card-header"><MeasureIcon icon="cross" /> Not applied ({d.not_applied_measures.length})</div>
            <div className="card-body pt-1"><MeasureList items={d.not_applied_measures} empty="Nothing left unapplied." showReason /></div>
          </div>
          {d.pending_measures.length > 0 && (
            <div className="card mb-3">
              <div className="card-header"><MeasureIcon icon="pending" /> Pending ({d.pending_measures.length})</div>
              <div className="card-body pt-1"><MeasureList items={d.pending_measures} empty="" /></div>
            </div>
          )}
          <Link to={`/incidents/${d.id}`} className="btn btn-outline-primary btn-sm">Open full incident record</Link>
        </div>
      </div>
    </>
  )
}
