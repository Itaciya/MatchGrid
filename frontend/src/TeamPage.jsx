import { useCallback, useEffect, useState } from 'react'
import { apiRequest } from './services/api'
import { PlayerSearch } from './components/Pickers'
import { playerName } from './components/pickerUtils'

function statusClass(value) {
  return `status-pill status-${String(value || 'unknown').toLowerCase().replace(/[^a-z0-9]+/g, '-')}`
}

function Notice({ kind, children }) {
  if (!children) return null
  return (
    <div className={`notice notice-${kind}`} role={kind === 'error' ? 'alert' : 'status'}>
      {children}
    </div>
  )
}

function TeamCreationForm({ onCreated, onCancel }) {
  const [name, setName] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function submitTeam(event) {
    event.preventDefault()
    setError('')
    const cleanName = name.trim()
    if (!cleanName) {
      setError('Team name is required.')
      return
    }

    setLoading(true)
    try {
      const createdTeam = await apiRequest('/player-team/team', {
        method: 'POST',
        body: JSON.stringify({ name: cleanName }),
      })
      setName('')
      onCreated(createdTeam)
    } catch (requestError) {
      setError(requestError.message || 'Could not create the team.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <form className="form-card" onSubmit={submitTeam}>
      <div className="field">
        <label htmlFor="new-team-name">Team name *</label>
        <input
          id="new-team-name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          maxLength={100}
          placeholder="e.g. Dhaka Strikers"
          required
        />
        <small>Up to 100 characters. Each team needs a unique name.</small>
      </div>

      <Notice kind="error">{error}</Notice>

      <div className="form-footer">
        <p className="muted">You will be the captain of this team.</p>
        <div className="table-actions">
          {onCancel && <button type="button" className="button button-secondary" onClick={onCancel}>Cancel</button>}
          <button className="button button-primary" type="submit" disabled={loading}>
            {loading ? 'Creating team...' : 'Create team'}
          </button>
        </div>
      </div>
    </form>
  )
}

function PlayerCard({ player, onClose }) {
  return (
    <div className="detail-card">
      <div className="detail-heading">
        <div><span className="eyebrow">PLAYER PROFILE</span><h2>{playerName(player)}</h2></div>
        <span className={statusClass(player.status)}>{player.status || 'Unknown'}</span>
      </div>
      <div className="detail-meta">
        <div className="meta-item"><span>Team</span><strong>{player.team_name || 'No team yet'}</strong></div>
        {player.created_at && <div className="meta-item"><span>Joined MatchGrid</span><strong>{new Date(player.created_at).toLocaleDateString()}</strong></div>}
      </div>
      {onClose && <button type="button" className="button button-secondary" onClick={onClose}>Close</button>}
    </div>
  )
}

export default function TeamPage() {
  const [teams, setTeams] = useState([])
  const [selectedTeamId, setSelectedTeamId] = useState('')
  const [team, setTeam] = useState(null)
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [viewedPlayer, setViewedPlayer] = useState(null)

  const loadTeam = useCallback(async (teamId) => {
    if (!teamId) {
      setTeam(null)
      return
    }
    try {
      setTeam(await apiRequest(`/player-team/team/${teamId}`))
    } catch (err) {
      setError(err.message || 'Could not load the team.')
    }
  }, [])

  const loadMyTeams = useCallback(async (preferredId = null) => {
    setLoading(true)
    setError('')
    try {
      const rows = await apiRequest('/player-team/teams/me')
      const list = Array.isArray(rows) ? rows : []
      setTeams(list)
      const nextId = preferredId ?? list[0]?.id ?? ''
      setSelectedTeamId(nextId ? String(nextId) : '')
      await loadTeam(nextId)
      setCreating(list.length === 0)
    } catch (err) {
      setError(err.message || 'Could not load your teams.')
    } finally {
      setLoading(false)
    }
  }, [loadTeam])

  useEffect(() => {
    const timer = window.setTimeout(() => loadMyTeams(), 0)
    return () => window.clearTimeout(timer)
  }, [loadMyTeams])

  async function changeRoster(action, player) {
    if (!team) return
    const name = playerName(player)
    if (action === 'remove' && !window.confirm(`Remove ${name} from ${team.name}?`)) return

    setError('')
    setSuccess('')
    setBusy(true)
    try {
      const endpoint = `/player-team/team/${team.id}/players/${player.id}`
      await apiRequest(endpoint, { method: action === 'add' ? 'POST' : 'DELETE' })
      await loadTeam(team.id)
      setSuccess(action === 'add' ? `${name} joined ${team.name}.` : `${name} was removed from ${team.name}.`)
    } catch (err) {
      setError(err.message || 'Could not update the roster.')
    } finally {
      setBusy(false)
    }
  }

  async function viewProfile(player) {
    setError('')
    try {
      const profile = await apiRequest(`/player-team/profile/${player.id}`)
      setViewedPlayer({ ...profile, team_name: player.team_name ?? (profile.team_id === team?.id ? team?.name : null) })
    } catch (err) {
      setError(err.message || 'Could not load the player profile.')
    }
  }

  const rosterIds = Array.isArray(team?.players) ? team.players.map((player) => player.id) : []

  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">PLAYER TEAMS</p>
          <h1>My teams</h1>
          <p className="muted">Create a team, then find players by name and add them to your roster.</p>
        </div>
        {!creating && teams.length > 0 && (
          <button type="button" className="button button-primary" onClick={() => setCreating(true)}>+ Create another team</button>
        )}
      </div>

      <Notice kind="error">{error}</Notice>
      <Notice kind="success">{success}</Notice>
      {loading && <div className="loading-state"><span className="spinner" />Loading your teams...</div>}

      {!loading && creating && (
        <>
          <div className="section-title">
            <div>
              <h2>{teams.length ? 'Create another team' : 'Create your first team'}</h2>
              <p className="muted">{teams.length ? 'You can captain more than one team.' : 'You are not captain of a team yet. Create one to start building a roster.'}</p>
            </div>
          </div>
          <TeamCreationForm
            onCreated={(created) => { setSuccess(`Team "${created.name}" created. You are its captain.`); loadMyTeams(created.id) }}
            onCancel={teams.length ? () => setCreating(false) : null}
          />
        </>
      )}

      {!loading && !creating && team && (
        <>
          {teams.length > 1 && (
            <div className="lookup-card">
              <div className="field">
                <label htmlFor="my-team-select">Team</label>
                <select id="my-team-select" value={selectedTeamId} onChange={(event) => { setSelectedTeamId(event.target.value); setSuccess(''); loadTeam(event.target.value) }}>
                  {teams.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                </select>
              </div>
            </div>
          )}

          <div className="detail-card">
            <div className="detail-heading">
              <div><span className="eyebrow">YOUR TEAM</span><h2>{team.name}</h2></div>
              <span className={statusClass(team.status)}>{team.status || 'Unknown'}</span>
            </div>
            <p className="muted">{rosterIds.length} {rosterIds.length === 1 ? 'player' : 'players'} on the roster.</p>
          </div>

          <div className="section-title"><div><h2>Roster</h2></div></div>
          {rosterIds.length > 0 ? (
            <div className="table-wrap">
              <table>
                <thead><tr><th>Player</th><th>Status</th><th>Actions</th></tr></thead>
                <tbody>
                  {team.players.map((rosterPlayer) => (
                    <tr key={rosterPlayer.id}>
                      <td><strong>{playerName(rosterPlayer)}</strong></td>
                      <td><span className={statusClass(rosterPlayer.status)}>{rosterPlayer.status || 'Unknown'}</span></td>
                      <td><div className="table-actions">
                        <button type="button" className="button button-secondary" onClick={() => viewProfile({ ...rosterPlayer, team_name: team.name })} disabled={busy}>View profile</button>
                        <button type="button" className="button button-secondary" onClick={() => changeRoster('remove', rosterPlayer)} disabled={busy}>Remove</button>
                      </div></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="detail-card"><p>No players yet. Search for players below and add them to your team.</p></div>
          )}

          <div className="section-title">
            <div>
              <h2>Add players</h2>
              <p className="muted">Only active players who are not on another team are shown.</p>
            </div>
          </div>
          <div className="lookup-card">
            <PlayerSearch
              id="add-player-search"
              label="Player name"
              availableOnly
              actionLabel="Add to team"
              busy={busy}
              excludeIds={rosterIds}
              onSelect={(player) => changeRoster('add', player)}
            />
          </div>
        </>
      )}

      {!loading && (
        <>
          <div className="section-title">
            <div>
              <h2>Find a player</h2>
              <p className="muted">Look up any player by name to see their profile and team.</p>
            </div>
          </div>
          <div className="lookup-card">
            <PlayerSearch id="find-player-search" label="Player name" actionLabel="View profile" onSelect={viewProfile} />
          </div>
          {viewedPlayer && <PlayerCard player={viewedPlayer} onClose={() => setViewedPlayer(null)} />}
        </>
      )}
    </>
  )
}
