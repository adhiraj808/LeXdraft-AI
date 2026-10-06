import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { casesAPI, healthAPI } from '../services/api'
import { Sidebar, SidebarTrigger, SidebarOverlay } from '../components/chat/Sidebar'
import {
  UserMessage,
  AssistantMessage,
  LoadingMessage,
  DateRule,
} from '../components/chat/Conversation'
import { Composer } from '../components/chat/Composer'
import { ContextPanel, ContextToggle } from '../components/chat/ContextPanel'
import { Icon } from '../components/chat/Icons'

function now() {
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function fmtSize(bytes) {
  if (!bytes && bytes !== 0) return ''
  if (bytes < 1024 * 1024) return Math.ceil(bytes / 1024) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}

const SUGGESTIONS = [
  {
    label: 'Cheque Bounce Complaint',
    text: 'Ramesh Kumar supplied building materials worth Rs. 5,00,000 to Suresh Sharma in New Delhi. Suresh issued a cheque which was dishonoured due to funds insufficient. Legal notice sent, no payment in 15 days. Need complaint under Section 138 NI Act. Saket court.',
  },
  {
    label: 'Divorce Petition',
    text: 'Priya wants divorce from Vikram on grounds of cruelty and desertion. Married 10 years, one child. Seeking custody and alimony. Bengaluru family court.',
  },
  {
    label: 'Contract Breach',
    text: 'XYZ Corp failed to deliver goods worth Rs. 50,00,000 to ABC Ltd as per contract dated January 2024 in Mumbai. Seeking damages and specific performance under Section 73 Indian Contract Act.',
  },
]

export default function NewChatPage() {
  const navigate = useNavigate()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [contextOpen, setContextOpen] = useState(false)
  const [messages, setMessages] = useState([])
  const [message, setMessage] = useState('')
  const [attachments, setAttachments] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [isListening, setIsListening] = useState(false)
  const [voiceNotice, setVoiceNotice] = useState('')
  const [contextInfo, setContextInfo] = useState({ extracted: [], sources: [], activity: [] })
  const [backendUp, setBackendUp] = useState(null)
  const [pollRound, setPollRound] = useState(0)
  const [recents, setRecents] = useState([])
  const fileInputRef = useRef(null)
  const recognitionRef = useRef(null)
  const pollRef = useRef(null)
  const bottomRef = useRef(null)

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
      try { recognitionRef.current && recognitionRef.current.stop() } catch (e) { /* noop */ }
    }
  }, [])

  useEffect(() => {
    if (bottomRef.current) bottomRef.current.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  useEffect(() => {
    let cancelled = false
    healthAPI.check()
      .then(() => { if (!cancelled) setBackendUp(true) })
      .catch(() => { if (!cancelled) setBackendUp(false) })
    return () => { cancelled = true }
  }, [])

  const fetchRecents = async () => {
    try {
      const res = await casesAPI.list(0, 6)
      setRecents(res.data || [])
    } catch (e) { /* silent: sidebar simply shows empty state */ }
  }

  useEffect(() => { fetchRecents() }, [])

  const startNewChat = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
    try { recognitionRef.current && recognitionRef.current.stop() } catch (e) { /* noop */ }
    setMessages([])
    setMessage('')
    setAttachments([])
    setIsLoading(false)
    setIsListening(false)
    setVoiceNotice('')
    setContextInfo({ extracted: [], sources: [], activity: [] })
    navigate('/cases/aichat')
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
      try { recognitionRef.current && recognitionRef.current.stop() } catch (e) { /* noop */ }
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
    recognition.lang = 'en-IN'
    recognition.onresult = (event) => {
      let transcript = ''
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        transcript += event.results[i][0].transcript
      }
      transcript = transcript.trim()
      if (transcript) setMessage((cur) => (cur ? cur + ' ' : '') + transcript)
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

  const handleFiles = (event) => {
    const files = Array.from(event.target.files || []).slice(0, 5).map((f) => ({
      name: f.name,
      sizeLabel: fmtSize(f.size),
    }))
    setAttachments((cur) => [...cur, ...files].slice(0, 5))
    event.target.value = ''
  }

  const removeAttachment = (index) => {
    setAttachments((cur) => cur.filter((_, i) => i !== index))
  }

  const pushActivity = (text) => {
    setContextInfo((cur) => ({
      ...cur,
      activity: [{ text, time: now() }, ...(cur.activity || [])].slice(0, 6),
    }))
  }

  const handleSubmit = async (promptText, files) => {
    const text = (promptText || '').trim()
    if ((!text && (!files || files.length === 0)) || isLoading) return

    let fullPrompt = text
    if (files && files.length > 0) {
      const names = files.map((f) => f.name).join(', ')
      fullPrompt = (text ? text + '\n\n' : '') + '[Attached files for reference: ' + names + ']'
    }

    const tempId = Date.now()
    setMessages((cur) => [...cur, {
      id: tempId, role: 'user', content: text || ('Attached ' + files.length + ' file(s)'), time: now(),
    }])
    setMessage('')
    setAttachments([])
    setIsLoading(true)
    pushActivity('Prompt submitted')

    let caseId = null
    try {
      const res = await casesAPI.prompt({ prompt: fullPrompt })
      caseId = res.data && res.data.id
      if (!caseId) throw new Error('No case id returned')
      pushActivity('Extracting details + drafting')
    } catch (err) {
      const msg = describeError(err, 'Failed to submit prompt. Please try again.')
      toast.error(msg)
      setMessages((cur) => [...cur, {
        id: Date.now(), role: 'assistant', time: now(), content: msg,
      }])
      setIsLoading(false)
      return
    }

    if (pollRef.current) clearInterval(pollRef.current)
    setPollRound(0)
    pollRef.current = setInterval(async () => {
      let d = null
      try {
        const res = await casesAPI.get(caseId)
        d = res.data
        setPollRound((r) => r + 1)
      } catch (err) {
        clearInterval(pollRef.current)
        pollRef.current = null
        setMessages((cur) => [...cur, { id: Date.now(), role: 'assistant', time: now(), content: 'Lost connection while checking draft status. Open My Cases to see the result.' }])
        setIsLoading(false)
        return
      }
      if (d.status === 'completed' || d.status === 'failed') {
        clearInterval(pollRef.current)
        pollRef.current = null
        setIsLoading(false)
        fetchRecents()
        if (d.status === 'completed' && d.draft) {
          const conf = d.case_type_confidence ? Math.round(d.case_type_confidence * 100) + '% confidence' : ''
          const ents = d.extracted_entities || {}
          const chips = []
          const pushChip = (label, vals) => {
            if (vals && vals.length) chips.push({ label, value: vals.slice(0, 3).join(', ') })
          }
          pushChip('PARTIES', [...(ents.persons || []), ...(ents.organizations || [])])
          pushChip('COURT', ents.courts)
          pushChip('STATUTES', ents.statutes)
          pushChip('MONEY', ents.money)
          pushChip('DATES', ents.dates)
          pushChip('CASE TYPE', d.case_type ? [d.case_type] : [])
          setContextInfo((cur) => ({
            ...cur,
            caseTitle: d.title,
            caseType: d.case_type,
            confidence: conf,
            extracted: chips,
            sources: (ents.statutes || []).slice(0, 4).map((s) => ({ name: s, meta: 'Identified statute', tone: 'policy' })),
            activity: [{ text: 'Draft generated (' + ((d.draft && d.draft.model_used) || 'template') + ')', time: now() }, ...cur.activity].slice(0, 6),
          }))
          const preview = (d.draft.sections && (d.draft.sections.complaint_body || d.draft.sections.prayer)) || 'Draft generated successfully.'
          const short = preview.length > 600 ? preview.slice(0, 600) + '...' : preview
          setMessages((cur) => [...cur, {
            id: Date.now(), role: 'assistant', time: now(), caseId: d.id,
            caseType: d.case_type, model: d.draft.model_used,
            content: 'Draft ready — classified as ' + (d.case_type || 'Unknown') + (conf ? ' (' + conf + ')' : '') + '. Preview below; open the full draft for all 7 sections + PDF.',
            preview: short,
          }])
          toast.success('Draft ready')
        } else {
          setMessages((cur) => [...cur, { id: Date.now(), role: 'assistant', time: now(), content: 'Draft generation failed for this prompt. Try rephrasing with more detail (parties, dates, amounts).' }])
          pushActivity('Draft failed')
        }
      }
    }, 4000)
  }

  return (
    <div className="chat-page">
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} recents={recents} onNewChat={startNewChat} />
      <SidebarOverlay isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <main className="chat-main">
        <header className="chat-topbar">
          <div className="topbar-left">
            <SidebarTrigger onOpen={() => setSidebarOpen(true)} />
            <div className="matter-title">
              <span className="eyebrow">NEW CASE · CHAT</span>
              <div className="title-line">
                <strong>Describe your case</strong>
                <span className="saved-status">AI POWERED</span>
              </div>
            </div>
          </div>
          <div className="top-actions">
            <ContextToggle onOpen={() => setContextOpen(true)} />
          </div>

        </header>

        <div className="chat-conversation">
          <DateRule>Today</DateRule>

          {backendUp === false ? (
            <div className="banner banner--error" role="alert">
              <div>
                <div className="banner-title">Backend not reachable</div>
                <div className="banner-body">
                  The AI service did not answer. Make sure the backend is running
                  (docker compose up) and you opened this page via http://localhost:5173
                  — the 127.0.0.1 address also works.
                </div>
              </div>
            </div>
          ) : null}

          {messages.length === 0 ? (
            <div className="welcome-state">
              <div className="welcome-icon">
                <Icon name="Sparkles" size={56} />
              </div>
              <h2>Start with a prompt</h2>
              <p>Describe the case in your own words — English, Hindi or Hinglish. AI extracts parties, court, statutes and drafts the pleading.</p>
              <div className="suggested-prompts">
                {SUGGESTIONS.map((s) => (
                  <button key={s.label} className="prompt-chip" type="button" onClick={() => setMessage(s.text)}>
                    {s.label}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((msg) => (
              msg.role === 'user' ? (
                <UserMessage key={msg.id} time={msg.time}>
                  {msg.content}
                </UserMessage>
              ) : (
                <AssistantMessage key={msg.id} time={msg.time} label="LEGAL DRAFTING" draft={msg.caseId ? { modelUsed: msg.model } : null} onViewDraft={msg.caseId ? () => navigate('/cases/' + msg.caseId) : null}>
                  {msg.content}
                  {msg.preview ? <p className="assistant-preview">{msg.preview}</p> : null}
                </AssistantMessage>
              )
            ))
          )}
          {isLoading ? (
            <LoadingMessage
              statusText={
                pollRound < 3
                  ? 'Extracting parties, court and statutes from your prompt…'
                  : pollRound < 10
                    ? 'Classifying case and finding precedents…'
                    : 'Drafting all 7 sections — usually done within 1–2 min…'
              }
            />
          ) : null}
          <div ref={bottomRef} />
        </div>

        <Composer
          message={message}
          setMessage={setMessage}
          attachments={attachments}
          isLoading={isLoading}
          onSubmit={handleSubmit}
          isListening={isListening}
          voiceNotice={voiceNotice}
          toggleVoice={toggleVoice}
          fileInputRef={fileInputRef}
          handleFiles={handleFiles}
          onRemoveAttachment={removeAttachment}
        />
      </main>

      <ContextPanel isOpen={contextOpen} onClose={() => setContextOpen(false)} info={contextInfo} />
      <SidebarOverlay isOpen={contextOpen} onClose={() => setContextOpen(false)} />
    </div>
  )
}
