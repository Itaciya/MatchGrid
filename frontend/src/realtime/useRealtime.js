import { useContext, useEffect } from 'react'
import { RealtimeContext } from './realtimeContext'
import { wsClient } from './websocketClient'

export const useRealtimeStatus = () => useContext(RealtimeContext).status

export function useRealtimeEvent(type, handler) {
  useEffect(() => wsClient.on(type, handler), [type, handler])
}
