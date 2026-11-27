import { useState, useCallback } from 'react'
import { useRealtimeEvent } from './useRealtime'

// Returns { [matchId]: 'live' | 'paused' | 'completed' | ... }, updated live
// from the backend's match_status:update events.
export function useMatchStatus(initial = {}) {
  const [statuses, setStatuses] = useState(initial)
  const onStatus = useCallback((payload) => {
    const matchId = payload?.match_id ?? payload?.matchId
    if (matchId == null || !payload.status) return
    setStatuses((previous) => (
      previous[matchId] === payload.status ? previous : { ...previous, [matchId]: payload.status }
    ))
  }, [])
  useRealtimeEvent('match_status:update', onStatus)
  return statuses
}
