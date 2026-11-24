import { useEffect, useState } from 'react'
import { apiRequest } from '../services/api'

/** Loads a tournament's fixtures (names included) for the given tournament. */
export function useTournamentFixtures(tournamentId) {
  const [state, setState] = useState({ fixtures: [], loading: false, error: '', forId: '' })

  useEffect(() => {
    if (!tournamentId) return undefined
    let cancelled = false
    // Defer state updates out of the effect body.
    const timer = window.setTimeout(() => {
      setState((current) => ({ ...current, loading: true, error: '', forId: tournamentId }))
      apiRequest(`/matches/tournaments/${tournamentId}/fixtures`)
        .then((rows) => { if (!cancelled) setState({ fixtures: Array.isArray(rows) ? rows : [], loading: false, error: '', forId: tournamentId }) })
        .catch((err) => { if (!cancelled) setState({ fixtures: [], loading: false, error: err.message || 'Could not load matches.', forId: tournamentId }) })
    }, 0)
    return () => { cancelled = true; window.clearTimeout(timer) }
  }, [tournamentId])

  if (!tournamentId || state.forId !== tournamentId) return { fixtures: [], loading: Boolean(tournamentId), error: '' }
  return state
}
