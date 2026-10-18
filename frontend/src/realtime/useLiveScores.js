import { useState, useCallback } from 'react'
import { useRealtimeEvent } from './RealtimeProvider'

// Returns { [matchId]: { home, away, updatedAt } }, updated live.
export function useLiveScores(initial = {}) {
  const [scores, setScores] = useState(initial)
  const onScore = useCallback((p) => {
    if (!p || p.matchId == null) return
    setScores((prev) => ({
      ...prev,
      [p.matchId]: { home: p.home, away: p.away, updatedAt: Date.now() },
    }))
  }, [])
  useRealtimeEvent('score:update', onScore)
  return scores
}
