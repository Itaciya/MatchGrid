import { useState, useCallback } from 'react'
import { useRealtimeEvent } from './useRealtime'

// Returns { [fixtureId]: { kickoff, ...fields } }, updated live.
export function useFixtureUpdates(initial = {}) {
  const [fixtures, setFixtures] = useState(initial)
  const onFixture = useCallback((p) => {
    if (!p || p.fixtureId == null) return
    setFixtures((prev) => ({ ...prev, [p.fixtureId]: { ...prev[p.fixtureId], ...p } }))
  }, [])
  useRealtimeEvent('fixture:update', onFixture)
  return fixtures
}
