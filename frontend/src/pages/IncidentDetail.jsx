import { useCallback, useEffect, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import { ColourPill, ErrorAlert, SeverityBadge, Spinner, StatusBadge } from '../components/ui'
import { formatDate, humanize, useTaxonomy } from '../taxonomy'
import { AnalysisCard, CloseCard, MeasuresCard, StartReviewCard, SummaryCard } from './officer/Workflow'

export default function IncidentDetail() {
  const { id } = useParams()
  const { user } = useAuth()
  const location = useLocation()
  const { categoryLabel, airportLabel, operatorLabel } = useTaxonomy()
  const [incident, setIncident] = useState(null)
  const [error, setError] = useState(null)

  const load = useCallback(() => api(`/incidents/${id}`).then(setIncident).catch(setError), [id])
  useEffect(() => { load() }, [load])

  // poll while the AI is generating
  const generating = incident?.summary?.status === 'generating'
  useEffect(() => {
    if (!generating) return undefined
    const t = setTimeout(load, 1500)
    return () => clearTimeout(t)
  }, [generating, incident, load])

  if (error) return <ErrorAlert error={error} />
  if (!incident) return <Spinner />

  const isOfficer = user.role === 'safety_officer'
  const isReporter = user.role === 'reporter'
  const open = incident.status === 'measures_pending'
  const details = [
    ['Category', categoryLabel(incident.category)],
    ['Occurred', formatDate(incident.occurred_at)],
    ['Airport', airportLabel(incident.airport_code)],
    ['Phase of flight', humanize(incident.flight_phase)],
    ['Aircraft', [incident.aircraft_type, incident.aircraft_registration].filter(Boolean).join(' · ') || '—'],
    ['Flight', [operatorLabel(incident.operator_code), incident.flight_number].filter(Boolean).join(' · ') || '—'],
    ['Reported by', incident.reporter.full_name],
    ['Safety Officer', incident.officer?.full_name || 'Not assigned'],
  ]

  return (
    <>
      {location.state?.justCreated && (
        <div className="alert alert-success">
          <i className="bi bi-check-circle me-2" aria-hidden="true" />
          Report <strong>{location.state.justCreated}</strong> submitted. A Safety Officer will review it.
        </div>
      )}
      <div className="mb-3">
        <Link to={user.role === 'admin' ? '/admin' : '/incidents'} className="small">
          <i className="bi bi-arrow-left me-1" aria-hidden="true" />Back
        </Link>
      </div>
      <div className="d-flex justify-content-between align-items-start flex-wrap gap-2 mb-3">
        <div>
          <div className="muted small">{incident.reference}</div>
          <h1 className="page-title">{incident.title}</h1>
        </div>
        <div className="d-flex gap-2 align-items-center">
          <SeverityBadge severity={incident.severity} />
          <StatusBadge status={incident.status} />
          {!isReporter && <ColourPill colour={incident.colour} />}
        </div>
      </div>

      <div className="row g-3">
        <div className="col-lg-8">
          <div className="card mb-3">
            <div className="card-header">Report</div>
            <div className="card-body">
              <p style={{ whiteSpace: 'pre-wrap' }}>{incident.description}</p>
              <div className="row g-2">
                {details.map(([k, v]) => (
                  <div className="col-sm-6 col-md-3" key={k}>
                    <div className="small-label">{k}</div>
                    <div className="small">{v}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {isOfficer && incident.status === 'submitted' && <StartReviewCard incident={incident} onChange={load} />}
          {isOfficer && incident.status === 'under_review' && <AnalysisCard incident={incident} onChange={load} />}

          {!isReporter && incident.analysis && (
            <div className="card mb-3">
              <div className="card-header">Safety Officer analysis</div>
              <div className="card-body" style={{ whiteSpace: 'pre-wrap' }}>{incident.analysis}</div>
            </div>
          )}

          {!isReporter && <SummaryCard incident={incident} editable={isOfficer && open} onChange={load} />}
          {!isReporter && (incident.status === 'measures_pending' || incident.status === 'closed') && (
            <MeasuresCard incident={incident} editable={isOfficer && open}
                          followUp={isOfficer && incident.status === 'closed'} onChange={load} />
          )}
          {isOfficer && open && <CloseCard incident={incident} onChange={load} />}

          {incident.status === 'closed' && incident.closing_note && (
            <div className="card mb-3"><div className="card-body">
              <div className="small-label">Closing note</div>{incident.closing_note}
            </div></div>
          )}
        </div>

        <div className="col-lg-4">
          <div className="card">
            <div className="card-header">History</div>
            <div className="card-body">
              <ul className="timeline">
                {incident.history.map((h, idx) => (
                  <li key={idx}>
                    <div className="fw-semibold small">{h.from_status === h.to_status ? 'Follow-up' : humanize(h.to_status)}</div>
                    <div className="small muted">{formatDate(h.changed_at)}{h.changed_by && ` · ${h.changed_by.full_name}`}</div>
                    {h.note && <div className="small">{h.note}</div>}
                  </li>
                ))}
              </ul>
            </div>
          </div>
          {isReporter && (
            <div className="card mt-3"><div className="card-body small muted">
              <i className="bi bi-info-circle me-1" aria-hidden="true" />
              Thank you for reporting. The Safety Office reviews every report; you can follow its progress here.
            </div></div>
          )}
        </div>
      </div>
    </>
  )
}
