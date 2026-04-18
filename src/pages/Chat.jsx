import { useState, useRef, useEffect } from 'react'
import styles from './Chat.module.css'

const DEFAULT_STATS = [
  { label: 'Recovery', value: '—' },
  { label: 'HRV',      value: '—' },
  { label: 'Sleep',    value: '—' },
  { label: 'Resting HR', value: '—' },
  { label: 'Last Run', value: '—' },
  { label: 'Last Lift', value: '—' },
]

const SUGGESTIONS = [
  "How's my recovery this week?",
  "Plan today's workout",
  'Analyze my sleep trends',
  'Show last run breakdown',
]

function now() {
  return new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true })
}

export default function Chat({ telegramId, firstName }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [showWelcome, setShowWelcome] = useState(true)
  const [stats, setStats] = useState(DEFAULT_STATS)
  const historyRef = useRef([])
  const messagesEndRef = useRef(null)
  const textareaRef = useRef(null)
  const fileInputRef = useRef(null)

  useEffect(() => {
    if (telegramId) {
      fetchDailySummary()
      fetchConversationHistory()
    }
  }, [telegramId])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  async function fetchDailySummary() {
    try {
      const res = await fetch(`/api/daily-summary/${telegramId}`)
      if (!res.ok) return
      const data = await res.json()
      setStats([
        { label: 'Recovery',   value: data.recovery ? `${data.recovery}%` : '—', good: data.recovery >= 67, warn: data.recovery < 34 },
        { label: 'HRV',        value: data.hrv ? `${Math.round(data.hrv)}ms` : '—', good: true },
        { label: 'Sleep',      value: data.sleep ? `${data.sleep}%` : '—' },
        { label: 'Resting HR', value: data.resting_hr ? `${data.resting_hr}bpm` : '—' },
        { label: 'Last Run',   value: data.last_run || '—' },
        { label: 'Last Lift',  value: data.last_lift || '—' },
      ])
    } catch (e) {
      console.error('Failed to fetch daily summary', e)
    }
  }

  async function fetchConversationHistory() {
    try {
      const res = await fetch(`/api/conversation/${telegramId}`)
      if (!res.ok) return
      const data = await res.json()
      if (data.messages && data.messages.length > 0) {
        setShowWelcome(false)
        const displayed = data.messages.map(m => ({
          role: m.role === 'assistant' ? 'ai' : 'user',
          text: m.content,
          time: '',
        }))
        setMessages(displayed)
        historyRef.current = data.messages
      }
    } catch (e) {
      console.error('Failed to fetch conversation history', e)
    }
  }

  async function handleSend(text) {
    const msg = text || input.trim()
    if (!msg || loading) return
    setShowWelcome(false)
    setInput('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'

    const userMsg = { role: 'user', text: msg, time: now() }
    setMessages(prev => [...prev, userMsg])
    setLoading(true)

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          telegram_id: telegramId,
          message: msg,
          history: historyRef.current,
        }),
      })

      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'API error')
      }

      const data = await res.json()

      historyRef.current = [
        ...historyRef.current,
        { role: 'user', content: msg },
        { role: 'assistant', content: data.text },
      ].slice(-40)

      setMessages(prev => [...prev, { role: 'ai', text: data.text, time: now() }])
    } catch (e) {
      setMessages(prev => [...prev, {
        role: 'ai',
        text: `Sorry, something went wrong: ${e.message}`,
        time: now(),
      }])
    } finally {
      setLoading(false)
    }
  }

  async function handlePhotoUpload(e) {
    const file = e.target.files[0]
    if (!file) return

    setShowWelcome(false)
    setLoading(true)

    const previewUrl = URL.createObjectURL(file)
    setMessages(prev => [...prev, {
      role: 'user',
      text: '📸 Food photo',
      image: previewUrl,
      time: now(),
    }])

    try {
      const formData = new FormData()
      formData.append('photo', file)
      formData.append('telegram_id', telegramId)

      const res = await fetch('/api/analyze-photo', {
        method: 'POST',
        body: formData,
      })

      if (!res.ok) throw new Error('Photo analysis failed')
      const data = await res.json()

      setMessages(prev => [...prev, { role: 'ai', text: data.text, time: now() }])
    } catch (e) {
      setMessages(prev => [...prev, {
        role: 'ai',
        text: `Sorry, couldn't analyze that photo: ${e.message}`,
        time: now(),
      }])
    } finally {
      setLoading(false)
      e.target.value = ''
    }
  }

  function handleKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  function handleInput(e) {
    setInput(e.target.value)
    e.target.style.height = 'auto'
    e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px'
  }

  const greeting = firstName ? `Good morning, ${firstName}` : 'Good morning'

  return (
    <div className={styles.page}>
      <nav className={styles.nav}>
        <div className={styles.navLeft}>
          <div className={styles.navLogoMark}>
            <svg viewBox="0 0 18 18" fill="none">
              <path d="M9 1.5L13 7H5L9 1.5Z" fill="white" />
              <path d="M3.5 8.5h11L12 16.5H6L3.5 8.5Z" fill="white" opacity="0.7" />
            </svg>
          </div>
          <span className={styles.navName}>FitStack</span>
          <div className={styles.navStatus}><div className={styles.statusDot} />ONLINE</div>
        </div>
        <div className={styles.navRight}>
          <button className={styles.navPill} onClick={fetchDailySummary}>/refresh</button>
          <button className={styles.navPill} onClick={() => handleSend('/nutrition')}>/nutrition</button>
          <div className={styles.avatar}>{firstName ? firstName[0].toUpperCase() : ''}</div>
        </div>
      </nav>

      <div className={styles.statsStrip}>
        {stats.map(s => (
          <div key={s.label} className={styles.statItem}>
            <span className={styles.statLabel}>{s.label}</span>
            <span className={`${styles.statVal} ${s.good ? styles.good : ''} ${s.warn ? styles.warn : ''}`}>{s.value}</span>
          </div>
        ))}
      </div>

      <div className={styles.messages}>
        {showWelcome && (
          <div className={styles.welcome}>
            <div className={styles.welcomeIcon}>
              <svg viewBox="0 0 26 26" fill="none">
                <path d="M13 2L18 9H8L13 2Z" fill="#2d5a27" />
                <path d="M5 11h16l-3 12H8L5 11Z" fill="#2d5a27" opacity="0.5" />
              </svg>
            </div>
            <h2 className={styles.welcomeTitle}>{greeting}</h2>
            <p className={styles.welcomeSub}>Your fitness data is loaded and ready. What do you want to dig into?</p>
            <div className={styles.chips}>
              {SUGGESTIONS.map(s => (
                <button key={s} className={styles.chip} onClick={() => handleSend(s)}>{s}</button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`${styles.msgRow} ${m.role === 'user' ? styles.user : styles.ai}`}>
            <div>
              {m.role === 'ai' && <div className={styles.aiName}>FITSTACK AI</div>}
              <div className={styles.bubble}>
                {m.image && (
                  <img src={m.image} alt="food" style={{ width: '100%', borderRadius: '8px', marginBottom: '6px' }} />
                )}
                {m.role === 'ai' ? formatAIText(m.text) : m.text}
              </div>
              {m.time && (
                <div className={`${styles.meta} ${m.role === 'user' ? styles.metaRight : ''}`}>
                  {m.time}{m.role === 'ai' ? ' · MST' : ''}
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className={`${styles.msgRow} ${styles.ai}`}>
            <div>
              <div className={styles.aiName}>FITSTACK AI</div>
              <div className={styles.typing}>
                <span className={styles.typingDot} />
                <span className={styles.typingDot} />
                <span className={styles.typingDot} />
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <div className={styles.inputArea}>
        <div className={styles.cmdRow}>
          {["🥗 /nutrition", "↺ /refresh", "How should I train today?", "How am I trending this month?"].map(c => (
            <button key={c} className={styles.cmdBtn} onClick={() => { setInput(c); textareaRef.current?.focus() }}>{c}</button>
          ))}
        </div>
        <div className={styles.inputRow}>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            style={{ display: 'none' }}
            onChange={handlePhotoUpload}
          />
          <button
            className={styles.photoBtn}
            onClick={() => fileInputRef.current?.click()}
            disabled={loading}
            title="Analyze food photo"
          >
            <svg viewBox="0 0 20 20" fill="none" width="18" height="18">
              <rect x="2" y="5" width="16" height="12" rx="2" stroke="currentColor" strokeWidth="1.5"/>
              <circle cx="10" cy="11" r="3" stroke="currentColor" strokeWidth="1.5"/>
              <path d="M7 5l1.5-2h3L13 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
          </button>
          <textarea
            ref={textareaRef}
            className={styles.input}
            value={input}
            onChange={handleInput}
            onKeyDown={handleKey}
            placeholder="Ask about your recovery, workouts, sleep..."
            rows={1}
          />
          <button className={styles.sendBtn} onClick={() => handleSend()} disabled={loading || !input.trim()}>
            <svg viewBox="0 0 16 16" fill="none" width="15" height="15">
              <path d="M14 8L2 2l2.5 6L2 14l12-6z" fill="white" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  )
}

function formatAIText(text) {
  if (!text) return ''
  const parts = text.split(/(\*[^*]+\*)/)
  return parts.map((part, i) => {
    if (part.startsWith('*') && part.endsWith('*')) {
      return <strong key={i}>{part.slice(1, -1)}</strong>
    }
    return part
  })
}
