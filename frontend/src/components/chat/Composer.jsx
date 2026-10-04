import { Icon } from './Icons'

export function Composer(props) {
  const message = props.message
  const setMessage = props.setMessage
  const attachments = props.attachments
  const isLoading = props.isLoading
  const onSubmit = props.onSubmit
  const isListening = props.isListening
  const voiceNotice = props.voiceNotice
  const toggleVoice = props.toggleVoice
  const fileInputRef = props.fileInputRef
  const handleFiles = props.handleFiles
  const onRemoveAttachment = props.onRemoveAttachment

  const textLen = (message || '').trim().length
  const hasFiles = attachments && attachments.length > 0
  const canSend = !isLoading && (textLen >= 30 || hasFiles)

  const submit = (e) => {
    if (e) e.preventDefault()
    if (!canSend) return
    onSubmit(message, attachments || [])
  }

  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  return (
    <div className="composer-wrap">
      <form className="composer" onSubmit={submit}>
        <label className="composer-label" htmlFor="lexdraft-query">
          <Icon name="Sparkles" size={14} />
          Message LexDraft
        </label>
        <textarea
          aria-label="Describe your case"
          id="lexdraft-query"
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Describe your case naturally — parties, what happened, court, amount... (English / Hindi / Hinglish, min 30 characters)"
          rows={3}
          value={message}
          disabled={isLoading}
        />
        <div className="composer-hint">
          <span className={textLen >= 30 || hasFiles ? 'composer-hint--ok' : ''}>
            {textLen >= 30 || hasFiles ? 'Ready to send' : 'Type at least 30 characters (' + textLen + '/30)'}
          </span>
        </div>
        <PendingAttachmentsLocal attachments={attachments} onRemove={onRemoveAttachment} />
        {voiceNotice ? <span className="voice-notice">{voiceNotice}</span> : null}
        <div className="composer-footer">
          <div>
            <input
              accept=".pdf,.doc,.docx,.txt,image/*"
              className="file-input"
              multiple
              onChange={handleFiles}
              ref={fileInputRef}
              type="file"
            />
            <button
              className="composer-tool"
              aria-label="Attach documents or images"
              onClick={() => fileInputRef.current && fileInputRef.current.click()}
              type="button"
              disabled={isLoading}
            >
              <Icon name="Paperclip" size={18} />
            </button>
            <button
              className={'composer-tool mic-button' + (isListening ? ' listening' : '')}
              aria-label={isListening ? 'Stop voice input' : 'Start voice input'}
              onClick={toggleVoice}
              type="button"
              disabled={isLoading}
            >
              <Icon name="Mic" size={18} />
              {isListening ? <span className="listening-dot" /> : null}
            </button>
          </div>
          <div className="send-group">
            <span>AI drafts need lawyer review before filing.</span>
            <button
              className="send-button"
              disabled={!canSend}
              aria-label="Send message"
              type="submit"
            >
              <Icon name="Send" size={17} />
            </button>
          </div>
        </div>
      </form>
    </div>
  )
}

function PendingAttachmentsLocal(props) {
  const attachments = props.attachments
  const onRemove = props.onRemove
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
