import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import Layout from '../components/Layout'
import StatusBadge from '../components/StatusBadge'
import CaseTypeBadge from '../components/CaseTypeBadge'
import { useCaseList } from '../hooks/useCase'
import { casesAPI } from '../services/api'
import { Plus, Trash2, Search, FileText, Filter, MoreVertical } from 'lucide-react'
import toast from 'react-hot-toast'

export default function CaseListPage() {
  const { cases, loading, refetch } = useCaseList()
  const [deleting, setDeleting] = useState(null)
  const [search, setSearch] = useState('')
  const navigate = useNavigate()

  const handleDelete = async (id, e) => {
    e.preventDefault()
    e.stopPropagation()
    if (!confirm('Delete this case and its draft? This cannot be undone.')) return
    setDeleting(id)
    try {
      await casesAPI.delete(id)
      toast.success('Case deleted')
      refetch()
    } catch {
      toast.error('Delete failed')
    } finally {
      setDeleting(null)
    }
  }

  const filteredCases = cases.filter(c =>
    c.title.toLowerCase().includes(search.toLowerCase()) ||
    c.case_type?.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <Layout>
      <header className="list-page-header animate-fade-up">
        <div>
          <h1>My Legal Archives</h1>
          <p className="list-page-count">
            <strong className="font-mono">{cases.length}</strong> Total drafts indexed
          </p>
        </div>
        <Link to="/cases/new" className="btn btn-accent">
          <Plus size={18} /> New Case Draft
        </Link>
      </header>

      <div className="toolbar animate-fade-up stagger-1">
        <div className="search-box">
          <Search className="field-icon" size={18} />
          <input
            type="text"
            placeholder="Search by title or case type..."
            className="text-input"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        <button className="toolbar-btn">
          <Filter size={18} /> Filter
        </button>
      </div>

      {loading ? (
        <div className="skeleton-list">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="skeleton-row animate-pulse" style={{ padding: '1.5rem' }}>
              <div className="flex items-center" style={{ gap: '1rem' }}>
                <div style={{ width: '2.5rem', height: '2.5rem', background: 'var(--navy-accent)', borderRadius: '0.5rem' }} />
                <div className="flex-1" style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  <div style={{ height: '1rem', background: 'var(--navy-accent)', borderRadius: '0.25rem', width: '33%' }} />
                  <div style={{ height: '0.75rem', background: 'var(--navy-accent)', borderRadius: '0.25rem', width: '25%' }} />
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : filteredCases.length === 0 ? (
        <div className="empty-state empty-state--rounder animate-fade-up">
          <div className="empty-icon-wrap">
            <FileText size={32} className="empty-icon" style={{ margin: 0 }} />
          </div>
          <h2 className="empty-title">No records found</h2>
          <p className="empty-body">
            {search ? `We couldn't find any results for "${search}"` : "You haven't initiated any legal drafts yet."}
          </p>
          <Link to="/cases/new" className="empty-link">
            <Plus size={16} /> Create your first case
          </Link>
        </div>
      ) : (
        <div className="case-list animate-fade-up stagger-2">
          {filteredCases.map((c, idx) => (
            <div
              key={c.id}
              onClick={() => navigate(`/cases/${c.id}`)}
              className="case-row animate-fade-up"
              style={{ animationDelay: `${idx * 0.05}s` }}
            >
              <div className="case-row-icon">
                <FileText size={20} />
              </div>

              <div className="case-row-info">
                <h3 className="case-row-title truncate">
                  {c.title}
                </h3>
                <div className="case-row-meta">
                  <span>ID: {c.id.slice(0, 8)}</span>
                  <span className="case-row-dot" />
                  <span>{new Date(c.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}</span>
                </div>
              </div>

              <div className="case-row-badges">
                {c.case_type && <CaseTypeBadge type={c.case_type} />}
                <StatusBadge status={c.status} />
              </div>

              <div className="case-row-actions">
                <button
                  onClick={(e) => handleDelete(c.id, e)}
                  disabled={deleting === c.id}
                  className="btn-icon"
                  title="Delete case"
                >
                  <Trash2 size={16} />
                </button>
                <div className="btn-icon" style={{ cursor: 'default' }}>
                  <MoreVertical size={16} />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </Layout>
  )
}
