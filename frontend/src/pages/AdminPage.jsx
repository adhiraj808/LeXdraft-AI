import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import toast from 'react-hot-toast'
import Layout from '../components/Layout'
import StatusBadge from '../components/StatusBadge'
import { adminAPI } from '../services/api'
import { useAuth } from '../hooks/useAuth'
import { 
  Users, 
  FileText, 
  RefreshCw, 
  Trash2, 
  Play, 
  Shield, 
  ToggleLeft,
  Plus,
  Settings,
  Trash,
  Eye,
  Search,
  ChevronDown,
  ChevronUp,
  X
} from 'lucide-react'

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
  const [searchQuery, setSearchQuery] = useState('')
  const [aiConfig, setAiConfig] = useState(null)
  const [aiConfigLoading, setAiConfigLoading] = useState(true)
  const [showAddModel, setShowAddModel] = useState(false)
  const [newModel, setNewModel] = useState({ id: '', label: '', provider: '' })

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

  const fetchAiConfig = useCallback(async () => {
    setAiConfigLoading(true)
    try {
      const res = await adminAPI.status()
      setAiConfig(res.data)
    } catch (err) {
      console.error('Failed to load AI config:', err)
    } finally {
      setAiConfigLoading(false)
    }
  }, [])

  useEffect(() => { 
    fetchAll()
    fetchAiConfig()
  }, [fetchAll, fetchAiConfig])

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

  const toggleLLM = async () => {
    try {
      const res = await adminAPI.toggleLLM()
      setAiConfig(prev => ({ ...prev, enabled: res.data.enabled }))
      toast.success(`LLM ${res.data.enabled ? 'enabled' : 'disabled'}`)
    } catch { toast.error('Failed to toggle LLM') }
  }

  const setDefaultModel = async (modelId) => {
    try {
      await adminAPI.setModel(modelId)
      setAiConfig(prev => ({ ...prev, model: modelId }))
      toast.success(`Default model set to ${modelId}`)
    } catch { toast.error('Failed to set model') }
  }

  const addModel = async (e) => {
    e.preventDefault()
    if (!newModel.id || !newModel.label || !newModel.provider) {
      toast.error('All fields required')
      return
    }
    try {
      await adminAPI.addModel(newModel)
      const res = await adminAPI.getModels()
      const aiConfigRes = await adminAPI.status()
      setAiConfig(aiConfigRes.data)
      setShowAddModel(false)
      setNewModel({ id: '', label: '', provider: '' })
      toast.success('Model added')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to add model')
    }
  }

  const deleteModel = async (modelId) => {
    if (!window.confirm(`Remove model "${modelId}"?`)) return
    try {
      await adminAPI.deleteModel(modelId)
      const res = await adminAPI.getModels()
      const aiConfigRes = await adminAPI.status()
      setAiConfig(aiConfigRes.data)
      toast.success('Model removed')
    } catch { toast.error('Failed to remove model') }
  }

  const filteredCases = cases.filter(c => 
    c.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    c.user_email.toLowerCase().includes(searchQuery.toLowerCase()) ||
    c.case_type?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    c.model_used?.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const filteredUsers = users.filter(u => 
    u.username.toLowerCase().includes(searchQuery.toLowerCase()) ||
    u.email.toLowerCase().includes(searchQuery.toLowerCase()) ||
    u.role.toLowerCase().includes(searchQuery.toLowerCase())
  )

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
          <h1>Admin — System Control</h1>
          <p className="list-page-count">
            <strong>{users.length}</strong> users &nbsp;·&nbsp; <strong>{cases.length}</strong> cases (all accounts)
          </p>
        </div>
        <button className="toolbar-btn" onClick={fetchAll} disabled={loading}>
          <RefreshCw size={16} /> Refresh
        </button>
      </div>

      <div className="toolbar" role="tablist" aria-label="Admin sections">
        <button className={`toolbar-btn${tab === 'cases' ? ' active-tab' : ''}`} onClick={() => { setTab('cases'); setSearchQuery(''); }} role="tab">
          <FileText size={16} /> Cases ({filteredCases.length})
        </button>
        <button className={`toolbar-btn${tab === 'users' ? ' active-tab' : ''}`} onClick={() => { setTab('users'); setSearchQuery(''); }} role="tab">
          <Users size={16} /> Users ({filteredUsers.length})
        </button>
        <button className={`toolbar-btn${tab === 'ai' ? ' active-tab' : ''}`} onClick={() => { setTab('ai'); setSearchQuery(''); }} role="tab">
          <Settings size={16} /> AI Config
        </button>
      </div>

      <div className="search-bar" style={{ marginBottom: '1rem' }}>
        <Search size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-faint)' }} />
        <input
          type="text"
          placeholder={`Search ${tab}...`}
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="search-input"
          style={{ paddingLeft: '36px' }}
        />
        {searchQuery && (
          <button className="clear-search" onClick={() => setSearchQuery('')} aria-label="Clear search">
            <X size={16} />
          </button>
        )}
      </div>

      {loading ? (
        <div className="skeleton-list"><div className="skeleton-row" /><div className="skeleton-row" /><div className="skeleton-row" /></div>
      ) : tab === 'cases' ? (
        <div className="case-list">
          {filteredCases.length === 0 && <div className="empty-state"><p className="empty-body">No cases found.</p></div>}
          {filteredCases.map((c) => (
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
      ) : tab === 'users' ? (
        <div className="case-list">
          {filteredUsers.length === 0 && <div className="empty-state"><p className="empty-body">No users found.</p></div>}
          {filteredUsers.map((u) => (
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
      ) : (
        <div className="ai-config-panel">
          {/* AI System Status */}
          <div className="ai-config-section">
            <div className="section-header">
              <h3><Settings size={20} /> AI System Status</h3>
              <button className="toolbar-btn" onClick={fetchAiConfig} disabled={aiConfigLoading}>
                <RefreshCw size={16} /> Refresh
              </button>
            </div>

            {aiConfigLoading ? (
              <div className="skeleton-list"><div className="skeleton-row" /><div className="skeleton-row" /></div>
            ) : aiConfig ? (
              <div className="ai-status-grid">
                <div className="ai-status-card">
                  <div className="status-label">LLM Generation</div>
                  <div className="status-value">
                    <label className="toggle-switch">
                      <input
                        type="checkbox"
                        checked={aiConfig.enabled}
                        onChange={toggleLLM}
                      />
                      <span className="slider"></span>
                    </label>
                    <span>{aiConfig.enabled ? 'Enabled' : 'Disabled'}</span>
                  </div>
                  <p className="status-desc">{aiConfig.enabled ? 'AI draft generation is active' : 'AI draft generation is disabled — only templates will be used'}</p>
                </div>

                <div className="ai-status-card">
                  <div className="status-label">Default Model</div>
                  <div className="status-value">
                    <select 
                      value={aiConfig.model} 
                      onChange={(e) => setDefaultModel(e.target.value)}
                      className="model-select"
                    >
                      {aiConfig.models?.map((m) => (
                        <option key={m.id} value={m.id}>
                          {m.label} ({m.provider})
                        </option>
                      ))}
                    </select>
                    <span className="provider-badge">{aiConfig.models?.find(m => m.id === aiConfig.model)?.provider || ''}</span>
                  </div>
                  <p className="status-desc">Default model used for AI draft generation</p>
                </div>
              </div>
            ) : (
              <p className="empty-body">Failed to load AI configuration</p>
            )}
          </div>

          {/* Available Models Management */}
          <div className="ai-config-section">
            <div className="section-header">
              <h3><Plus size={20} /> Available Models</h3>
              <button 
                className="btn-secondary" 
                onClick={() => setShowAddModel(!showAddModel)}
              >
                {showAddModel ? <ChevronUp size={16} /> : <ChevronDown size={16} />} 
                {showAddModel ? 'Cancel' : 'Add Model'}
              </button>
            </div>

            {showAddModel && (
              <form onSubmit={addModel} className="add-model-form">
                <div className="form-row">
                  <div className="field">
                    <label className="field-label">Model ID</label>
                    <input
                      type="text"
                      value={newModel.id}
                      onChange={(e) => setNewModel({...newModel, id: e.target.value})}
                      placeholder="e.g., groq-llama3"
                      required
                    />
                  </div>
                  <div className="field">
                    <label className="field-label">Display Label</label>
                    <input
                      type="text"
                      value={newModel.label}
                      onChange={(e) => setNewModel({...newModel, label: e.target.value})}
                      placeholder="e.g., Groq (Llama 3.1 70B)"
                      required
                    />
                  </div>
                  <div className="field">
                    <label className="field-label">Provider</label>
                    <select value={newModel.provider} onChange={(e) => setNewModel({...newModel, provider: e.target.value})} required>
                      <option value="">Select provider</option>
                      <option value="groq">Groq</option>
                      <option value="hf">HuggingFace</option>
                      <option value="local">Local GGUF</option>
                      <option value="template">Template Fallback</option>
                      <option value="openai">OpenAI</option>
                      <option value="anthropic">Anthropic</option>
                      <option value="other">Other</option>
                    </select>
                  </div>
                </div>
                <div className="form-actions">
                  <button type="button" className="btn-secondary" onClick={() => setShowAddModel(false)}>Cancel</button>
                  <button type="submit" className="btn-accent">Add Model</button>
                </div>
              </form>
            )}

            <div className="models-table">
              {aiConfig?.models?.map((m) => (
                <div key={m.id} className="model-row">
                  <div className="model-info">
                    <div className="model-name">{m.label}</div>
                    <div className="model-meta">
                      <span className="model-id">{m.id}</span>
                      <span className="provider-badge">{m.provider}</span>
                    </div>
                  </div>
                  <div className="model-actions">
                    {aiConfig.model === m.id && <span className="default-badge">Default</span>}
                    <button 
                      className="btn-icon" 
                      title="Set as default" 
                      onClick={() => setDefaultModel(m.id)}
                      disabled={aiConfig.model === m.id}
                    >
                      <Eye size={14} />
                    </button>
                    {/* Only allow deletion of non-default, non-core models */}
                    {(m.id !== 'groq' && m.id !== 'hf' && m.id !== 'local' && m.id !== 'template') && (
                      <button 
                        className="btn-icon danger" 
                        title="Remove model" 
                        onClick={() => deleteModel(m.id)}
                      >
                        <Trash size={14} />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </Layout>
  )
}


