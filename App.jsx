import { useState } from 'react'
import Login from './pages/Login'
import Chat from './pages/Chat'

export default function App() {
  const [user, setUser] = useState(null)

  // user = { telegramId, firstName }
  return user
    ? <Chat telegramId={user.telegramId} firstName={user.firstName} />
    : <Login onLogin={(u) => setUser(u)} />
}
