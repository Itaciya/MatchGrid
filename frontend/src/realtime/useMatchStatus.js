import { useState, useCallback } from 'react'
import { useRealtimeEvent } from './RealtimeProvider'

// Returns { [matchId]: 'live' | 'halftime' | ... }, updated live.
export function useMatchStatus(initial = {}) {
  const [statuses, setStatuses] = useState(initial)
  const onStatus = useCallback((p) => {
    if (!p || p.matchId == null) return
    setStatuses((prev) => ({ ...prev, [p.matchId]: p.status }))
  }, [])
  useRealtimeEvent('match:status', onStatus)
  return statuses
}
