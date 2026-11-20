import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api'
import { useAuth } from '../auth'
import { ErrorAlert, Spinner } from '../components/ui'
import { humanize, useTaxonomy } from '../taxonomy'

const SERIES = '#2a78d6' // single-series charts: one hue, the title names the series
const AXIS = { fontSize: 12, fill: '#52514e' }
const GRID = '#e6e5e1'
const STATUS = { red: '#d03b3b', yellow: '#fab219', grey: '#8a8984', green: '#0ca30c' }
const STATUS_LABEL = { red: 'Red', yellow: 'Yellow', grey: 'In progress', green: 'Green' }

function ChartTip({ active, payload, label, unit = 'incidents' }) {
  if (!active || !payload?.length) return null
  return (
    <div className="chart-tooltip">
      <div className="fw-semibold">{label}</div>
      <div>{payload[0].value} {unit}</div>
    </div>
  )
}

function Tile({ label, value, sub, icon }) {
  return (
    <div className="card stat-tile h-100">
      <div className="card-body">
        <div className="small-label">{icon && <i className={`bi ${icon} me-1`} aria-hidden="true" />}{label}</div>
        <div className="value mt-1">{value}</div>
        {sub && <div className="small muted">{sub}</div>}
      </div>
    </div>
  )
}

function ChartCard({ title, children, table }) {
  const [showTable, setShowTable] = useState(false)
  return (
    <div className="card h-100">
      <div className="card-header d-flex justify-content-between align-items-center">
        <span>{title}</span>
        <button className="btn btn-sm btn-link p-0" onClick={() => setShowTable((s) => !s)}>{showTable ? 'Chart' : 'Table'}</button>
      </div>
      <div className="card-body">
        {showTable ? (
          <table className="table table-sm mb-0">
            <tbody>{table.map(([k, v]) => <tr key={k}><td>{k}</td><td className="text-end">{v}</td></tr>)}</tbody>
          </table>
        ) : children}
      </div>
    </div>
  )
}

export default function Dashboard() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const { categoryLabel, airportLabel } = useTaxonomy()
  const [s, setS] = useState(null)
  const [error, setError] = useState(null)
  useEffect(() => { api('/dashboard/stats').then(setS).catch(setError) }, [])

  if (error) return <ErrorAlert error={error} />
  if (!s) return <Spinner />

  const open = s.total_incidents - (s.by_status.find((x) => x.key === 'closed')?.count || 0)
  const months = s.by_month.map((m) => ({
    label: new Date(`${m.key}-01T00:00:00`).toLocaleDateString('en-IN', { month: 'short', year: '2-digit' }),
    count: m.count,
  }))
  const cats = s.by_category.map((c) => ({ label: categoryLabel(c.key), count: c.count }))
  const colours = ['red', 'yellow', 'grey', 'green'].map((k) => ({ key: k, label: STATUS_LABEL[k], count: s.colours[k] || 0 }))
  const sevOrder = ['accident', 'serious_incident', 'incident', 'unclassified']
  const sev = sevOrder.map((k) => ({ label: humanize(k), count: s.by_severity.find((x) => x.key === k)?.count || 0 }))
  const airports = s.top_airports.map((a) => ({ label: airportLabel(a.key).split(' (')[0], count: a.count }))
  const goColour = (key) => navigate(user.role === 'admin' ? `/admin?colour=${key}` : `/incidents?colour=${key}`)

  return (
    <>
      <h1 className="page-title mb-3">Safety dashboard</h1>
      <div className="row g-3 mb-3">
        <div className="col-6 col-lg-3"><Tile label="Total incidents" value={s.total_incidents} icon="bi-collection" /></div>
        <div className="col-6 col-lg-3"><Tile label="Open" value={open} sub="not yet closed" icon="bi-hourglass-split" /></div>
        <div className="col-6 col-lg-3">
          <Tile label="Mandatory not applied" value={s.measures.must_not_applied} sub={`${s.colours.red || 0} red incidents`} icon="bi-x-circle" />
        </div>
        <div className="col-6 col-lg-3">
          <Tile label="Measures applied" value={s.measures.applied_rate == null ? '—' : `${Math.round(s.measures.applied_rate * 100)}%`}
                sub={`of ${s.measures.total - s.measures.pending} decided`} icon="bi-check2-circle" />
        </div>
      </div>

      <div className="row g-3">
        <div className="col-lg-8">
          <ChartCard title="Incidents per month (last 12 months)" table={months.map((m) => [m.label, m.count])}>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={months} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
                <CartesianGrid vertical={false} stroke={GRID} />
                <XAxis dataKey="label" tick={AXIS} tickLine={false} axisLine={{ stroke: GRID }} interval="preserveStartEnd" />
                <YAxis allowDecimals={false} tick={AXIS} tickLine={false} axisLine={false} />
                <Tooltip content={<ChartTip />} cursor={{ fill: 'rgba(42,120,214,0.08)' }} />
                <Bar dataKey="count" fill={SERIES} radius={[4, 4, 0, 0]} maxBarSize={36} />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        </div>
        <div className="col-lg-4">
          <ChartCard title="Incident colour" table={colours.map((c) => [c.label, c.count])}>
            <div className="d-flex flex-column gap-2">
              {colours.map((c) => {
                const total = colours.reduce((a, b) => a + b.count, 0) || 1
                return (
                  <button key={c.key} className="btn btn-light text-start p-2 border" onClick={() => goColour(c.key)}>
                    <div className="d-flex justify-content-between small mb-1">
                      <span className={`colour-pill colour-${c.key}`}><span className="dot" aria-hidden="true" />{c.label}</span>
                      <span className="fw-semibold">{c.count}</span>
                    </div>
                    <div className="progress" style={{ height: 8 }} role="progressbar" aria-label={`${c.label} share`}
                         aria-valuenow={Math.round((c.count / total) * 100)} aria-valuemin={0} aria-valuemax={100}>
                      <div className="progress-bar" style={{ width: `${(c.count / total) * 100}%`, background: STATUS[c.key] }} />
                    </div>
                  </button>
                )
              })}
              <div className="small muted">Click a colour to see those incidents.</div>
            </div>
          </ChartCard>
        </div>
        <div className="col-lg-6">
          <ChartCard title="Incidents by category" table={cats.map((c) => [c.label, c.count])}>
            <ResponsiveContainer width="100%" height={Math.max(220, cats.length * 28)}>
              <BarChart data={cats} layout="vertical" margin={{ top: 0, right: 16, left: 8, bottom: 0 }}>
                <CartesianGrid horizontal={false} stroke={GRID} />
                <XAxis type="number" allowDecimals={false} tick={AXIS} tickLine={false} axisLine={false} />
                <YAxis type="category" dataKey="label" width={235} tick={AXIS} tickLine={false} axisLine={false} interval={0} />
                <Tooltip content={<ChartTip />} cursor={{ fill: 'rgba(42,120,214,0.08)' }} />
                <Bar dataKey="count" fill={SERIES} radius={[0, 4, 4, 0]} barSize={14} />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        </div>
        <div className="col-lg-6 d-flex flex-column gap-3">
          <ChartCard title="Incidents by severity" table={sev.map((x) => [x.label, x.count])}>
            <ResponsiveContainer width="100%" height={170}>
              <BarChart data={sev} layout="vertical" margin={{ top: 0, right: 16, left: 8, bottom: 0 }}>
                <CartesianGrid horizontal={false} stroke={GRID} />
                <XAxis type="number" allowDecimals={false} tick={AXIS} tickLine={false} axisLine={false} />
                <YAxis type="category" dataKey="label" width={130} tick={AXIS} tickLine={false} axisLine={false} />
                <Tooltip content={<ChartTip />} cursor={{ fill: 'rgba(42,120,214,0.08)' }} />
                <Bar dataKey="count" radius={[0, 4, 4, 0]} barSize={16}>
                  {sev.map((x) => <Cell key={x.label} fill={SERIES} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
          <ChartCard title="Top airports" table={airports.map((a) => [a.label, a.count])}>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={airports} layout="vertical" margin={{ top: 0, right: 16, left: 8, bottom: 0 }}>
                <CartesianGrid horizontal={false} stroke={GRID} />
                <XAxis type="number" allowDecimals={false} tick={AXIS} tickLine={false} axisLine={false} />
                <YAxis type="category" dataKey="label" width={200} tick={AXIS} tickLine={false} axisLine={false} interval={0} />
                <Tooltip content={<ChartTip />} cursor={{ fill: 'rgba(42,120,214,0.08)' }} />
                <Bar dataKey="count" fill={SERIES} radius={[0, 4, 4, 0]} barSize={14} />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        </div>
      </div>
    </>
  )
}
