import { useState } from 'react'
import { ChevronDown } from 'lucide-react'

const SECTIONS = [
  { key: 'title_block',        label: 'Title Block & Case Caption',           num: 'I'   },
  { key: 'complaint_body',     label: 'Complaint — Most Respectfully Showeth', num: 'II'  },
  { key: 'prayer',             label: 'Prayer',                               num: 'III' },
  { key: 'list_of_witnesses',  label: 'List of Witnesses',                    num: 'IV'  },
  { key: 'list_of_documents',  label: 'List of Documents',                    num: 'V'   },
  { key: 'affidavit',          label: 'Affidavit',                            num: 'VI'  },
  { key: 'evidence_affidavit', label: 'Evidence by Way of Affidavit',         num: 'VII' },
]

function Section({ num, label, sectionKey, content, onRegenerate }) {
  const [open, setOpen] = useState(true)
  const [regenOpen, setRegenOpen] = useState(false)
  const [ctx, setCtx] = useState('')

  return (
    <div className="draft-section collapse" data-open={open}>
      <div
        className="draft-section-header"
        onClick={() => setOpen(o => !o)}
        role="button"
        tabIndex={0}
        onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setOpen(o => !o); } }}
      >
        <span className="draft-section-num">{num}</span>
        <span className="draft-section-label">{label}</span>
        <div
          className="draft-section-regen"
          onClick={e => { e.stopPropagation(); setRegenOpen(o => !o); }}
          role="button"
          tabIndex={0}
          onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setRegenOpen(o => !o); } }}
        >
          Regenerate
        </div>
        <ChevronDown className={`draft-section-chevron ${open ? 'open' : ''}`} size={14} />
      </div>

      {regenOpen && (
        <div className="draft-section-regen-panel animate-fade-down">
          <input
            className="input"
            value={ctx}
            onChange={e => setCtx(e.target.value)}
            placeholder="Optional: additional instructions..."
          />
          <button
            className="btn btn-primary btn-sm"
            onClick={() => { onRegenerate(sectionKey, ctx); setRegenOpen(false); setCtx(''); }}
          >
            Generate
          </button>
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => setRegenOpen(false)}
          >
            Cancel
          </button>
        </div>
      )}

      <div className={`draft-section-content collapse-content ${open ? 'is-open' : ''}`}>
        {content
          ? <pre>{content}</pre>
          : <p className="draft-section-empty">No content generated for this section.</p>
        }
      </div>
    </div>
  )
}

export default function DraftViewer({ draft, onRegenerate }) {
  if (!draft) return (
    <div className="empty-state">
      <div className="empty-icon" style={{ width: '4rem', height: '4rem', fontSize: '1.5rem' }}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" width="32" height="32">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <polyline points="14 2 14 8 20 8" />
          <line x1="16" y1="13" x2="8" y2="13" />
          <line x1="16" y1="17" x2="8" y2="17" />
          <polyline points="10 9 9 9 8 9" />
        </svg>
      </div>
      <h3 className="empty-title">Draft not yet generated</h3>
      <p className="empty-body">Submit a case description to generate a legal draft.</p>
    </div>
  )

  return (
    <div className="draft-frame">
      <div className="draft-format-badge">
        <span className="draft-format-label">Format</span>
        <span className="draft-format-desc">Indian Court Complaint — 7 sections: Title Block → Complaint Body → Prayer → Witnesses → Documents → Affidavit → Evidence</span>
      </div>
      {SECTIONS.map(({ key, label, num }) => (
        <Section
          key={key}
          num={num}
          label={label}
          sectionKey={key}
          content={draft.sections?.[key]}
          onRegenerate={onRegenerate}
        />
      ))}
    </div>
  )
}