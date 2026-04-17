import { useState, useRef, useEffect } from 'react'
import styles from './Chat.module.css'

const STATS = [
  { label: 'Recovery', value: '82%', good: true },
  { label: 'HRV',      value: '71ms', good: true },
  { label: 'Strain',   value: '14.2', warn: true },
  { label: 'Sleep',    value: '7h 14m' },
  { label: 'Last Run', value: '5.2mi · 8:42/mi' },
  { label: 'Last Lift', value: 'Chest · Yesterday' },
]

const SUGGESTIONS = [
  'How\'s my recovery this week?',
  'Plan today\'s workout',
  'Analyze my sleep trends',
  'Show last run breakdown',
]

function getAIResponse(text) {
  const t = text.toLowerCase()
  if (t.includes('sleep'))
    return { text: "Last night: 7h 14m with 89% efficiency. REM came in at 1h 42m — solid. Sleep performance score was 84, above your monthly average of 79. Consistency has been good this week.", chips: ['Efficiency 89%', 'REM 1h 42m', 'Deep 1h 08m'] }
  if (t.includes('run') || t.includes('strava'))
    return { text: "Last run: 5.2 miles at an 8:42/mi average pace. Avg HR 158bpm — zone 3. Cadence 172spm. Your pace has improved ~12 sec/mile over the past 30 days.", chips: ['Pace 8:42/mi', 'Avg HR 158bpm', 'Zone 3 effort'] }
  if (t.includes('workout') || t.includes('train') || t.includes('today'))
    return { text: "Based on 82% recovery and yesterday's 14.2 strain, you're clear for intensity. I'd suggest a strength session — last chest day was 3 days ago. Deadlifts or squats would be ideal today.", chips: ['Recovery 82% · Green', 'Last heavy lift 3d ago', 'Strain budget ~16'] }
  return { text: "Your recovery score of 82% puts you in the green zone, with HRV tracking above your 30-day baseline. Strain yesterday was 14.2 — moderate. You're primed for a hard effort today.", chips: ['HRV 71ms · +4 vs baseline', 'Resting HR 48bpm', 'REM 1h 42m'] }
}

function now() {
  return new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true })
}

export default function Chat() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [showWelcome, setShowWelcome] = useState(true)
  const messagesEndRef = useRef(null)
  const textareaRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  function handleSend(text) {
    const msg = text || input.trim()
    if (!msg || loading) return
    setShowWelcome(false)
    setInput('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'

    setMessages(prev => [...prev, { role: 'user', text: msg, time: now() }])
    setLoading(true)

    setTimeout(() => {
      const resp = getAIResponse(msg)
      setMessages(prev => [...prev, { role: 'ai', ...resp, time: now() }])
      setLoading(false)
    }, 1300)
  }

  function handleKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  function handleInput(e) {
    setInput(e.target.value)
    e.target.style.height = 'auto'
    e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px'
  }

  return (
    <div className={styles.page}>
      {/* Nav */}
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
          <button className={styles.navPill}>/refresh</button>
          <button className={styles.navPill}>/nutrition</button>
          <div className={styles.avatar}>JD</div>
        </div>
      </nav>

      {/* Stats strip */}
      <div className={styles.statsStrip}>
        {STATS.map(s => (
          <div key={s.label} className={styles.statItem}>
            <span className={styles.statLabel}>{s.label}</span>
            <span className={`${styles.statVal} ${s.good ? styles.good : ''} ${s.warn ? styles.warn : ''}`}>{s.value}</span>
          </div>
        ))}
      </div>

      {/* Messages */}
      <div className={styles.messages}>
        {showWelcome && (
          <div className={styles.welcome}>
            <div className={styles.welcomeIcon}>
              <svg viewBox="0 0 26 26" fill="none">
                <path d="M13 2L18 9H8L13 2Z" fill="#2d5a27" />
                <path d="M5 11h16l-3 12H8L5 11Z" fill="#2d5a27" opacity="0.5" />
              </svg>
            </div>
            <h2 className={styles.welcomeTitle}>Good morning, JD</h2>
            <p className={styles.welcomeSub}>Recovery is solid at 82%. You're cleared for intensity today. What do you want to dig into?</p>
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
                {m.text}
                {m.chips && (
                  <div className={styles.dataChips}>
                    {m.chips.map(c => <span key={c} className={styles.dataChip}>{c}</span>)}
                  </div>
                )}
              </div>
              <div className={`${styles.meta} ${m.role === 'user' ? styles.metaRight : ''}`}>
                {m.time}{m.role === 'ai' ? ' · MST' : ''}
              </div>
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

      {/* Input */}
      <div className={styles.inputArea}>
        <div className={styles.cmdRow}>
          {['🥗 /nutrition', '↺ /refresh', 'Today\'s plan', 'Monthly trend'].map(c => (
            <button key={c} className={styles.cmdBtn} onClick={() => { setInput(c); textareaRef.current?.focus() }}>{c}</button>
          ))}
        </div>
        <div className={styles.inputRow}>
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
