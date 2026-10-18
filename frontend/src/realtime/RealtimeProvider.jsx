import { useEffect, useState } from 'react'
import { wsClient } from './websocketClient'
import { RealtimeContext } from './realtimeContext'

export function RealtimeProvider({ children }) {
  const [status, setStatus] = useState(wsClient.status)

  useEffect(() => {
    const off = wsClient.onStatus(setStatus)
    wsClient.connect()
    return () => { off(); wsClient.disconnect() }
  }, [])

  return <RealtimeContext.Provider value={{ status }}>{children}</RealtimeContext.Provider>
}
