import { useLiveScores } from './useLiveScores'
import { useMatchStatus } from './useMatchStatus'
import { useMatchSubscriptions } from './useMatchSubscriptions'

const FINISHED = new Set(['cancelled', 'bye'])

/**
 * Live scores and statuses for a list of fixtures. Works for everyone,
 * signed in or not: guests follow public matches over the same connection.
 */
export function useLiveFixtures(fixtures) {
  const ids = (fixtures || [])
    .filter((fixture) => !FINISHED.has(fixture.status))
    .slice(0, 60)
    .map((fixture) => fixture.id)
  useMatchSubscriptions(ids)
  const scores = useLiveScores()
  const statuses = useMatchStatus()
  return { scores, statuses }
}
