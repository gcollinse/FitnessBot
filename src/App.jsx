import { useState } from 'react'
import Login from './pages/Login'
import Chat from './pages/Chat'

export default function App() {
  const [loggedIn, setLoggedIn] = useState(false)
  return loggedIn ? <Chat /> : <Login onLogin={() => setLoggedIn(true)} />
}
