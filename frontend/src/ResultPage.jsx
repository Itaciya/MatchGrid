import { useState } from 'react'
import { getPublicResult } from './services/resultsApi'

const box = { border: '1px solid rgba(128,128,128,.4)', borderRadius: 8, padding: 16, marginTop: 12 }

function winnerLabel(result) {
  if (result.winner_team_id != null) return `Team ${result.winner_team_id}`
  return 'No winner (draw)'
}

export default function ResultPage() {
  const [matchId, setMatchId] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function onSubmit(event) {
    event.preventDefault()
    setError('')
    setResult(null)
    if (!/^[1-9]\d*$/.test(matchId)) {
      setError('Enter a valid match ID.')
      return
    }
    setLoading(true)
    try {
      setResult(await getPublicResult(Number(matchId)))
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <section>
      <h2>Match result</h2>
      <p style={{ fontSize: 13, opacity: 0.7 }}>
        Only completed matches with a verified score, in tournaments with published fixtures, are shown.
      </p>
      <form onSubmit={onSubmit} style={{ display: 'flex', gap: 8 }}>
        <input
          inputMode="numeric"
          value={matchId}
          onChange={(e) => setMatchId(e.target.value)}
          placeholder="Match ID"
          aria-label="Match ID"
        />
        <button type="submit" disabled={loading}>{loading ? 'Loading...' : 'View result'}</button>
      </form>
      {error && <div className="notice notice-error" role="alert">{error}</div>}
      {result && (
        <div style={box}>
          <div><strong>Match {result.match_id}</strong> <span className="status-pill">Verified result</span></div>
          <div style={{ fontSize: 28, margin: '8px 0' }}>
            Team A {result.team_a_score} - {result.team_b_score} Team B
          </div>
          <div>Winner: <b>{winnerLabel(result)}</b></div>
          <div style={{ fontSize: 13, opacity: 0.7 }}>
            Outcome: {result.outcome} · Finalized {new Date(result.finalized_at).toLocaleString()}
          </div>
        </div>
      )}
    </section>
  )
}