import { useEffect } from 'react'
import styles from './Login.module.css'

export default function Login({ onLogin }) {

  useEffect(() => {
    // Telegram Login Widget calls window.onTelegramAuth when user logs in
    window.onTelegramAuth = async (user) => {
      try {
        const res = await fetch('/api/start-signup', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            telegram_id: String(user.id),
            telegram_username: user.username || '',
            name: `${user.first_name || ''} ${user.last_name || ''}`.trim(),
          }),
        })
        if (!res.ok) throw new Error('Signup failed')
        onLogin({ telegramId: String(user.id), firstName: user.first_name || '' })
      } catch (e) {
        alert('Login failed: ' + e.message)
      }
    }
  }, [])

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

        <h1 className={styles.headline}>
          Your fitness data,<br />
          <span>finally talking.</span>
        </h1>
        <p className={styles.sub}>
          Connect Whoop, Strava, and Hevy. Ask anything. Get answers grounded in your actual performance data.
        </p>

        <div className={styles.divider} />

        <p className={styles.connectLabel}>Works with</p>
        <div className={styles.apps}>
          <div className={styles.appBadge}><span className={`${styles.dot} ${styles.dotWhoop}`} />Whoop</div>
          <div className={styles.appBadge}><span className={`${styles.dot} ${styles.dotStrava}`} />Strava</div>
          <div className={styles.appBadge}><span className={`${styles.dot} ${styles.dotHevy}`} />Hevy</div>
        </div>

        {/* Real Telegram Login Widget — replace YOUR_BOT_USERNAME below */}
        <div className={styles.tgWidgetWrapper}>
          <script
            async
            src="https://telegram.org/js/telegram-widget.js?22"
            data-telegram-login="FitBrainAI_bot"
            data-size="large"
            data-radius="12"
            data-onauth="onTelegramAuth(user)"
            data-request-access="write"
          />
        </div>

        <p className={styles.footer}>
          By continuing you agree to our <a href="#">Terms</a> and <a href="#">Privacy Policy</a>.<br />
          Your fitness data is never sold or shared.
        </p>
      </div>
    </div>
  )
}
