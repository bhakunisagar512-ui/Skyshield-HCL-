import { humanize } from '../taxonomy'

const COLOUR_TEXT = {
  green: 'All measures applied',
  yellow: 'Recommended measure open',
  red: 'Mandatory measure not applied',
  grey: 'In progress',
}
const COLOUR_SHORT = { green: 'Green', yellow: 'Yellow', red: 'Red', grey: 'In progress' }

export function ColourPill({ colour, long = false }) {
  return (
    <span className={`colour-pill colour-${colour}`} title={COLOUR_TEXT[colour]}>
      <span className="dot" aria-hidden="true" />
      {long ? COLOUR_TEXT[colour] : COLOUR_SHORT[colour]}
    </span>
  )
}

const STATUS_STYLE = {
  submitted: 'text-bg-light border',
  under_review: 'text-bg-info',
  measures_pending: 'text-bg-warning',
  closed: 'text-bg-secondary',
}
export function StatusBadge({ status }) {
  return <span className={`badge ${STATUS_STYLE[status] || 'text-bg-light'}`}>{humanize(status)}</span>
}

const SEV_ICON = { accident: 'bi-exclamation-octagon', serious_incident: 'bi-exclamation-triangle', incident: 'bi-info-circle' }
export function SeverityBadge({ severity }) {
  if (!severity) return <span className="muted small">Not classified</span>
  return (
    <span className="badge badge-soft">
      <i className={`bi ${SEV_ICON[severity]} me-1`} aria-hidden="true" />
      {humanize(severity)}
    </span>
  )
}

export function PriorityBadge({ priority }) {
  return <span className={`badge ${priority === 'must' ? 'badge-must' : 'badge-should'}`}>{priority === 'must' ? 'MUST' : 'SHOULD'}</span>
}

const ICONS = {
  tick: ['bi-check-circle-fill', 'Applied'],
  exclamation: ['bi-exclamation-circle-fill', 'Recommended, not applied'],
  cross: ['bi-x-circle-fill', 'Mandatory, not applied'],
  pending: ['bi-circle', 'Pending'],
}
export function MeasureIcon({ icon, withLabel = false }) {
  const [cls, label] = ICONS[icon] || ICONS.pending
  return (
    <span className="d-inline-flex align-items-center gap-1" title={label}>
      <i className={`bi ${cls} measure-icon ${icon}`} aria-hidden="true" />
      {withLabel ? <span className="small">{label}</span> : <span className="visually-hidden">{label}</span>}
    </span>
  )
}

export function Spinner({ label = 'Loading…' }) {
  return (
    <div className="d-flex align-items-center gap-2 muted py-4 justify-content-center">
      <span className="spinner-border spinner-border-sm" role="status" aria-hidden="true" />
      {label}
    </div>
  )
}

export function ErrorAlert({ error, onClose }) {
  if (!error) return null
  return (
    <div className="alert alert-danger d-flex justify-content-between align-items-start" role="alert">
      <span><i className="bi bi-exclamation-triangle me-2" aria-hidden="true" />{error.message || String(error)}</span>
      {onClose && <button type="button" className="btn-close" aria-label="Close" onClick={onClose} />}
    </div>
  )
}

export function Pagination({ page, pageSize, total, onChange }) {
  const pages = Math.max(1, Math.ceil(total / pageSize))
  if (pages <= 1) return null
  return (
    <div className="d-flex justify-content-between align-items-center mt-3">
      <span className="muted small">Page {page} of {pages} · {total} incidents</span>
      <div className="btn-group">
        <button className="btn btn-sm btn-outline-secondary" disabled={page <= 1} onClick={() => onChange(page - 1)}>Previous</button>
        <button className="btn btn-sm btn-outline-secondary" disabled={page >= pages} onClick={() => onChange(page + 1)}>Next</button>
      </div>
    </div>
  )
}

export function Field({ label, error, children, hint }) {
  return (
    <div className="mb-3">
      <label className="form-label fw-semibold">{label}</label>
      {children}
      {hint && !error && <div className="form-text">{hint}</div>}
      {error && <div className="invalid-feedback d-block">{error}</div>}
    </div>
  )
}
