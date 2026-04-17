import styles from './Login.module.css'

export default function Login({ onLogin }) {
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

        <button className={styles.tgBtn} onClick={onLogin}>
          <svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
            <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.562 8.248l-2.04 9.607c-.148.658-.538.817-1.09.508l-3.01-2.218-1.454 1.398c-.16.16-.296.296-.607.296l.215-3.053 5.566-5.028c.242-.215-.053-.334-.374-.12L6.68 14.875l-2.95-.92c-.641-.2-.654-.641.134-.948l11.523-4.44c.533-.194 1.001.13.175.681z" />
          </svg>
          Continue with Telegram
        </button>

        <p className={styles.footer}>
          By continuing you agree to our <a href="#">Terms</a> and <a href="#">Privacy Policy</a>.<br />
          Your fitness data is never sold or shared.
        </p>
      </div>
    </div>
  )
}
