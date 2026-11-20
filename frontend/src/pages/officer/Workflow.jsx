import { useState } from 'react'
import { api } from '../../api'
import { ColourPill, ErrorAlert, MeasureIcon, PriorityBadge } from '../../components/ui'
import { formatDate, humanize, useTaxonomy } from '../../taxonomy'

/* Colour the incident would have with these measures (mirrors the backend rule). */
export function previewColour(measures) {
  if (!measures.length || measures.some((m) => m.status === 'pending')) return 'grey'
  if (measures.some((m) => m.priority === 'must' && m.status === 'not_applied')) return 'red'
  if (measures.some((m) => m.status === 'not_applied')) return 'yellow'
  return 'green'
}

function useAction(onDone) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const run = async (fn) => {
    setBusy(true)
    setError(null)
    try {
      await fn()
      await onDone()
      return true
    } catch (err) {
      setError(err)
      return false
    } finally {
      setBusy(false)
    }
  }
  return { busy, error, setError, run }
}

export function StartReviewCard({ incident, onChange }) {
  const { busy, error, run } = useAction(onChange)
  return (
    <div className="card mb-3 border-primary">
      <div className="card-body d-flex justify-content-between align-items-center flex-wrap gap-2">
        <div>
          <div className="fw-semibold">New report waiting for review</div>
          <div className="muted small">Starting the review assigns this incident to you.</div>
        </div>
        <button className="btn btn-primary" disabled={busy}
                onClick={() => run(() => api(`/incidents/${incident.id}/start-review`, { method: 'POST' }))}>
          <i className="bi bi-play-circle me-1" aria-hidden="true" />{busy ? 'Starting…' : 'Start review'}
        </button>
      </div>
      {error && <div className="card-body pt-0"><ErrorAlert error={error} /></div>}
    </div>
  )
}

export function AnalysisCard({ incident, onChange }) {
  const { tax } = useTaxonomy()
  const [severity, setSeverity] = useState(incident.severity || '')
  const [analysis, setAnalysis] = useState(incident.analysis || '')
  const { busy, error, run } = useAction(onChange)
  const tooShort = analysis.trim().length < 20

  return (
    <div className="card mb-3 border-primary">
      <div className="card-header"><i className="bi bi-clipboard-check me-2" aria-hidden="true" />Your analysis</div>
      <div className="card-body">
        <ErrorAlert error={error} />
        <div className="mb-3">
          <label className="form-label fw-semibold" htmlFor="severity">Severity</label>
          <select id="severity" className="form-select" value={severity} onChange={(e) => setSeverity(e.target.value)}>
            <option value="">Choose…</option>
            {tax?.severities?.map((s) => <option key={s} value={s}>{humanize(s)}</option>)}
          </select>
          <div className="form-text">Accident, serious incident or incident, as classified by AAIB India.</div>
        </div>
        <div className="mb-3">
          <label className="form-label fw-semibold" htmlFor="analysis">Analysis</label>
          <textarea id="analysis" className="form-control" rows={5} value={analysis}
                    onChange={(e) => setAnalysis(e.target.value)}
                    placeholder="What you found, likely causes and contributing factors. The AI uses this together with the report." />
          {analysis && tooShort && <div className="form-text text-danger">At least 20 characters.</div>}
        </div>
        <button className="btn btn-primary" disabled={busy || !severity || tooShort}
                onClick={() => run(() => api(`/incidents/${incident.id}/analysis`, {
                  method: 'POST', body: { severity, analysis: analysis.trim() },
                }))}>
          <i className="bi bi-stars me-1" aria-hidden="true" />{busy ? 'Submitting…' : 'Submit and get AI measures'}
        </button>
      </div>
    </div>
  )
}

export function SummaryCard({ incident, editable, onChange }) {
  const s = incident.summary
  const [editing, setEditing] = useState(false)
  const [text, setText] = useState('')
  const { busy, error, run } = useAction(onChange)
  if (!s) return null

  const post = (path) => run(() => api(`/incidents/${incident.id}/ai-summary${path}`, { method: 'POST' }))
  const badge = {
    generating: ['text-bg-info', 'Generating'], draft: ['text-bg-warning', 'Draft – needs your approval'],
    approved: ['text-bg-success', 'Approved'], discarded: ['text-bg-secondary', 'Discarded'], failed: ['text-bg-danger', 'Failed'],
  }[s.status]

  return (
    <div className="card mb-3">
      <div className="card-header d-flex justify-content-between align-items-center">
        <span><i className="bi bi-stars me-2" aria-hidden="true" />AI summary</span>
        <span className={`badge ${badge[0]}`}>{badge[1]}</span>
      </div>
      <div className="card-body">
        <ErrorAlert error={error} />
        {s.status === 'generating' && (
          <div className="d-flex align-items-center gap-2 muted">
            <span className="spinner-border spinner-border-sm" aria-hidden="true" />
            Reading the policies and drafting measures…
          </div>
        )}
        {s.status === 'failed' && (
          <div className="alert alert-warning mb-3">
            The AI could not produce a usable result: <span className="small">{s.error}</span>
            <div className="small mt-1">You can try again, or discard it and add measures yourself.</div>
          </div>
        )}
        {s.summary && !editing && <div className="summary-box mb-2">{s.summary}</div>}
        {editing && (
          <textarea className="form-control mb-2" rows={5} value={text} onChange={(e) => setText(e.target.value)} />
        )}
        {s.summary && s.status !== 'generating' && (
          <div className="small muted">
            {s.model && <>Model: {s.model} · </>}Sources: {s.citations || '—'}
            {s.error && s.status !== 'failed' && <div className="text-warning-emphasis">{s.error}</div>}
          </div>
        )}
        {editable && (
          <div className="d-flex flex-wrap gap-2 mt-3">
            {editing ? (
              <>
                <button className="btn btn-sm btn-primary" disabled={busy || text.trim().length < 10}
                        onClick={() => run(async () => {
                          await api(`/incidents/${incident.id}/ai-summary`, { method: 'PATCH', body: { summary: text.trim() } })
                          setEditing(false)
                        })}>Save</button>
                <button className="btn btn-sm btn-outline-secondary" onClick={() => setEditing(false)}>Cancel</button>
              </>
            ) : (
              <>
                {s.status === 'draft' && (
                  <button className="btn btn-sm btn-success" disabled={busy} onClick={() => post('/approve')}>
                    <i className="bi bi-check2 me-1" aria-hidden="true" />Approve
                  </button>
                )}
                {['draft', 'approved'].includes(s.status) && (
                  <button className="btn btn-sm btn-outline-primary" disabled={busy}
                          onClick={() => { setText(s.summary || ''); setEditing(true) }}>
                    <i className="bi bi-pencil me-1" aria-hidden="true" />Edit
                  </button>
                )}
                {['draft', 'failed'].includes(s.status) && (
                  <button className="btn btn-sm btn-outline-secondary" disabled={busy} onClick={() => post('/discard')}>Discard</button>
                )}
                {s.status !== 'generating' && (
                  <button className="btn btn-sm btn-outline-secondary" disabled={busy} onClick={() => post('/regenerate')}>
                    <i className="bi bi-arrow-repeat me-1" aria-hidden="true" />Regenerate
                  </button>
                )}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export function FollowUpInfo({ m }) {
  if (!m.completed_late) return null
  return (
    <div className="small mt-2 p-2 rounded" style={{ background: '#eef7ee', border: '1px solid #cfe8cf' }}>
      <div><span className="fw-semibold">Completed after closing</span> · {formatDate(m.completed_at)}{m.completed_by && ` · ${m.completed_by}`}</div>
      <div>{m.completion_note}</div>
      {m.reason && <div className="muted mt-1">Originally not applied: {m.reason}</div>}
    </div>
  )
}

function MeasureRow({ m, editable, followUp, onChange }) {
  const [reasonOpen, setReasonOpen] = useState(false)
  const [reason, setReason] = useState(m.reason || '')
  const [completeOpen, setCompleteOpen] = useState(false)
  const [note, setNote] = useState('')
  const { busy, error, run } = useAction(onChange)
  const patch = (body) => run(() => api(`/measures/${m.id}`, { method: 'PATCH', body }))

  return (
    <div className="measure-row">
      <div className="d-flex gap-3 align-items-start">
        <div className="pt-1"><MeasureIcon icon={m.icon} /></div>
        <div className="flex-grow-1">
          <div className="d-flex flex-wrap gap-2 align-items-center mb-1">
            {editable ? (
              <button className="btn p-0 border-0" title="Click to change priority" disabled={busy}
                      onClick={() => patch({ priority: m.priority === 'must' ? 'should' : 'must' })}>
                <PriorityBadge priority={m.priority} />
              </button>
            ) : <PriorityBadge priority={m.priority} />}
            {m.source === 'officer' && <span className="badge badge-soft">Added by officer</span>}
            {m.completed_late && <span className="badge text-bg-success">Completed after closing</span>}
            {m.policy_reference && <span className="small muted"><i className="bi bi-journal-text me-1" aria-hidden="true" />{m.policy_reference}</span>}
          </div>
          <div>{m.description}</div>
          {m.status === 'not_applied' && m.reason && !reasonOpen && (
            <div className="small mt-1"><span className="fw-semibold">Reason not applied:</span> {m.reason}</div>
          )}
          <FollowUpInfo m={m} />
          {completeOpen && (
            <form className="mt-2" onSubmit={(e) => {
              e.preventDefault()
              run(() => api(`/measures/${m.id}/complete`, { method: 'POST', body: { note: note.trim() } }))
                .then((ok) => ok && setCompleteOpen(false))
            }}>
              <label className="form-label small fw-semibold mb-1" htmlFor={`note-${m.id}`}>What was done? (required)</label>
              <div className="d-flex gap-2">
                <input id={`note-${m.id}`} className="form-control form-control-sm" autoFocus maxLength={1000}
                       placeholder="e.g. Part fitted on 12 Dec by R. Verma, work order WO-4471"
                       value={note} onChange={(e) => setNote(e.target.value)} />
                <button className="btn btn-sm btn-success text-nowrap" disabled={busy || note.trim().length < 5}>Mark completed</button>
                <button type="button" className="btn btn-sm btn-outline-secondary" onClick={() => setCompleteOpen(false)}>Cancel</button>
              </div>
            </form>
          )}
          {reasonOpen && (
            <form className="d-flex gap-2 mt-2" onSubmit={(e) => {
              e.preventDefault()
              patch({ status: 'not_applied', reason: reason.trim() }).then((ok) => ok && setReasonOpen(false))
            }}>
              <input className="form-control form-control-sm" autoFocus placeholder="Why is this not being applied? (required)"
                     value={reason} onChange={(e) => setReason(e.target.value)} maxLength={1000} />
              <button className="btn btn-sm btn-danger text-nowrap" disabled={busy || !reason.trim()}>Save</button>
              <button type="button" className="btn btn-sm btn-outline-secondary" onClick={() => setReasonOpen(false)}>Cancel</button>
            </form>
          )}
          {error && <div className="text-danger small mt-1">{error.message}</div>}
        </div>
        {followUp && m.status === 'not_applied' && !completeOpen && (
          <button className="btn btn-sm btn-outline-success flex-shrink-0" onClick={() => setCompleteOpen(true)}>
            <i className="bi bi-check2-circle me-1" aria-hidden="true" />Mark as completed
          </button>
        )}
        {editable && !reasonOpen && (
          <div className="btn-group btn-group-sm flex-shrink-0" role="group" aria-label="Mark measure">
            <button className={`btn ${m.status === 'applied' ? 'btn-success' : 'btn-outline-success'}`} disabled={busy}
                    onClick={() => patch({ status: 'applied' })}>Applied</button>
            <button className={`btn ${m.status === 'not_applied' ? 'btn-danger' : 'btn-outline-danger'}`} disabled={busy}
                    onClick={() => setReasonOpen(true)}>Not applied</button>
            {m.status !== 'pending' && (
              <button className="btn btn-outline-secondary" title="Reset to pending" disabled={busy}
                      onClick={() => patch({ status: 'pending' })}>
                <i className="bi bi-arrow-counterclockwise" aria-hidden="true" /><span className="visually-hidden">Reset</span>
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export function MeasuresCard({ incident, editable, followUp = false, onChange }) {
  const [desc, setDesc] = useState('')
  const [priority, setPriority] = useState('should')
  const { busy, error, run } = useAction(onChange)
  const ms = incident.measures
  const must = ms.filter((m) => m.priority === 'must')
  const should = ms.filter((m) => m.priority === 'should')
  const pending = ms.filter((m) => m.status === 'pending').length

  return (
    <div className="card mb-3">
      <div className="card-header d-flex justify-content-between align-items-center flex-wrap gap-2">
        <span><i className="bi bi-list-check me-2" aria-hidden="true" />Measures</span>
        <span className="d-flex gap-2 align-items-center">
          {ms.length > 0 && <span className="small muted">{ms.length - pending}/{ms.length} decided</span>}
          <ColourPill colour={incident.colour} />
        </span>
      </div>
      <div className="card-body pt-1">
        {followUp && ms.some((m) => m.status === 'not_applied') && (
          <div className="alert alert-info py-2 small mt-2 mb-1">
            <i className="bi bi-info-circle me-1" aria-hidden="true" />
            This incident is closed. If a measure that was not applied has since been carried out, mark it as completed.
            The incident stays closed and the original reason is kept.
          </div>
        )}
        {ms.length === 0 && <div className="muted py-3">No measures yet.{editable && ' Add one below, or regenerate the AI suggestions.'}</div>}
        {must.length > 0 && <div className="small-label mt-2">Must be done</div>}
        {must.map((m) => <MeasureRow key={m.id} m={m} editable={editable} followUp={followUp} onChange={onChange} />)}
        {should.length > 0 && <div className="small-label mt-3">Should be done</div>}
        {should.map((m) => <MeasureRow key={m.id} m={m} editable={editable} followUp={followUp} onChange={onChange} />)}

        {editable && (
          <form className="mt-3 pt-3 border-top" onSubmit={(e) => {
            e.preventDefault()
            run(async () => {
              await api(`/incidents/${incident.id}/measures`, { method: 'POST', body: { description: desc.trim(), priority } })
              setDesc('')
            })
          }}>
            <div className="small-label mb-2">Add your own measure</div>
            <ErrorAlert error={error} />
            <div className="d-flex gap-2 flex-wrap">
              <input className="form-control flex-grow-1" style={{ minWidth: 240 }} placeholder="Describe the measure"
                     value={desc} onChange={(e) => setDesc(e.target.value)} maxLength={1000} />
              <select className="form-select w-auto" value={priority} onChange={(e) => setPriority(e.target.value)} aria-label="Priority">
                <option value="must">Must</option>
                <option value="should">Should</option>
              </select>
              <button className="btn btn-outline-primary" disabled={busy || desc.trim().length < 5}>Add</button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}

export function CloseCard({ incident, onChange }) {
  const [note, setNote] = useState('')
  const { busy, error, run } = useAction(onChange)
  const ms = incident.measures
  const pending = ms.filter((m) => m.status === 'pending').length
  const summaryOpen = ['draft', 'generating'].includes(incident.summary?.status)
  const blockers = []
  if (!ms.length) blockers.push('Add at least one measure.')
  if (pending) blockers.push(`${pending} measure${pending > 1 ? 's' : ''} still pending.`)
  if (summaryOpen) blockers.push('Approve or discard the AI summary.')
  const result = previewColour(ms)

  return (
    <div className="card mb-3">
      <div className="card-header"><i className="bi bi-flag me-2" aria-hidden="true" />Close incident</div>
      <div className="card-body">
        <ErrorAlert error={error} />
        {blockers.length > 0 ? (
          <ul className="mb-0 small">{blockers.map((b) => <li key={b}>{b}</li>)}</ul>
        ) : (
          <>
            <div className="mb-2 small">This incident will close as <ColourPill colour={result} long />.</div>
            {result === 'red' && (
              <div className="alert alert-danger py-2 small">
                A mandatory measure is not applied. The incident can close, but it stays red on the admin panel.
              </div>
            )}
            <textarea className="form-control mb-2" rows={2} placeholder="Closing note (optional)"
                      value={note} onChange={(e) => setNote(e.target.value)} maxLength={2000} />
            <button className="btn btn-primary" disabled={busy}
                    onClick={() => run(() => api(`/incidents/${incident.id}/close`, {
                      method: 'POST', body: { closing_note: note.trim() || null },
                    }))}>
              {busy ? 'Closing…' : 'Close incident'}
            </button>
          </>
        )}
      </div>
    </div>
  )
}
