import { useEffect, useRef, useState } from 'react'
import toast from 'react-hot-toast'
import { Icon } from './Icons'
import { ModelSelector } from './ModelSelector'

export function Composer(props) {
  const message = props.message
  const setMessage = props.setMessage
  const isLoading = props.isLoading
  const onSubmit = props.onSubmit
  const isListening = props.isListening
  const voiceNotice = props.voiceNotice
  const toggleVoice = props.toggleVoice
  const primaryModel = props.primaryModel
  const fallbackModel = props.fallbackModel
  const onModelsChange = props.onModelsChange
  const [modelOpen, setModelOpen] = useState(false)
  const modelWrapRef = useRef(null)

  useEffect(() => {
    if (!modelOpen) return
    const onDown = (e) => {
      if (modelWrapRef.current && !modelWrapRef.current.contains(e.target)) setModelOpen(false)
    }
    const onKey = (e) => {
      if (e.key === 'Escape') setModelOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [modelOpen])

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
          <div className="composer-footer-left">
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
            {onModelsChange && (
              <div className="composer-model" ref={modelWrapRef}>
                <button
                  className="composer-model-btn"
                  type="button"
                  onClick={() => setModelOpen((v) => !v)}
                  aria-expanded={modelOpen}
                  aria-label="Change model"
                  title="Change model"
                >
                  <span className="composer-model-label">{primaryModel || 'groq'}</span>
                  <Icon name="ChevronDown" size={12} />
                </button>
                {modelOpen && (
                  <div className="composer-model-pop">
                    <ModelSelector
                      compact
                      onModelsChange={(v) => {
                        onModelsChange(v)
                        setModelOpen(false)
                      }}
                      initialPrimary={primaryModel}
                      initialFallback={fallbackModel}
                    />
                  </div>
                )}
              </div>
            )}
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