import { useCallback, useEffect, useState } from 'react'
import { apiRequest } from './services/api'

const STATUS_OPTIONS = ['pending', 'approved', 'rejected', 'cancelled']

function showDate(value) {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString()
}

export default function RegistrationPage({ initialTournamentId = null }) {
  const [tournamentId, setTournamentId] = useState(initialTournamentId ? String(initialTournamentId) : '')
  const [teamId, setTeamId] = useState('')
  const [note, setNote] = useState('')
  const [tournament, setTournament] = useState(null)
  const [registrations, setRegistrations] = useState([])
  const [loading, setLoading] = useState(false)
  const [checking, setChecking] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const loadRegistrations = useCallback(async () => {
    setLoading(true)
    try {
      const result = await apiRequest('/registrations/my')
      setRegistrations(Array.isArray(result) ? result : [])
    } catch (err) {
      setError(err.message || 'Could not load your registrations.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      loadRegistrations()
    }, 0)

    return () => window.clearTimeout(timer)
  }, [loadRegistrations])

  async function checkTournament(event) {
    event.preventDefault()
    setError('')
    setSuccess('')
    setTournament(null)

    if (!/^[1-9]\d*$/.test(tournamentId)) {
      setError('Enter a valid tournament ID.')
      return
    }

    setChecking(true)
    try {
      const result = await apiRequest(`/tournaments/${Number(tournamentId)}`)
      if (!['individual', 'team'].includes(result.participation_type)) {
        throw new Error('This tournament has an unsupported participation type.')
      }
      setTournament(result)
    } catch (err) {
      setError(err.message || 'Could not find this tournament.')
    } finally {
      setChecking(false)
    }
  }

  async function submitRegistration(event) {
    event.preventDefault()
    setError('')
    setSuccess('')

    if (!tournament) {
      setError('Check the tournament first.')
      return
    }

    const isTeam = tournament.participation_type === 'team'
    if (isTeam && !/^[1-9]\d*$/.test(teamId)) {
      setError('Enter a valid team ID.')
      return
    }

    setSubmitting(true)
    try {
      await apiRequest(isTeam ? '/registrations/' : '/registrations/player', {
        method: 'POST',
        body: JSON.stringify({
          tournament_id: Number(tournamentId),
          team_id: isTeam ? Number(teamId) : null,
          player_id: null,
          registration_type: isTeam ? 'team' : 'player',
          note: note.trim() || null,
        }),
      })
      setSuccess('Registration submitted. Its initial status is pending.')
      setTeamId('')
      setNote('')
      await loadRegistrations()
    } catch (err) {
      setError(err.message || 'Registration failed. Check your eligibility and permissions.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">TOURNAMENT PARTICIPATION</p>
          <h1>Tournament registration</h1>
          <p className="muted">Choose a tournament. Its participation type determines how you register.</p>
        </div>
      </div>

      <form className="auth-card" onSubmit={checkTournament}>
        <h2>Find a tournament</h2>
        <div className="field">
          <label htmlFor="registration-tournament">Tournament ID</label>
          <input
            id="registration-tournament"
            type="number"
            min="1"
            value={tournamentId}
            onChange={(event) => {
              setTournamentId(event.target.value)
              setTournament(null)
            }}
            required
          />
        </div>
        <button className="button button-primary auth-submit" type="submit" disabled={checking}>
          {checking ? 'Checking…' : 'Check tournament'}
        </button>
      </form>

      {tournament && (
        <form className="auth-card" onSubmit={submitRegistration}>
          <h2>{tournament.name}</h2>
          <p className="muted">
            Participation: <strong>{tournament.participation_type === 'team' ? 'Team' : 'Individual'}</strong>
          </p>

          {tournament.participation_type === 'team' ? (
            <div className="field">
              <label htmlFor="registration-team">Your team ID</label>
              <input
                id="registration-team"
                type="number"
                min="1"
                value={teamId}
                onChange={(event) => setTeamId(event.target.value)}
                required
              />
              <p className="muted">Only the team captain can register the team.</p>
            </div>
          ) : (
            <p className="muted">You will be registered using your own player profile.</p>
          )}

          <div className="field">
            <label htmlFor="registration-note">Note (optional)</label>
            <input
              id="registration-note"
              value={note}
              maxLength="500"
              onChange={(event) => setNote(event.target.value)}
              placeholder="Additional information"
            />
          </div>

          <button className="button button-primary auth-submit" type="submit" disabled={submitting}>
            {submitting ? 'Submitting…' : 'Submit registration'}
          </button>
        </form>
      )}

      {error && <p role="alert" className="notice notice-error">{error}</p>}
      {success && <p role="status" className="notice notice-success">{success}</p>}

      <div className="section-title">
        <div>
          <h2>My registrations</h2>
          <p className="muted">Review your registration details and status.</p>
        </div>
        <button className="button button-secondary" onClick={loadRegistrations} disabled={loading}>
          {loading ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      {loading && <p>Loading registrations…</p>}
      {!loading && registrations.length === 0 && (
        <div className="detail-card"><p>No registrations found for your account.</p></div>
      )}

      {registrations.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Registration</th><th>Tournament</th><th>Team / Player</th>
                <th>Type</th><th>Status</th><th>Registered</th>
              </tr>
            </thead>
            <tbody>
              {registrations.map((item) => (
                <tr key={item.id}>
                  <td>#{item.id}</td>
                  <td>#{item.tournament_id}</td>
                  <td>{item.team_id ? `Team #${item.team_id}` : item.player_id ? `Player #${item.player_id}` : '—'}</td>
                  <td>{item.registration_type || '—'}</td>
                  <td>
                    <span className={STATUS_OPTIONS.includes(String(item.status).toLowerCase()) ? `status status-${String(item.status).toLowerCase()}` : ''}>
                      {item.status || 'Unknown'}
                    </span>
                  </td>
                  <td>{showDate(item.registered_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
