import { Link } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { useCaseList } from '../hooks/useCase'
import Layout from '../components/Layout'
import StatusBadge from '../components/StatusBadge'
import CaseTypeBadge from '../components/CaseTypeBadge'
import { Plus, ArrowRight, FolderOpen, CheckCircle, Clock, Sparkles } from 'lucide-react'

function StatPill({ label, value, sub, delay, icon: Icon }) {
  return (
    <div className="stat-pill animate-fade-up" style={{ animationDelay: `${delay}s` }}>
      <div className="stat-pill-label">
        <Icon size={14} /> {label}
      </div>
      <div className="stat-pill-value">{value}</div>
      {sub && <div className="stat-pill-sub">{sub}</div>}
    </div>
  )
}

export default function DashboardPage() {
  const { user } = useAuth()
  const { cases, loading } = useCaseList()

  const total = cases.length
  const completed = cases.filter(c => c.status === 'completed').length
  const pending = cases.filter(c => ['pending', 'processing'].includes(c.status)).length

  return (
    <Layout>
      <header className="dash-header animate-fade-up">
        <div className="dash-kicker">
          <Sparkles size={14} /> Welcome back
        </div>
        <h1 className="dash-title">
          {user?.full_name || user?.username}
        </h1>
        <p className="dash-subtitle">
          Your intelligent workspace for Indian legal drafting. Leverage fine-tuned LLMs and RAG technology for precision drafts.
        </p>
      </header>

      {/* Stat bar - runs off left edge */}
      <div className="stat-bar">
        <StatPill label="Total Drafts" value={total} sub="Cumulative cases" delay={0.1} icon={FolderOpen} />
        <StatPill label="Completed" value={completed} sub="Ready for export" delay={0.2} icon={CheckCircle} />
        <StatPill label="In Progress" value={pending} sub="Queue / Processing" delay={0.3} icon={Clock} />
      </div>

      {/* CTA Banner - runs off right edge */}
      <section className="animate-fade-up stagger-4">
        <div className="cta-banner">
          <div className="cta-text">
            <h2 className="cta-text-title">Create New Legal Draft</h2>
            <p className="cta-text-body">
              Generate a professional legal document based on case facts. Our system extracts entities and applies relevant legal precedents automatically.
            </p>
          </div>
          <Link to="/cases/new" className="btn btn-primary">
            <Plus size={20} /> New Draft
          </Link>
        </div>
      </section>

      {/* Activity feed */}
      <section className="animate-fade-up stagger-4">
        <div className="section-row">
          <h2 className="section-title">Recent Case Activity</h2>
          <Link to="/cases" className="section-link">
            All cases <ArrowRight size={14} />
          </Link>
        </div>

        {loading ? (
          <div className="choreo-list">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="skeleton skeleton-card animate-shimmer" />
            ))}
          </div>
        ) : cases.length === 0 ? (
          <div className="empty-state">
            <FolderOpen size={40} className="empty-icon" />
            <h3 className="empty-title">Your archives are empty</h3>
            <Link to="/cases/new" className="empty-action">Start your first draft today</Link>
          </div>
        ) : (
          <div className="activity-feed choreo-list">
            {cases.slice(0, 5).map((c) => (
              <Link key={c.id} to={`/cases/${c.id}`}>
                <div className="activity-item-row">
                  <div className={`activity-dot ${c.status === 'completed' ? 'activity-dot-completed' :
                    c.status === 'failed' ? 'activity-dot-failed' :
                      'activity-dot-active'
                  }`} />
                  <div className="activity-info">
                    <h3 className="activity-title truncate">{c.title}</h3>
                    <time className="activity-date">
                      Created {new Date(c.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}
                    </time>
                  </div>
                  <div className="activity-badges">
                    {c.case_type && <CaseTypeBadge type={c.case_type} />}
                    <StatusBadge status={c.status} />
                  </div>
                  <ArrowRight size={16} className="activity-chevron" />
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>
    </Layout>
  )
}