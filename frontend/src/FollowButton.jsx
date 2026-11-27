import { useEffect, useState } from 'react'
import { apiRequest } from './services/api'

/** Follow a tournament to get notified about fixtures, live matches and results. */
export function FollowButton({ tournamentId }) {
  const [state, setState] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    apiRequest(`/tournaments/${tournamentId}/follow`)
      .then((result) => { if (!cancelled) setState(result) })
      .catch(() => { if (!cancelled) setState(null) })
    return () => { cancelled = true }
  }, [tournamentId])

  async function toggle() {
    setBusy(true)
    setError('')
    try {
      setState(await apiRequest(`/tournaments/${tournamentId}/follow`, {
        method: state?.following ? 'DELETE' : 'POST',
      }))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  if (!state) return null

  return (
    <span className="follow-control">
      <button
        type="button"
        className={`button ${state.following ? 'button-secondary' : 'button-primary'}`}
        onClick={toggle}
        disabled={busy}
        aria-pressed={state.following}
        title={state.following ? 'You get notified about fixtures, live matches and results' : 'Get notified about fixtures, live matches and results'}
      >
        {state.following ? '✓ Following' : '☆ Follow'}
      </button>
      <span className="muted small">{state.followers} {state.followers === 1 ? 'follower' : 'followers'}</span>
      {error && <span className="field-error">{error}</span>}
    </span>
  )
}
