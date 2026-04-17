import { useState } from 'react'
import styles from './Onboarding.module.css'

export default function Onboarding({ telegramId, firstName, onComplete }) {
  const [whoopConnected, setWhoopConnected] = useState(false)
  const [stravaConnected, setStravaConnected] = useState(false)
  const [hevyKey, setHevyKey] = useState('')
  const [launching, setLaunching] = useState(false)
  const [error, setError] = useState('')

  function connectWhoop() {
    const w = window.open(`/auth/whoop/start?user_id=${telegramId}`, '_blank', 'width=600,height=700')
    const check = setInterval(() => {
      if (w.closed) {
        clearInterval(check)
        setWhoopConnected(true)
      }
    }, 500)
  }

  function connectStrava() {
    const w = window.open(`/auth/strava/start?user_id=${telegramId}`, '_blank', 'width=600,height=700')
    const check = setInterval(() => {
      if (w.closed) {
        clearInterval(check)
        setStravaConnected(true)
      }
    }, 500)
  }

  async function handleLaunch() {
    setLaunching(true)
    setError('')

    try {
      if (hevyKey.trim()) {
        await fetch('/api/save-hevy-key', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_id: telegramId, hevy_api_key: hevyKey.trim() })
        })
      }
      onComplete()
    } catch (e) {
      setError('Something went wrong. Please try again.')
      setLaunching(false)
    }
  }

  const initials = firstName ? firstName[0].toUpperCase() : '?'

  return (
    <div className={styles.page}>
      <div className={styles.texture} />
      <div className={styles.blob} />

      <div className={styles.card}>
        <div className={styles.logo}>
          <div className={styles.logoMark}>
            <svg viewBox="0 0 18 18" fill="none">
              <path d="M9 1.5L13 7H5L9 1.5Z" fill="white" />
              <path d="M3.5 8.5h11L12 16.5H6L3.5 8.5Z" fill="white" opacity="0.7" />
            </svg>
          </div>
          <span className={styles.logoName}>FitStack AI</span>
        </div>

        <div className={styles.userBadge}>
          <div className={styles.avatar}>{initials}</div>
          <div>
            <div className={styles.userName}>{firstName}</div>
            <div className={styles.userSub}>Telegram connected</div>
          </div>
        </div>

        <p className={styles.connectLabel}>Connect your apps</p>

        <button
          className={`${styles.connectBtn} ${whoopConnected ? styles.connected : ''}`}
          onClick={connectWhoop}
        >
          <div className={styles.connectLeft}>
            <span className={`${styles.dot} ${styles.dotWhoop}`} />
            Whoop
          </div>
          <span className={`${styles.connectStatus} ${whoopConnected ? styles.done : ''}`}>
            {whoopConnected ? '✓ Connected' : 'Connect →'}
          </span>
        </button>

        <button
          className={`${styles.connectBtn} ${stravaConnected ? styles.connected : ''}`}
          onClick={connectStrava}
        >
          <div className={styles.connectLeft}>
            <span className={`${styles.dot} ${styles.dotStrava}`} />
            Strava
          </div>
          <span className={`${styles.connectStatus} ${stravaConnected ? styles.done : ''}`}>
            {stravaConnected ? '✓ Connected' : 'Connect →'}
          </span>
        </button>

        <div className={styles.hevySection}>
          <label className={styles.inputLabel}>
            Hevy API Key <span className={styles.optional}>(optional)</span>
          </label>
          <input
            type="text"
            className={styles.input}
            placeholder="Your Hevy API key"
            value={hevyKey}
            onChange={e => setHevyKey(e.target.value)}
          />
          <p className={styles.note}>Hevy app → Settings → API Key · Requires Hevy Pro ($3/mo)</p>
        </div>

        <div className={styles.divider} />

        {error && <p className={styles.error}>{error}</p>}

        <button
          className={styles.launchBtn}
          onClick={handleLaunch}
          disabled={launching}
        >
          {launching ? 'Launching...' : 'Launch FitStack AI →'}
        </button>

        <p className={styles.skip} onClick={onComplete}>Skip for now</p>
      </div>
    </div>
  )
}
