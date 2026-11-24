import { useEffect, useState } from 'react'
import { getPublicResult } from './services/resultsApi'
import { MatchSelect, TournamentSelect } from './components/Pickers'
import { teamLabel } from './components/pickerUtils'

function winnerLabel(result) {
  if (result.winner_team_id == null) return 'No winner (draw)'
  return result.winner_team_name || 'Winner to be confirmed'
}

export default function ResultPage() {
  const [tournamentId, setTournamentId] = useState('')
  const [matchId, setMatchId] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!matchId) return undefined
    let cancelled = false
    const timer = window.setTimeout(() => {
      setLoading(true)
      setError('')
      setResult(null)
      getPublicResult(Number(matchId))
        .then((value) => { if (!cancelled) setResult(value) })
        .catch((err) => { if (!cancelled) setError(err.message) })
        .finally(() => { if (!cancelled) setLoading(false) })
    }, 0)
    return () => { cancelled = true; window.clearTimeout(timer) }
  }, [matchId])

  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">RESULTS</p>
          <h1>Match results</h1>
          <p className="muted">Pick a tournament and an ended match to see its official result.</p>
        </div>
      </div>

      <div className="lookup-card picker-row">
        <TournamentSelect
          id="result-tournament"
          value={tournamentId}
          onChange={(value) => { setTournamentId(value); setMatchId(''); setResult(null); setError('') }}
          filter={(tournament) => tournament.fixtures_published}
          emptyText="No tournaments have published fixtures yet."
        />
        <MatchSelect
          id="result-match"
          tournamentId={tournamentId}
          value={matchId}
          onChange={setMatchId}
          filter={(match) => match.status === 'completed'}
          emptyText="No ended matches in this tournament yet."
        />
      </div>

      {loading && <p className="muted">Loading result...</p>}
      {error && <div className="notice notice-error" role="alert">{error}</div>}
      {result && (
        <div className="detail-card result-card">
          <span className="status-pill status-completed">Official result</span>
          <div className="result-scoreline">
            <span>{teamLabel(result.team_a_name, true)}</span>
            <strong>{result.team_a_score} - {result.team_b_score}</strong>
            <span>{teamLabel(result.team_b_name, true)}</span>
          </div>
          <p>Winner: <b>{winnerLabel(result)}</b></p>
          <p className="muted">Finalized {new Date(result.finalized_at).toLocaleString()}</p>
        </div>
      )}
    </>
  )
}
