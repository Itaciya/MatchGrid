import { useEffect } from 'react'
import { useRealtimeStatus } from './useRealtime'
import { wsClient } from './websocketClient'

// Follow live updates for a set of matches while the component is mounted.
// Subscriptions are sent again after every reconnect.
export function useMatchSubscriptions(matchIds) {
  const status = useRealtimeStatus()
  const key = [...new Set(matchIds.filter((id) => Number.isInteger(id) && id > 0))].sort((a, b) => a - b).join(',')

  useEffect(() => {
    if (status !== 'open' || !key) return undefined
    const ids = key.split(',').map(Number)
    ids.forEach((match_id) => wsClient.send('subscribe_match', { match_id }))
    return () => {
      if (wsClient.status === 'open') {
        ids.forEach((match_id) => wsClient.send('unsubscribe_match', { match_id }))
      }
    }
  }, [status, key])
}
