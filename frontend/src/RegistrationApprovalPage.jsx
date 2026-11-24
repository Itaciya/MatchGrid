import { useCallback, useEffect, useState } from 'react'
import { apiRequest } from './services/api'
import { TournamentSelect } from './components/Pickers'

function participantLabel(item) {
  if (item.team_id) return item.team_name || 'Unnamed team'
  if (item.player_id) return item.player_name || 'Unnamed player'
  return '-'
}

export default function RegistrationApprovalPage({ currentUser }) {
  const [tournamentId, setTournamentId] = useState('')
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const [actionId, setActionId] = useState(null)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const loadPending = useCallback(async (id) => {
    setError('')
    setLoading(true)
    try {
      const result = await apiRequest(`/registrations/pending/${Number(id)}`)
      setItems(Array.isArray(result) ? result : [])
    } catch (err) {
      setItems([])
      setError(err.message || 'Could not load pending registrations.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!tournamentId) return undefined
    const timer = window.setTimeout(() => loadPending(tournamentId), 0)
    return () => window.clearTimeout(timer)
  }, [tournamentId, loadPending])

  async function reviewRegistration(item, decision) {
    const name = participantLabel(item)
    const question = decision === 'approve'
      ? `Approve ${name} for this tournament?`
      : `Reject ${name}? They will be notified and cannot be approved later.`
    if (!window.confirm(question)) return

    setError('')
    setSuccess('')
    setActionId(item.id)

    try {
      await apiRequest(`/registrations/${item.id}/${decision}`, { method: 'PATCH' })
      await loadPending(tournamentId)
      setSuccess(`${name} ${decision === 'approve' ? 'approved' : 'rejected'}.`)
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
          <p className="eyebrow">ORGANISER WORKSPACE</p>
          <h1>Registration approvals</h1>
          <p className="muted">Choose one of your tournaments to review the teams and players waiting for approval.</p>
        </div>
      </div>

      <div className="lookup-card">
        <TournamentSelect
          id="approval-tournament"
          label="Your tournament"
          value={tournamentId}
          onChange={(value) => { setTournamentId(value); setItems([]); setSuccess('') }}
          ownerId={currentUser?.id ?? null}
          emptyText="You have not created any tournaments yet."
        />
      </div>

      {error && <p role="alert" className="notice notice-error">{error}</p>}
      {success && <p role="status" className="notice notice-success">{success}</p>}

      {loading && <p className="muted">Loading pending registrations...</p>}

      {!loading && tournamentId && items.length === 0 && !error && (
        <div className="detail-card">
          <p>No registrations are waiting for review in this tournament.</p>
        </div>
      )}

      {items.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Team / Player</th>
                <th>Type</th>
                <th>Registered</th>
                <th>Note</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id}>
                  <td><strong>{participantLabel(item)}</strong></td>
                  <td>{item.registration_type === 'team' ? 'Team' : 'Individual'}</td>
                  <td>{item.registered_at ? new Date(item.registered_at).toLocaleDateString() : '-'}</td>
                  <td>{item.note || '-'}</td>
                  <td>
                    <div className="table-actions">
                      <button
                        className="button button-primary"
                        disabled={actionId !== null}
                        onClick={() => reviewRegistration(item, 'approve')}
                      >
                        {actionId === item.id ? 'Saving...' : 'Approve'}
                      </button>
                      <button
                        className="button button-secondary"
                        disabled={actionId !== null}
                        onClick={() => reviewRegistration(item, 'reject')}
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
