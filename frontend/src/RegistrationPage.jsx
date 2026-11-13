import { useCallback, useEffect, useState } from 'react'
import { apiRequest } from './services/api'

const STATUS_OPTIONS = ['pending', 'approved', 'rejected', 'cancelled']

function showDate(value) {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString()
}

export default function RegistrationPage({ initialTournamentId = null }) {
  const [tournamentId, setTournamentId] = useState(
    initialTournamentId ? String(initialTournamentId) : ''
  )
  const [teamId, setTeamId] = useState('')
  const [note, setNote] = useState('')
  const [tournament, setTournament] = useState(null)
  const [profile, setProfile] = useState(null)
  const [teams, setTeams] = useState([])
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [registrations, setRegistrations] = useState([])
  const [loading, setLoading] = useState(false)
  const [checking, setChecking] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [profileLoading, setProfileLoading] = useState(true)
  const [profileSaving, setProfileSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const loadAccountSetup = useCallback(async () => {
    setProfileLoading(true)
    try {
      const result = await apiRequest('/player-team/profile/me')
      setProfile(result || null)

      if (result) {
        const teamResult = await apiRequest('/player-team/teams/me')
        setTeams(Array.isArray(teamResult) ? teamResult : [])
      } else {
        setTeams([])
      }
    } catch (err) {
      setError(err.message || 'Could not load your player profile.')
    } finally {
      setProfileLoading(false)
    }
  }, [])

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
      loadAccountSetup()
      loadRegistrations()
    }, 0)

    return () => window.clearTimeout(timer)
  }, [loadAccountSetup, loadRegistrations])

  async function createProfile(event) {
    event.preventDefault()
    setError('')
    setSuccess('')

    setProfileSaving(true)
    try {
      await apiRequest('/player-team/profile', {
        method: 'POST',
        body: JSON.stringify({
          first_name: firstName.trim(),
          last_name: lastName.trim(),
        }),
      })
      setSuccess('Player profile created successfully.')
      setFirstName('')
      setLastName('')
      await loadAccountSetup()
    } catch (err) {
      setError(err.message || 'Could not create your player profile.')
    } finally {
      setProfileSaving(false)
    }
  }

  async function checkTournament(event) {
    event.preventDefault()
    setError('')
    setSuccess('')
    setTournament(null)
    setTeamId('')

    if (!/^[1-9]\d*$/.test(tournamentId)) {
      setError('Enter a valid tournament ID.')
      return
    }

    setChecking(true)
    try {
      const result = await apiRequest(`/tournaments/${Number(tournamentId)}`)
      const participationType = String(result?.participation_type ?? '').trim().toLowerCase()

      if (!['individual', 'team'].includes(participationType)) {
        throw new Error('This tournament has an invalid participation setting. Please contact the organiser.')
      }

      setTournament({ ...result, participation_type: participationType })
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

    if (!profile) {
      setError('Create your player profile before registering.')
      return
    }

    if (!tournament) {
      setError('Check the tournament first.')
      return
    }

    const isTeam = tournament.participation_type === 'team'
    if (isTeam && !teamId) {
      setError('Select one of your teams.')
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
          <p className="muted">Create your player profile, then register for a tournament.</p>
        </div>
      </div>

      <section className="auth-card">
        <h2>Your player profile</h2>
        {profileLoading ? (
          <p className="muted">Loading player profile...</p>
        ) : profile ? (
          <div className="detail-meta">
            <div><strong>{profile.first_name} {profile.last_name}</strong></div>
            <div className="muted">Player ID: {profile.id}</div>
            <div className="muted">Status: {profile.status}</div>
          </div>
        ) : (
          <form onSubmit={createProfile}>
            <p className="muted">You need a player profile before you can register.</p>
            <div className="field">
              <label htmlFor="profile-first-name">First name</label>
              <input
                id="profile-first-name"
                value={firstName}
                maxLength={100}
                onChange={(event) => setFirstName(event.target.value)}
                required
              />
            </div>
            <div className="field">
              <label htmlFor="profile-last-name">Last name</label>
              <input
                id="profile-last-name"
                value={lastName}
                maxLength={100}
                onChange={(event) => setLastName(event.target.value)}
                required
              />
            </div>
            <button className="button button-primary auth-submit" type="submit" disabled={profileSaving}>
              {profileSaving ? 'Creating profile...' : 'Create player profile'}
            </button>
          </form>
        )}
      </section>

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
          {checking ? 'Checking...' : 'Check tournament'}
        </button>
      </form>

      {tournament && (
        <form className="auth-card" onSubmit={submitRegistration}>
          <h2>{tournament.name}</h2>
          <p className="muted">
            Participation: <strong>{tournament.participation_type === 'team' ? 'Team' : 'Individual'}</strong>
          </p>

          {!profile ? (
            <p className="muted">Create your player profile above before registering.</p>
          ) : tournament.participation_type === 'team' ? (
            <div className="field">
              <label htmlFor="registration-team">Select your team</label>
              <select
                id="registration-team"
                value={teamId}
                onChange={(event) => setTeamId(event.target.value)}
                required
              >
                <option value="">Choose your team</option>
                {teams.map((team) => (
                  <option key={team.id} value={team.id}>
                    {team.name}
                  </option>
                ))}
              </select>
              {teams.length === 0 && (
                <p className="muted">
                  You have no team as captain yet. Open Team options and create a team first.
                </p>
              )}
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
              maxLength={500}
              onChange={(event) => setNote(event.target.value)}
              placeholder="Additional information"
            />
          </div>

          <button
            className="button button-primary auth-submit"
            type="submit"
            disabled={submitting || !profile || (tournament.participation_type === 'team' && teams.length === 0)}
          >
            {submitting ? 'Submitting...' : 'Submit registration'}
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
          {loading ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      {loading && <p>Loading registrations...</p>}
      {!loading && registrations.length === 0 && (
        <div className="detail-card"><p>No registrations found for your account.</p></div>
      )}

      {registrations.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Registration</th>
                <th>Tournament</th>
                <th>Team / Player</th>
                <th>Type</th>
                <th>Status</th>
                <th>Registered</th>
              </tr>
            </thead>
            <tbody>
              {registrations.map((item) => (
                <tr key={item.id}>
                  <td>#{item.id}</td>
                  <td>#{item.tournament_id}</td>
                  <td>{item.team_id ? 'Team registration' : item.player_id ? 'Individual registration' : '—'}</td>
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


