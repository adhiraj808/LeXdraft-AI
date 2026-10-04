import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'
import { Icon } from './Icons'

const navItems = [
  { icon: 'Folder', label: 'My Cases', href: '/cases' },
  { icon: 'New', label: 'New Case (Form)', href: '/cases/new' },
  { icon: 'Sparkles', label: 'New Case (Chat)', href: '/cases/newchat' },
]

export function timeAgo(iso) {
  if (!iso) return ''
  const s = Math.max(1, Math.floor((Date.now() - new Date(iso).getTime()) / 1000))
  if (s < 60) return 'Just now'
  const m = Math.floor(s / 60)
  if (m < 60) return m + 'm ago'
  const h = Math.floor(m / 60)
  if (h < 24) return h + 'h ago'
  const d = Math.floor(h / 24)
  if (d < 30) return d === 1 ? 'Yesterday' : d + 'd ago'
  return new Date(iso).toLocaleDateString()
}

export function Sidebar({ isOpen, onClose, onNavigate, recents }) {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, logout } = useAuth()

  const go = (href) => {
    if (onNavigate) onNavigate(href)
    else navigate(href)
    if (onClose && typeof window !== 'undefined' && window.innerWidth < 900) onClose()
  }

  const initials = ((user && (user.full_name || user.username)) || 'AD')
    .split(' ')
    .map((w) => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()

  return (
    <aside className={'chat-sidebar' + (isOpen ? ' open' : '')}>
      <div className="brand">
        <div className="brand-mark">
          <svg width="20" height="20" viewBox="0 0 28 28" fill="none" aria-hidden="true">
            <path d="M14 5L6 10v3h16v-3L14 5z" fill="currentColor" />
            <rect x="7" y="14" width="2" height="7" fill="currentColor" opacity="0.7" />
            <rect x="13" y="14" width="2" height="7" fill="currentColor" opacity="0.7" />
            <rect x="19" y="14" width="2" height="7" fill="currentColor" opacity="0.7" />
            <rect x="5" y="21" width="18" height="2" rx="1" fill="currentColor" />
          </svg>
        </div>
        <div className="brand-type">
          <span className="brand-name">LEXDRAFT</span>
          <span className="brand-subtitle">LEGAL INTELLIGENCE</span>
        </div>
      </div>

      <button className="new-chat-button" type="button" onClick={() => go('/cases/newchat')}>
        <Icon name="New" size={16} />
        <span>New conversation</span>
      </button>

      <nav className="main-nav" aria-label="Primary">
        <span className="nav-label">WORKSPACE</span>
        {navItems.map((item) => (
          <Link
            className={'nav-item' + (location.pathname === item.href ? ' active' : '')}
            key={item.label}
            to={item.href}
            onClick={(e) => { e.preventDefault(); go(item.href) }}
          >
            <Icon name={item.icon} size={16} />
            <span>{item.label}</span>
          </Link>
        ))}
      </nav>

      <section className="history">
        <div className="section-heading">
          <span>RECENT DRAFTS</span>
        </div>
        {(!recents || recents.length === 0) ? (
          <div className="history-empty">No drafts yet — send your first prompt.</div>
        ) : (
          recents.map((c) => (
            <button
              className="history-item"
              key={c.id}
              type="button"
              title={c.title}
              onClick={() => {
                navigate('/cases/' + c.id)
                if (onClose && typeof window !== 'undefined' && window.innerWidth < 900) onClose()
              }}
            >
              <span>{c.title}</span>
              <small>{timeAgo(c.created_at)}{c.status && c.status !== 'completed' ? ' · ' + c.status : ''}</small>
            </button>
          ))
        )}
      </section>

      <div className="sidebar-footer">
        <button
          className="profile"
          type="button"
          onClick={() => { logout(); navigate('/login') }}
          title="Sign out"
        >
          <span className="avatar">{initials}</span>
          <span className="profile-copy">
            <strong>{(user && (user.full_name || user.username)) || 'Counsel'}</strong>
            <small>{(user && user.role) || 'advocate'}</small>
          </span>
        </button>
      </div>
    </aside>
  )
}

export function SidebarTrigger({ onOpen }) {
  return (
    <button className="sidebar-trigger-btn" onClick={onOpen} aria-label="Open menu" type="button">
      &#9776;
    </button>
  )
}

export function SidebarOverlay({ isOpen, onClose }) {
  if (!isOpen) return null
  return <div className="sidebar-overlay show" onClick={onClose} />
}
