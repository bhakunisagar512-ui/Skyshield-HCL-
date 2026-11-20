import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { ROLE_LABELS, useAuth } from '../auth'

const NAV = {
  reporter: [
    ['/report/new', 'New report', 'bi-plus-circle'],
    ['/incidents', 'My reports', 'bi-list-ul'],
  ],
  safety_officer: [
    ['/incidents', 'Incident queue', 'bi-inboxes'],
    ['/dashboard', 'Dashboard', 'bi-bar-chart'],
    ['/report/new', 'New report', 'bi-plus-circle'],
  ],
  admin: [
    ['/admin', 'Overview', 'bi-shield-check'],
    ['/dashboard', 'Dashboard', 'bi-bar-chart'],
    ['/admin/users', 'Users', 'bi-people'],
    ['/policies', 'Policies', 'bi-journal-text'],
  ],
}

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const links = NAV[user.role] || []

  return (
    <>
      <nav className="navbar navbar-expand-md navbar-dark sky-navbar">
        <div className="container-xl">
          <span className="navbar-brand sky-brand">
            <i className="bi bi-shield-fill-check me-2" aria-hidden="true" />SkyShield
          </span>
          <button className="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#nav"
                  aria-controls="nav" aria-expanded="false" aria-label="Toggle navigation"
                  onClick={() => document.getElementById('nav')?.classList.toggle('show')}>
            <span className="navbar-toggler-icon" />
          </button>
          <div className="collapse navbar-collapse" id="nav">
            <ul className="navbar-nav me-auto">
              {links.map(([to, label, icon]) => (
                <li className="nav-item" key={to}>
                  <NavLink to={to} end={to === '/admin'} className="nav-link">
                    <i className={`bi ${icon} me-1`} aria-hidden="true" />{label}
                  </NavLink>
                </li>
              ))}
            </ul>
            <div className="d-flex align-items-center gap-3 text-white">
              <div className="text-end lh-sm">
                <div className="small fw-semibold">{user.full_name}</div>
                <div className="small opacity-75">{ROLE_LABELS[user.role]}</div>
              </div>
              <button className="btn btn-sm btn-outline-light" onClick={() => { logout(); navigate('/login') }}>
                <i className="bi bi-box-arrow-right me-1" aria-hidden="true" />Log out
              </button>
            </div>
          </div>
        </div>
      </nav>
      <main className="container-xl py-4">
        <Outlet />
      </main>
    </>
  )
}
