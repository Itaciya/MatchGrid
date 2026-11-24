import { useEffect, useState } from 'react'
import { apiRequest } from '../services/api'
import { MATCH_STATUS_LABELS, matchLabel, playerName } from './pickerUtils'
import { useTournamentFixtures } from './useTournamentFixtures'

// Shared pickers so people choose tournaments, matches and players by name
// instead of typing database IDs.

/**
 * Dropdown of tournaments.
 * ownerId: only show tournaments organised by this user.
 * filter: optional predicate for further narrowing.
 */
export function TournamentSelect({ id, label = 'Tournament', value, onChange, ownerId = null, filter = null, emptyText = 'No tournaments available yet.' }) {
  const [tournaments, setTournaments] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    apiRequest('/tournaments/')
      .then((rows) => {
        if (cancelled) return
        let list = Array.isArray(rows) ? rows : []
        if (ownerId != null) list = list.filter((item) => item.organizer_id === ownerId)
        if (filter) list = list.filter(filter)
        setTournaments(list)
      })
      .catch((err) => { if (!cancelled) setError(err.message || 'Could not load tournaments.') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
    // filter is intentionally excluded: callers pass inline functions.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ownerId])

  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <select id={id} value={value} onChange={(event) => onChange(event.target.value)} disabled={loading || tournaments.length === 0}>
        <option value="">{loading ? 'Loading tournaments...' : tournaments.length ? 'Choose a tournament' : emptyText}</option>
        {tournaments.map((tournament) => (
          <option key={tournament.id} value={tournament.id}>
            {tournament.name}{tournament.status ? ` (${tournament.status})` : ''}
          </option>
        ))}
      </select>
      {error && <small className="field-error">{error}</small>}
    </div>
  )
}

/** Dropdown of a tournament's matches, labelled by team names. */
export function MatchSelect({ id, label = 'Match', tournamentId, value, onChange, filter = null, emptyText = 'No matches available.' }) {
  const { fixtures, loading, error } = useTournamentFixtures(tournamentId)
  const matches = filter ? fixtures.filter(filter) : fixtures

  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <select id={id} value={value} onChange={(event) => onChange(event.target.value)} disabled={!tournamentId || loading || matches.length === 0}>
        <option value="">
          {!tournamentId ? 'Choose a tournament first' : loading ? 'Loading matches...' : matches.length ? 'Choose a match' : emptyText}
        </option>
        {matches.map((match) => (
          <option key={match.id} value={match.id}>
            {matchLabel(match)} ({MATCH_STATUS_LABELS[match.status] || match.status})
          </option>
        ))}
      </select>
      {error && <small className="field-error">{error}</small>}
    </div>
  )
}

/**
 * Search players by name and act on a result.
 * availableOnly: only players without a team.
 */
export function PlayerSearch({ id = 'player-search', label = 'Search players by name', availableOnly = false, actionLabel = 'Select', onSelect, busy = false, excludeIds = [] }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [searching, setSearching] = useState(false)
  const [error, setError] = useState('')
  const term = query.trim()

  useEffect(() => {
    if (term.length < 2) return undefined
    let cancelled = false
    const timer = window.setTimeout(() => {
      setSearching(true)
      setError('')
      const params = new URLSearchParams({ q: term, available_only: String(availableOnly) })
      apiRequest(`/player-team/players/search?${params}`)
        .then((rows) => { if (!cancelled) setResults(Array.isArray(rows) ? rows : []) })
        .catch((err) => { if (!cancelled) { setResults([]); setError(err.message || 'Search failed.') } })
        .finally(() => { if (!cancelled) setSearching(false) })
    }, 300)
    return () => { cancelled = true; window.clearTimeout(timer) }
  }, [term, availableOnly])

  const visible = term.length < 2 ? [] : results.filter((player) => !excludeIds.includes(player.id))

  return (
    <div className="player-search">
      <div className="field">
        <label htmlFor={id}>{label}</label>
        <input
          id={id}
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Type at least 2 letters of a name"
          autoComplete="off"
        />
      </div>
      {error && <div className="notice notice-error" role="alert">{error}</div>}
      {term.length >= 2 && (
        <ul className="search-results" aria-live="polite">
          {searching && <li className="muted">Searching...</li>}
          {!searching && visible.length === 0 && <li className="muted">No matching players{availableOnly ? ' without a team' : ''}.</li>}
          {!searching && visible.map((player) => (
            <li key={player.id}>
              <span>
                <strong>{playerName(player)}</strong>
                <small className="cell-subtitle">{player.team_name ? `Plays for ${player.team_name}` : 'No team yet'}</small>
              </span>
              <button type="button" className="button button-secondary" disabled={busy} onClick={() => onSelect(player)}>
                {actionLabel}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
