import { useState } from 'react'
import Login from './pages/Login'
import Onboarding from './pages/Onboarding'
import Chat from './pages/Chat'

export default function App() {
  const [user, setUser] = useState(null)
  const [onboarded, setOnboarded] = useState(false)

  if (!user) {
    return <Login onLogin={(u) => setUser(u)} />
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
