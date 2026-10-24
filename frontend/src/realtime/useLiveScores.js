import { useState, useCallback, useRef } from 'react'
import { useRealtimeEvent } from './useRealtime'

const MAX_SEEN = 200
const isScore = (n) => Number.isInteger(n) && n >= 0

export function useLiveScores(initial = {}) {
  const [scores, setScores] = useState(initial)
  const seen = useRef(new Set())

  const onScore = useCallback((payload) => {
    if (!payload) return

    const matchId = payload.match_id ?? payload.matchId
    const home = payload.score?.team_a_score ?? payload.team_a?.score ?? payload.home
    const away = payload.score?.team_b_score ?? payload.team_b?.score ?? payload.away
    const eventId = payload.event_id ?? payload.eventId

    if (matchId == null || !isScore(home) || !isScore(away)) return

    if (eventId != null) {
      if (seen.current.has(eventId)) return
      seen.current.add(eventId)

      if (seen.current.size > MAX_SEEN) {
        seen.current.delete(seen.current.values().next().value)
      }
    }

    setScores((previous) => {
      const current = previous[matchId]

      if (current && current.home === home && current.away === away) {
        return previous
      }

      return {
        ...previous,
        [matchId]: { home, away, updatedAt: Date.now() },
      }
    })
  }, [])

  useRealtimeEvent('live_score:update', onScore)

  return scores
}
