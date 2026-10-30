import { Icon } from './Icons'

export function Composer(props) {
  const message = props.message
  const setMessage = props.setMessage
  const isLoading = props.isLoading
  const onSubmit = props.onSubmit
  const isListening = props.isListening
  const voiceNotice = props.voiceNotice
  const toggleVoice = props.toggleVoice

  const textLen = (message || '').trim().length
  const canSend = !isLoading && textLen >= 30

  const submit = (e) => {
    if (e) e.preventDefault()
    if (!canSend) return
    onSubmit(message)
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
          <Icon name="Sparkles" size={12} />
          Message LexDraft AI
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
          <span className={textLen >= 30 ? 'composer-hint--ok' : ''}>
            {textLen >= 30 ? 'Ready to send' : 'Type at least 30 characters (' + textLen + '/30)'}
          </span>
        </div>
        {voiceNotice ? <span className="voice-notice">{voiceNotice}</span> : null}
        <div className="composer-footer">
          <div>
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