import { Icon } from './Icons'

export function DateRule({ children }) {
  return (
    <div className="date-rule">
      <span>{children}</span>
    </div>
  )
}

export function UserMessage({ time, attachments, children }) {
  return (
    <article className="message user-message">
      <div className="message-avatar user-avatar">
        <Icon name="User" size={17} />
      </div>
      <div className="message-body">
        <div className="message-meta">
          <strong>You</strong>
          <span>{time}</span>
        </div>
        <p>{children}</p>
        {attachments && attachments.length > 0 && (
          <div className="pending-attachments">
            {attachments.map((f, i) => (
              <span className="pending-file" key={(f.name || 'file') + '-' + i}>
                <Icon name="File" size={14} />
                <span>
                  <strong>{f.name}</strong>
                  <small>{f.sizeLabel || ''}</small>
                </span>
              </span>
            ))}
          </div>
        )}
      </div>
    </article>
  )
}

export function AssistantMessage({ time, label, children, draft, onViewDraft }) {
  return (
    <article className="message assistant-message">
      <div className="message-avatar ai-avatar">
        <Icon name="Sparkles" size={17} />
      </div>
      <div className="message-body">
        <div className="message-meta">
          <strong>LexDraft AI</strong>
          <span>{time}</span>
          <span className="ai-label">{label || 'LEGAL DRAFTING'}</span>
        </div>
        <p>{children}</p>
        {draft && (
          <div className="draft-actions">
            <span className="model-badge">{draft.modelUsed || 'DRAFT'}</span>
            <div className="action-buttons">
              <button className="action-btn secondary" type="button" onClick={onViewDraft}>
                View full draft
              </button>
            </div>
          </div>
        )}
      </div>
    </article>
  )
}

export function LoadingMessage({ statusText }) {
  return (
    <article className="message assistant-message">
      <div className="message-avatar ai-avatar">
        <Icon name="Sparkles" size={17} />
      </div>
      <div className="message-body loading">
        <div className="message-meta">
          <strong>LexDraft AI</strong>
          <span>now</span>
          <span className="ai-label">WORKING</span>
        </div>
        {statusText ? <p className="loading-status">{statusText}</p> : null}
        <div className="skeleton-lines">
          <div className="skeleton-line" />
          <div className="skeleton-line short" />
          <div className="skeleton-line" />
        </div>
      </div>
    </article>
  )
}

export function PendingAttachments({ attachments, onRemove }) {
  if (!attachments || attachments.length === 0) return null
  return (
    <div className="pending-attachments" aria-label="Selected attachments">
      {attachments.map((file, index) => (
        <span className="pending-file" key={(file.name || 'file') + '-' + index}>
          <Icon name="File" size={14} />
          <span>
            <strong>{file.name}</strong>
            <small>{file.sizeLabel || ''}</small>
          </span>
          <button aria-label={'Remove ' + file.name} onClick={() => onRemove(index)} type="button">
            ×
          </button>
        </span>
      ))}
    </div>
  )
}

export function VoiceNotice({ message }) {
  if (!message) return null
  return (
    <span className="voice-notice">{message}</span>
  )
}
