import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { useTheme } from '../hooks/useTheme'
import { Sun, Moon } from 'lucide-react'

const NAV = [
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/cases/new',  label: 'New Draft'  },
  { to: '/cases',      label: 'My Cases'   },
]

export default function Layout({ children }) {
  const { user, logout } = useAuth()
  const { isDark, toggleTheme } = useTheme()
  const location = useLocation()
  const navigate = useNavigate()

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header-inner">
          <Link to="/dashboard" className="brand">
            <div className="brand-icon">
              <svg width="24" height="24" viewBox="0 0 28 28" fill="none">
                <path d="M14 5L6 10v3h16v-3L14 5z" fill="currentColor"/>
                <rect x="7" y="14" width="2" height="7" fill="currentColor" opacity="0.7"/>
                <rect x="13" y="14" width="2" height="7" fill="currentColor" opacity="0.7"/>
                <rect x="19" y="14" width="2" height="7" fill="currentColor" opacity="0.7"/>
                <rect x="5" y="21" width="18" height="2" rx="1" fill="currentColor"/>
              </svg>
            </div>
            <span className="brand-name">
              Lex<span className="brand-accent">Draft</span> AI
            </span>
          </Link>

          <nav className="main-nav">
            {NAV.map(({ to, label }) => {
              const active = location.pathname === to
              return (
                <Link
                  key={to}
                  to={to}
                  className={`nav-link ${active ? 'active' : ''}`}
                >
                  {label}
                </Link>
              )
            })}
          </nav>

          <div className="header-actions">
            <button onClick={toggleTheme} className="theme-toggle" aria-label="Toggle theme">
              {isDark ? <Sun size={18} /> : <Moon size={18} />}
            </button>
            <div className="user-info">
              <div className="user-name">{user?.full_name || user?.username}</div>
              <div className="user-role font-mono">{user?.role}</div>
            </div>
            <button
              onClick={() => { logout(); navigate('/login') }}
              className="signout-btn"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>

      <main className="app-main animate-fade-up">
        {children}
      </main>

      <footer className="app-footer">
        LexDraft AI — Academic Use Only — Not Legal Advice
      </footer>
    </div>
  )
}
