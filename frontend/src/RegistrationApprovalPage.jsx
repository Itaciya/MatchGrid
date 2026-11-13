import { useState } from 'react'
import { apiRequest } from './services/api'

export default function RegistrationApprovalPage() {
  const [tournamentId, setTournamentId] = useState('')
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const [actionId, setActionId] = useState(null)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  async function loadPending(event) {
    event?.preventDefault()
    setError('')
    setSuccess('')

    if (!/^[1-9]\d*$/.test(tournamentId)) {
      setError('Enter a valid positive tournament ID.')
      return
    }

    setLoading(true)
    try {
      const result = await apiRequest(`/registrations/pending/${Number(tournamentId)}`)
      setItems(Array.isArray(result) ? result : [])
    } catch (err) {
      setError(err.message || 'Could not load pending registrations.')
    } finally {
      setLoading(false)
    }
  }

  async function reviewRegistration(id, decision) {
    setError('')
    setSuccess('')
    setActionId(id)

    try {
      await apiRequest(`/registrations/${id}/${decision}`, {
        method: 'PATCH',
      })
      await loadPending()
      setSuccess(
        `Registration #${id} ${decision === 'approve' ? 'approved' : 'rejected'}.`
      )
    } catch (err) {
      setError(err.message || `Could not ${decision} this registration.`)
    } finally {
      setActionId(null)
    }
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">ORGANIZER WORKSPACE</p>
          <h1>Registration approvals</h1>
          <p className="muted">Review pending team and player registrations.</p>
        </div>
      </div>

      <form className="lookup-card" onSubmit={loadPending}>
        <div className="field">
          <label htmlFor="approval-tournament-id">Tournament ID</label>
          <input
            id="approval-tournament-id"
            type="number"
            min="1"
            value={tournamentId}
            onChange={(event) => setTournamentId(event.target.value)}
            required
          />
        </div>
        <button className="button button-primary" type="submit" disabled={loading}>
          {loading ? 'Loadingâ€¦' : 'Load pending registrations'}
        </button>
      </form>

      {error && <p role="alert" className="notice notice-error">{error}</p>}
      {success && <p role="status" className="notice notice-success">{success}</p>}

      {loading && <p>Loading pending registrationsâ€¦</p>}

      {!loading && items.length === 0 && tournamentId && !error && (
        <div className="detail-card">
          <p>There are no pending registrations to review right now.</p>
        </div>
      )}

      {items.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Registration</th>
                <th>Tournament</th>
                <th>Team / Player</th>
                <th>Type</th>
                <th>Note</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id}>
                  <td>#{item.id}</td>
                  <td>#{item.tournament_id}</td>
                  <td>{item.team_id ? 'Team registration' : item.player_id ? 'Individual registration' : '—'}</td>
                  <td>{item.registration_type || 'â€”'}</td>
                  <td>{item.note || 'â€”'}</td>
                  <td>
                    <div className="table-actions">
                      <button
                        className="button button-primary"
                        disabled={actionId !== null}
                        onClick={() => reviewRegistration(item.id, 'approve')}
                      >
                        {actionId === item.id ? 'Savingâ€¦' : 'Approve'}
                      </button>
                      <button
                        className="button button-secondary"
                        disabled={actionId !== null}
                        onClick={() => reviewRegistration(item.id, 'reject')}
                      >
                        Reject
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

