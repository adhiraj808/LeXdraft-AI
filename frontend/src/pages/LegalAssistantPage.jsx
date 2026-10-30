import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { casesAPI, healthAPI } from '../services/api'
import { Icon } from '../components/chat/Icons'
import { ModelSelector } from '../components/chat/ModelSelector'

function now() {
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

const SUGGESTIONS = [
  { label: 'FIR / Arrest / Bail', text: 'I have an FIR against me under section 420. Will I go to jail? Can I get anticipatory bail?' },
  { label: 'Property / Rent / Landlord', text: 'My landlord is not returning my security deposit of 50,000. Agreement ended 2 months ago.' },
  { label: 'Family / Divorce / 498A', text: 'My wife filed 498A against me. Will I be arrested? What is the process?' },
  { label: 'Cheque Bounce / Money Recovery', text: 'My cheque of 50,000 bounced. Got legal notice. What happens now?' },
  { label: 'Divorce / Maintenance / Custody', text: 'I want divorce from my wife after 5 years marriage. One child. What is the process?' },
]

export default function LegalAssistantPage() {
  const navigate = useNavigate()
  const [question, setQuestion] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isListening, setIsListening] = useState(false)
  const [voiceNotice, setVoiceNotice] = useState('')
  const [backendUp, setBackendUp] = useState(null)
  const [answer, setAnswer] = useState(null)
  const [language, setLanguage] = useState('english')
  const [showHistory, setShowHistory] = useState(false)
  const [history, setHistory] = useState([])
  const recognitionRef = useRef(null)
  const bottomRef = useRef(null)
  
  // Model selection state
  const [primaryModel, setPrimaryModel] = useState('groq')
  const [fallbackModel, setFallbackModel] = useState('template')
  
  const handleModelsChange = ({ primary, fallback }) => {
    setPrimaryModel(primary)
    setFallbackModel(fallback)
  }

  useEffect(() => {
    return () => {
      try { recognitionRef.current && recognitionRef.current.stop() } catch (e) { }
    }
  }, [])

  useEffect(() => {
    if (bottomRef.current) bottomRef.current.scrollIntoView({ behavior: 'smooth' })
  }, [answer])

  useEffect(() => {
    let cancelled = false
    healthAPI.check()
      .then(() => { if (!cancelled) setBackendUp(true) })
      .catch(() => { if (!cancelled) setBackendUp(false) })
    return () => { cancelled = true }
  }, [])

  const startNewQuery = () => {
    setQuestion('')
    setAnswer(null)
    setVoiceNotice('')
    try { recognitionRef.current && recognitionRef.current.stop() } catch (e) { }
    setIsListening(false)
  }

  const describeError = (err, fallback) => {
    if (!err.response) return 'Cannot reach backend — check your connection and that the API is running.'
    const detail = err.response.data && err.response.data.detail
    if (Array.isArray(detail)) {
      const first = detail[0]
      const where = first && first.loc ? first.loc.join('.') : 'input'
      return (first && first.msg ? first.msg + ' (' + where + ')' : fallback)
    }
    if (typeof detail === 'string' && detail) return detail
    return (err.response.data && err.response.data.message) || err.message || fallback
  }

  const toggleVoice = () => {
    if (isListening) {
      try { recognitionRef.current && recognitionRef.current.stop() } catch (e) { }
      setIsListening(false)
      return
    }
    const w = window
    const Recognition = w.SpeechRecognition || w.webkitSpeechRecognition
    if (!Recognition) {
      setVoiceNotice('Voice input is not supported in this browser.')
      return
    }
    const recognition = new Recognition()
    recognition.continuous = false
    recognition.interimResults = false
    recognition.lang = language === 'hindi' ? 'hi-IN' : 'en-IN'
    recognition.onresult = (event) => {
      let transcript = ''
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        transcript += event.results[i][0].transcript
      }
      transcript = transcript.trim()
      if (transcript) setQuestion((cur) => (cur ? cur + ' ' : '') + transcript)
    }
    recognition.onend = () => setIsListening(false)
    recognition.onerror = () => {
      setIsListening(false)
      setVoiceNotice('Microphone access was unavailable.')
    }
    recognitionRef.current = recognition
    setVoiceNotice('')
    setIsListening(true)
    try { recognition.start() } catch (e) { setIsListening(false) }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    const text = (question || '').trim()
    if (!text || isLoading) return

    setIsLoading(true)
    try {
      const res = await casesAPI.ask({ 
        question: text, 
        language,
        model: primaryModel,
        fallback_model: fallbackModel
      })
      setAnswer(res)
      // Add to history
      setHistory(prev => [{ id: Date.now(), question: text, answer: res, time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }, ...prev].slice(0, 10))
      toast.success('Answer received')
    } catch (err) {
      const msg = describeError(err, 'Failed to get answer. Please try again.')
      toast.error(msg)
    } finally {
      setIsLoading(false)
    }
  }

  const handleSuggestionClick = (text) => {
    setQuestion(text)
  }

  return (
    <div className="legal-assistant-page">
      <div className="assistant-header">
        <div className="header-left">
          <h1><Icon name="Scale" size={28} /> Legal Assistant</h1>
          <p className="subtitle">Ask any legal question in plain language. Get simple answers in English or Hindi.</p>
        </div>
        <div className="header-right">
          <ModelSelector 
            onModelsChange={handleModelsChange}
            initialPrimary={primaryModel}
            initialFallback={fallbackModel}
          />
          <select value={language} onChange={(e) => setLanguage(e.target.value)} className="language-select">
            <option value="english">English</option>
            <option value="hindi">हिंदी (Hindi)</option>
          </select>
          <button className="btn btn-ghost" onClick={() => setShowHistory(!showHistory)}>
            <Icon name="History" size={18} /> History
          </button>
        </div>
      </div>

      {backendUp === false ? (
        <div className="banner banner--error" role="alert">
          <div>
            <div className="banner-title">Backend not reachable</div>
            <div className="banner-body">
              The AI service did not answer. Make sure the backend is running
              (docker compose up) and you opened this page via http://localhost:5173
            </div>
          </div>
        </div>
      ) : null}

      <div className="assistant-main">
        <div className="assistant-panel">
          <div className="input-section">
            <div className="input-header">
              <h2><Icon name="HelpCircle" size={20} /> Ask Your Legal Question</h2>
              <p className="input-hint">Type or speak your question in English or Hindi. No legal jargon needed.</p>
            </div>

            <form className="question-form" onSubmit={(e) => { e.preventDefault(); handleSubmit(e); }}>
              <div className="question-input-wrap">
                <textarea
                  id="legal-question"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={(e) => { e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), handleSubmit(e)) }}
                  placeholder="e.g., 'I have an FIR under 420. Will I go to jail?' or 'My landlord won't return deposit. What to do?'"
                  placeholder={language === 'hindi' ? 'उदाहरण: मेरे खिलाफ 420 की FIR है। क्या मुझे जेल होगी?' : "e.g., 'I have an FIR under 420. Will I go to jail?' or 'My landlord won't return deposit. What to do?'"}
                  rows={4}
                  disabled={isLoading}
                  ref={(el) => { if (el) el.focus() }}
                />
                <div className="input-footer">
                  <span className="char-count">{question.length} characters</span>
                  <div className="input-actions">
                    <button
                      type="button"
                      className={`voice-btn ${isListening ? 'listening' : ''}`}
                      onClick={toggleVoice}
                      disabled={isLoading}
                      aria-label={isListening ? 'Stop voice input' : 'Start voice input'}
                    >
                      <Icon name="Mic" size={18} />
                      {isListening && <span className="listening-dot" />}
                    </button>
                    <button
                      type="button"
                      className="clear-btn"
                      onClick={startNewQuery}
                      disabled={isLoading || !question}
                    >
                      <Icon name="X" size={16} /> Clear
                    </button>
                  </div>
                </div>
              </div>

              <div className="form-footer">
                <span className="disclaimer-note">AI drafts need lawyer review before filing.</span>
                <button
                  type="submit"
                  className="submit-btn"
                  disabled={isLoading || !question.trim()}
                >
                  {isLoading ? (
                    <>
                      <span className="spinner" /> Getting answer...
                    </>
                  ) : (
                    <>
                      <Icon name="Send" size={17} /> Get Answer
                    </>
                  )}
                </button>
              </div>
            </form>

            <div className="suggestions">
              <span className="suggestions-label">Quick questions:</span>
              <div className="suggestion-chips">
                {SUGGESTIONS.map((s) => (
                  <button key={s.label} className="suggestion-chip" type="button" onClick={() => handleSuggestionClick(s.text)}>
                    {s.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {answer && (
            <div className="answer-section">
              <div className="answer-header">
                <div className="answer-meta">
                  <span className="category-badge">{answer.category}</span>
                  <span className="model-badge">{answer.model_used || 'AI'}</span>
                </div>
                <button className="copy-btn" onClick={() => { navigator.clipboard.writeText(answer.answer); toast.success('Copied!') }} title="Copy answer">
                  <Icon name="Copy" size={16} />
                </button>
              </div>

              <div className="answer-content">
                <div className="answer-text">{answer.answer}</div>

                {answer.key_points?.length > 0 && (
                  <div className="answer-section-block">
                    <h4><Icon name="CheckSquare" size={16} /> Key Points</h4>
                    <ul>{answer.key_points.map((p, i) => <li key={i}>{p}</li>)}</ul>
                  </div>
                )}

                {answer.next_steps?.length > 0 && (
                  <div className="answer-section-block">
                    <h4><Icon name="ArrowRight" size={16} /> What to Do Next</h4>
                    <ol>{answer.next_steps.map((s, i) => <li key={i}>{s}</li>)}</ol>
                  </div>
                )}

                {answer.applicable_laws?.length > 0 && (
                  <div className="answer-section-block">
                    <h4><Icon name="BookOpen" size={16} /> Relevant Laws</h4>
                    <ul>{answer.applicable_laws.map((l, i) => <li key={i}>{l}</li>)}</ul>
                  </div>
                )}

                <div className="disclaimer-box">
                  <Icon name="AlertTriangle" size={16} />
                  <span>{answer.disclaimer}</span>
                </div>

                <div className="answer-actions">
                  <button className="btn btn-secondary" onClick={startNewQuery}>
                    <Icon name="Plus" size={16} /> New Question
                  </button>
                  <button className="btn btn-primary" onClick={() => { setAnswer({...answer, showHistory: true }); setShowHistory(true); }}>
                    <Icon name="History" size={16} /> Save to History
                  </button>
                </div>
              </div>
            </div>
          )}

          {!answer && !question && (
            <div className="empty-state">
              <div className="empty-icon"><Icon name="Scale" size={56} /></div>
              <h2>Ask Anything Legal</h2>
              <p>No legal knowledge needed. Ask in plain English or Hindi.</p>
              <div className="suggested-prompts">
                {SUGGESTIONS.map((s) => (
                  <button key={s.label} className="prompt-chip" type="button" onClick={() => handleSuggestionClick(s.text)}>
                    {s.label}
                  </button>
                ))}
              </div>
            </div>
          )}

        </div>

        {showHistory && history.length > 0 && (
          <div className="history-panel">
            <div className="history-header">
              <h3><Icon name="History" size={20} /> Recent Questions</h3>
              <button className="close-history" onClick={() => setShowHistory(false)}><Icon name="X" size={18} /></button>
            </div>
            <div className="history-list">
              {history.map((h) => (
                <div key={h.id} className="history-item" onClick={() => setAnswer(h.answer)}>
                  <div className="history-question">{h.question}</div>
                  <div className="history-meta">
                    <span>{h.time}</span>
                    <span className="category-badge">{h.answer?.category}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
