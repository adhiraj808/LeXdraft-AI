import { Icon } from './Icons'

export function ContextPanel(props) {
  const isOpen = props.isOpen
  const onClose = props.onClose
  const info = props.info || {}
  const extracted = info.extracted || []
  const sources = info.sources || []
  const activity = info.activity || []

  return (
    <aside className={'context-panel' + (isOpen ? ' open' : '')}>
      <div className="context-header">
        <span>SOURCES & CONTEXT</span>
        <button onClick={onClose} aria-label="Close source panel" type="button">×</button>
      </div>

      <div className="context-content">
        <div className="matter-card">
          <span className="context-label">LINKED MATTER</span>
          <button type="button">
            <span className="matter-icon">
              <Icon name="Briefcase" size={18} />
            </span>
            <span>
              <strong>{info.caseTitle || 'Current draft session'}</strong>
              <small>{info.caseType ? info.caseType + (info.confidence ? ' · ' + info.confidence : '') : 'Auto-saved'}</small>
            </span>
            <Icon name="ChevronRight" size={15} />
          </button>
        </div>

        <section className="identified-section">
          <div className="identified-heading">
            <span className="context-label">IDENTIFIED FROM PROMPT</span>
            <span className="identified-status">
              <Icon name="Sparkles" size={11} />
              {' ' + extracted.length + ' found'}
            </span>
          </div>
          <div className="identified-filters" aria-label="Identified request filters">
            {extracted.length === 0 ? (
              <button type="button">
                <small>HINT</small>
                <span>Send a prompt to extract</span>
              </button>
            ) : (
              extracted.map((item) => (
                <button type="button" key={item.label}>
                  <small>{item.label}</small>
                  <span>{item.value}</span>
                </button>
              ))
            )}
          </div>
        </section>

        <section className="source-section">
          <div className="context-title">
            <span className="context-label">REFERENCED SOURCES</span>
            <span className="source-count">{sources.length}</span>
          </div>
          {sources.map((source, i) => (
            <button className="source-card" key={source.name + '-' + i} type="button">
              <span className={'source-icon ' + (source.tone || 'law')}>
                <Icon name={source.tone === 'policy' ? 'Document' : 'Library'} size={17} />
              </span>
              <span>
                <strong>{source.name}</strong>
                <small>{source.meta}</small>
              </span>
              <Icon name="ChevronRight" size={14} />
            </button>
          ))}
        </section>

        <section className="activity-section">
          <span className="context-label">ACTIVITY</span>
          {activity.map((a, i) => (
            <div className="activity-item" key={i}>
              <span className="activity-icon">
                <Icon name="Clock" size={16} />
              </span>
              <p>
                {a.text}
                <small>{a.time}</small>
              </p>
            </div>
          ))}
        </section>
      </div>

      <div className="confidential">
        <span className="security-dot" />
        <span>
          <strong>Private & confidential</strong>
          <small>Drafts need lawyer review before filing.</small>
        </span>
      </div>
    </aside>
  )
}

export function ContextToggle(props) {
  return (
    <button className="icon-button" onClick={props.onOpen} aria-label="Open context panel" type="button">
      <Icon name="Document" size={18} />
    </button>
  )
}
