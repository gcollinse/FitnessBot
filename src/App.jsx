import { useState, useEffect } from 'react'
import Login from './pages/Login'
import Onboarding from './pages/Onboarding'
import Chat from './pages/Chat'

export default function App() {
  const [user, setUser] = useState(null)
  const [onboarded, setOnboarded] = useState(false)

  useEffect(() => {
    // Check localStorage first (returning users)
    const userId = localStorage.getItem('fitstack_user_id')
    const firstName = localStorage.getItem('fitstack_first_name')
    if (userId) {
      setUser({ telegramId: userId, firstName: firstName || '' })
      setOnboarded(true)
      return
    }
    // Fall back to URL param (coming from onboarding redirect)
    const params = new URLSearchParams(window.location.search)
    const urlUserId = params.get('user_id')
    if (urlUserId) {
      setUser({ telegramId: urlUserId, firstName: '' })
      setOnboarded(true)
    }
  }, [])

  if (!user) {
    return <Login onLogin={(u) => { setUser(u) }} />
  }

  if (!onboarded) {
    return (
      <Onboarding
        telegramId={user.telegramId}
        firstName={user.firstName}
        onComplete={() => setOnboarded(true)}
      />
    )
  }

  return <Chat telegramId={user.telegramId} firstName={user.firstName} />
}
