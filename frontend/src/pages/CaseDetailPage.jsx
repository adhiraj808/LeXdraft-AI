import { useParams, Link } from 'react-router-dom'
import Layout from '../components/Layout'
import DraftViewer from '../components/DraftViewer'
import EntityPanel from '../components/EntityPanel'
import StatusBadge from '../components/StatusBadge'
import CaseTypeBadge from '../components/CaseTypeBadge'
import { useCaseDetail } from '../hooks/useCase'
import { Download, RefreshCw, ArrowLeft, Clock, AlertCircle, Info, FileText } from 'lucide-react'

function InfoRow({ label, value }) {
  if (!value) return null
  return (
    <div className="info-row">
      <span className="info-row-label">{label}</span>
      <span className="info-row-value">{value}</span>
    </div>
  )
}

export default function CaseDetailPage() {
  const { id } = useParams()
  const { caseData, loading, regenerate, exportPdf } = useCaseDetail(id)

  if (loading) {
    return (
      <Layout>
        <div className="center-loading animate-fade-up">
          <div className="spinner-lg" />
          <p className="animate-pulse">Retrieving case files...</p>
        </div>
      </Layout>
    )
  }

  if (!caseData) {
    return (
      <Layout>
        <div className="not-found-box animate-fade-up">
          <AlertCircle size={48} />
          <h2>Case not found</h2>
          <p>The requested draft could not be located in the archives.</p>
          <Link to="/cases">
            <ArrowLeft size={16} /> Back to cases
          </Link>
        </div>
      </Layout>
    )
  }

  const isProcessing = ['processing', 'pending'].includes(caseData.status)

  return (
    <Layout>
      <nav className="breadcrumb animate-fade-up">
        <Link to="/cases">
          Archives
        </Link>
        <span>/</span>
        <span className="breadcrumb-current">{caseData.title}</span>
      </nav>

      <div className="detail-header animate-fade-up stagger-1">
        <div className="flex-1">
          <div className="detail-badges">
            <StatusBadge status={caseData.status} />
            {caseData.case_type && (
              <CaseTypeBadge type={caseData.case_type} confidence={caseData.case_type_confidence} />
            )}
          </div>
          <h1 className="detail-title">
            {caseData.title}
          </h1>
          <div className="detail-date">
            <Clock size={14} />
            <span>Indexed on {new Date(caseData.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' })}</span>
          </div>
        </div>

        <div className="detail-actions">
          {caseData.draft && (
            <>
              <button onClick={() => regenerate('all', '')} className="btn-outline">
                <RefreshCw size={14} /> Regenerate Draft
              </button>
              <button onClick={exportPdf} className="btn btn-accent">
                <Download size={14} /> Export PDF
              </button>
            </>
          )}
        </div>
      </div>

      {isProcessing && (
        <div className="banner banner--processing animate-pulse">
          <div className="banner-spinner animate-spin" />
          <div className="flex-1">
            <p className="banner-title font-mono">AI Engine Active</p>
            <p className="banner-body">
              Generating legal draft using RAG-enhanced Llama model. Analyzing precedents and structuring content...
            </p>
          </div>
        </div>
      )}

      {caseData.status === 'failed' && (
        <div className="banner banner--error animate-fade-up">
          <AlertCircle size={24} />
          <div>
            <p className="banner-title font-mono">Processing Error</p>
            <p className="banner-body">The AI pipeline encountered an issue. Please attempt to regenerate or check input facts.</p>
          </div>
        </div>
      )}

      <div className="detail-grid">
        <div className="detail-col-left animate-fade-up stagger-2">
          <div className="detail-card">
            <div className="detail-card-bg-icon">
              <Info size={120} strokeWidth={1} />
            </div>
            <h2 className="detail-card-heading">
              <FileText size={12} /> Case Specifications
            </h2>
            <div className="detail-card-body">
              <InfoRow label="Petitioner"    value={caseData.petitioner_name} />
              <InfoRow label="Respondent"    value={caseData.respondent_name} />
              <InfoRow label="Jurisdiction"  value={caseData.jurisdiction} />
              <InfoRow label="Statutes"      value={caseData.sections_alleged} />
            </div>
          </div>

          <div className="detail-card">
            <h2 className="detail-card-heading">Incident Summary</h2>
            <p className="description-text">
              "{caseData.case_description}"
            </p>
          </div>

          {caseData.extracted_entities && (
            <div className="detail-card">
              <h2 className="detail-card-heading">Identified Entities</h2>
              <EntityPanel entities={caseData.extracted_entities} />
            </div>
          )}

          {caseData.draft && (
            <div className="detail-card metadata-card">
              <div className="metadata-row">
                <span>Model Profile</span>
                <span>{caseData.draft.model_used || 'Indian-Legal-Llama-GGUF'}</span>
              </div>
              <div className="metadata-row">
                <span>Ref Version</span>
                <span>v{caseData.draft.version}.0</span>
              </div>
              {caseData.draft.generation_time_seconds && (
                <div className="metadata-row">
                  <span>Engine Time</span>
                  <span>{caseData.draft.generation_time_seconds}s</span>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="detail-col-right animate-fade-up stagger-3">
          <div className="draft-section-title">
            <h2>AI Draft Output</h2>
            {caseData.draft && (
              <div className="rag-badge">RAG ENHANCED</div>
            )}
          </div>

          {isProcessing ? (
            <div className="draft-processing">
              <div className="draft-processing-spinner animate-spin" />
              <h3>Assembling Legal Sections...</h3>
              <p>Consulting Indian Penal Code & NI Act precedents</p>
            </div>
          ) : (
            <div className="draft-frame">
              <DraftViewer
                draft={caseData.draft}
                onRegenerate={regenerate}
              />
            </div>
          )}
        </div>
      </div>
    </Layout>
  )
}
