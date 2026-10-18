import { useState, useCallback, useRef } from 'react'
import { useRealtimeEvent } from './useRealtime'

const MAX_SEEN = 200
const isScore = (n) => Number.isInteger(n) && n >= 0

// Returns { [matchId]: { home, away, updatedAt } }, updated live.
// Malformed events and duplicates are ignored.
export function useLiveScores(initial = {}) {
  const [scores, setScores] = useState(initial)
  const seen = useRef(new Set())

  const onScore = useCallback((p) => {
    if (!p || p.matchId == null || !isScore(p.home) || !isScore(p.away)) return
    if (p.eventId != null) {
      if (seen.current.has(p.eventId)) return
      seen.current.add(p.eventId)
      if (seen.current.size > MAX_SEEN) {
        seen.current.delete(seen.current.values().next().value)
      }
    }
    setScores((prev) => {
      const cur = prev[p.matchId]
      if (cur && cur.home === p.home && cur.away === p.away) return prev
      return { ...prev, [p.matchId]: { home: p.home, away: p.away, updatedAt: Date.now() } }
    })
  }, [])

  useRealtimeEvent('score:update', onScore)
  return scores
}