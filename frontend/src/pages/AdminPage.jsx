import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import toast from 'react-hot-toast'
import Layout from '../components/Layout'
import StatusBadge from '../components/StatusBadge'
import { adminAPI } from '../services/api'
import { useAuth } from '../hooks/useAuth'
import { Users, FileText, RefreshCw, Trash2, Play, Shield } from 'lucide-react'

function timeStr(iso) {
  if (!iso) return '-'
  try { return new Date(iso).toLocaleString() } catch { return iso }
}

export default function AdminPage() {
  const { user } = useAuth()
  const [tab, setTab] = useState('cases')
  const [cases, setCases] = useState([])
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [forbidden, setForbidden] = useState(false)

  const fetchAll = useCallback(async () => {
    setLoading(true)
    setForbidden(false)
    try {
      const [c, u] = await Promise.all([adminAPI.cases(), adminAPI.users()])
      setCases(c.data || [])
      setUsers(u.data || [])
    } catch (err) {
      if (err.response?.status === 403) setForbidden(true)
      else toast.error('Failed to load admin data')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchAll() }, [fetchAll])

  const doDeleteCase = async (id, title) => {
    if (!window.confirm(`Delete case "${title}" and its draft?`)) return
    try {
      await adminAPI.deleteCase(id)
      toast.success('Case deleted')
      setCases((cur) => cur.filter((c) => c.id !== id))
    } catch { toast.error('Delete failed') }
  }

  const doReprocess = async (id) => {
    try {
      await adminAPI.reprocess(id)
      toast.success('Queued again — refresh in a minute')
      setCases((cur) => cur.map((c) => (c.id === id ? { ...c, status: 'pending', has_draft: c.has_draft } : c)))
    } catch { toast.error('Reprocess failed') }
  }

  const doDeleteUser = async (id, username) => {
    if (!window.confirm(`Delete user "${username}" AND all their cases?`)) return
    try {
      await adminAPI.deleteUser(id)
      toast.success('User deleted')
      fetchAll()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Delete failed')
    }
  }

  const doSetRole = async (id, username, role) => {
    try {
      await adminAPI.setRole(id, role)
      toast.success(`${username} is now ${role}`)
      fetchAll()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Role change failed')
    }
  }

  if (forbidden) {
    return (
      <Layout>
        <div className="not-found-box">
          <h2>Admins only</h2>
          <p>Your account ({user?.username}, role: {user?.role}) cannot open this page.</p>
        </div>
      </Layout>
    )
  }

  return (
    <Layout>
      <div className="list-page-header">
        <div>
          <h1>Admin — Data Explorer</h1>
          <p className="list-page-count">
            <strong>{users.length}</strong> users &nbsp;·&nbsp; <strong>{cases.length}</strong> cases (all accounts)
          </p>
        </div>
        <button className="toolbar-btn" onClick={fetchAll} disabled={loading}>
          <RefreshCw size={16} /> Refresh
        </button>
      </div>

      <div className="toolbar" role="tablist" aria-label="Admin sections">
        <button className={`toolbar-btn${tab === 'cases' ? ' active-tab' : ''}`} onClick={() => setTab('cases')} role="tab">
          <FileText size={16} /> Cases ({cases.length})
        </button>
        <button className={`toolbar-btn${tab === 'users' ? ' active-tab' : ''}`} onClick={() => setTab('users')} role="tab">
          <Users size={16} /> Users ({users.length})
        </button>
      </div>

      {loading ? (
        <div className="skeleton-list"><div className="skeleton-row" /><div className="skeleton-row" /><div className="skeleton-row" /></div>
      ) : tab === 'cases' ? (
        <div className="case-list">
          {cases.length === 0 && <div className="empty-state"><p className="empty-body">No cases yet.</p></div>}
          {cases.map((c) => (
            <div className="case-row" key={c.id}>
              <div className="case-row-info">
                <div className="case-row-title">{c.title}</div>
                <div className="case-row-meta">
                  <span>{c.user_email}</span><span className="case-row-dot" />
                  <span>{c.case_type || '—'}</span><span className="case-row-dot" />
                  <span>{c.model_used || 'no draft'}</span><span className="case-row-dot" />
                  <span>{timeStr(c.created_at)}</span>
                </div>
              </div>
              <div className="case-row-badges"><StatusBadge status={c.status} /></div>
              <div className="case-row-actions">
                <Link className="btn-outline" to={`/cases/${c.id}`}>Open</Link>
                {(c.status === 'failed' || c.status === 'processing') && (
                  <button className="toolbar-btn" title="Reset to pending + process again" onClick={() => doReprocess(c.id)}>
                    <Play size={14} /> Retry
                  </button>
                )}
                <button className="btn-icon" title="Delete case + draft" onClick={() => doDeleteCase(c.id, c.title)}>
                  <Trash2 size={16} />
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="case-list">
          {users.map((u) => (
            <div className="case-row" key={u.id}>
              <div className="case-row-info">
                <div className="case-row-title">{u.username} {u.role === 'admin' && <Shield size={14} />}</div>
                <div className="case-row-meta">
                  <span>{u.email}</span><span className="case-row-dot" />
                  <span>{u.role}</span><span className="case-row-dot" />
                  <span>{u.case_count} cases</span><span className="case-row-dot" />
                  <span>{timeStr(u.created_at)}</span>
                </div>
              </div>
              <div className="case-row-actions">
                {u.role !== 'admin' ? (
                  <button className="btn-outline" onClick={() => doSetRole(u.id, u.username, 'admin')}>Make admin</button>
                ) : (
                  u.username !== user?.username && (
                    <button className="btn-outline" onClick={() => doSetRole(u.id, u.username, 'advocate')}>Remove admin</button>
                  )
                )}
                {u.username !== user?.username && (
                  <button className="btn-icon" title="Delete user + all their cases" onClick={() => doDeleteUser(u.id, u.username)}>
                    <Trash2 size={16} />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </Layout>
  )
}
