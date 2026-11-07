import { useState } from 'react'
import toast from 'react-hot-toast'
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
      <div className="message-body">
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

export function AssistantMessage({ time, label, children, draft, onViewDraft, copyText, feedback, onFeedback }) {
  const [copied, setCopied] = useState(false)

  // Claude-style: assistant text is plain (no avatar column, no bubble).
  // Actions row below: Copy + Good (thumbs up) + Bad (thumbs down) ONLY.
  // No read-aloud, no retry (per user request).
  const handleCopy = async () => {
    const text = copyText || (typeof children === 'string' ? children : '')
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      toast.success('Copied to clipboard')
      setTimeout(() => setCopied(false), 1400)
    } catch {
      toast.error('Copy not available')
    }
  }

  const handleFeedback = (value) => {
    // value: 'good' | 'bad' | null (toggle)
    const next = feedback === value ? null : value
    onFeedback?.(next)
    if (next === 'good') toast.success('Thanks for the feedback')
    else if (next === 'bad') toast('Feedback noted — we will improve', { icon: 'ℹ️' })
  }

  return (
    <article className="message assistant-message assistant-message--claude">
      <div className="message-body">
        <div className="message-text">{children}</div>
        {draft && (
          <div className="draft-actions">
            <div className="action-buttons">
              <button className="action-btn secondary" type="button" onClick={onViewDraft}>
                View full draft
              </button>
            </div>
          </div>
        )}
        <div className="message-actions" role="group" aria-label="Actions for this response">
          <button
            type="button"
            className="message-action"
            onClick={handleCopy}
            title={copied ? 'Copied!' : 'Copy'}
            aria-label={copied ? 'Copied' : 'Copy response'}
          >
            <Icon name="Copy" size={15} />
          </button>
          <button
            type="button"
            className={'message-action' + (feedback === 'good' ? ' is-active' : '')}
            onClick={() => handleFeedback('good')}
            title="Good response"
            aria-label="Mark response as good"
            aria-pressed={feedback === 'good'}
          >
            <Icon name="ThumbsUp" size={15} />
          </button>
          <button
            type="button"
            className={'message-action' + (feedback === 'bad' ? ' is-active' : '')}
            onClick={() => handleFeedback('bad')}
            title="Bad response"
            aria-label="Mark response as bad"
            aria-pressed={feedback === 'bad'}
          >
            <Icon name="ThumbsDown" size={15} />
          </button>
        </div>
      </div>
    </article>
  )
}

export function LoadingMessage({ statusText }) {
  return (
    <article className="message assistant-message assistant-message--claude">
      <div className="message-body loading">
        <div className="message-meta">
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
