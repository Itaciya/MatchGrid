import { useEffect, useState } from 'react'
import { getFixtures, getScoreForReview, reviewScore } from './services/resultsApi'

const box = { border: '1px solid rgba(128,128,128,.4)', borderRadius: 8, padding: 16, marginBottom: 12 }

function MatchRow({ fixture }) {
  const [score, setScore] = useState(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    getScoreForReview(fixture.id)
      .then((s) => { if (!cancelled) setScore(s) })
      .catch((err) => { if (cancelled) return; if (/no score/i.test(err.message)) setNote('No score submitted yet.'); else setError(err.message) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [fixture.id])

  async function decide(status) {
    setBusy(true)
    setError('')
    try {
      setScore(await reviewScore(fixture.id, status))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const reviewable = score && score.verification_status !== 'verified'

  return (
    <div style={box}>
      <strong>Match {fixture.match_number}</strong>
      {' '}(Team {fixture.team_a_id ?? 'TBD'} vs Team {fixture.team_b_id ?? 'TBD'})
      {loading && <div>Loading score...</div>}
      {note && <div style={{ opacity: 0.7 }}>{note}</div>}
      {score && (
        <div style={{ margin: '8px 0' }}>
          Submitted score: <b>{score.team_a_score} - {score.team_b_score}</b>
          {' '}<span className="status-pill">{score.verification_status}</span>
        </div>
      )}
      {reviewable && (
        <div style={{ display: 'flex', gap: 8 }}>
          <button type="button" disabled={busy} onClick={() => decide('verified')}>Approve</button>
          <button type="button" disabled={busy} onClick={() => decide('rejected')}>Reject</button>
        </div>
      )}
      {error && <div className="notice notice-error" role="alert">{error}</div>}
    </div>
  )
}

export default function VerificationPage() {
  const [tournamentId, setTournamentId] = useState('')
  const [fixtures, setFixtures] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function load(event) {
    event.preventDefault()
    setError('')
    setFixtures([])
    if (!/^[1-9]\d*$/.test(tournamentId)) {
      setError('Enter a valid tournament ID.')
      return
    }
    setLoading(true)
    try {
      const rows = await getFixtures(Number(tournamentId))
      setFixtures(Array.isArray(rows) ? rows : [])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <section>
      <h2>Score verification</h2>
      <p style={{ fontSize: 13, opacity: 0.7 }}>
        Organisers review submitted scores for their own tournaments. The server enforces access.
      </p>
      <form onSubmit={load} style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <input
          inputMode="numeric"
          value={tournamentId}
          onChange={(e) => setTournamentId(e.target.value)}
          placeholder="Tournament ID"
          aria-label="Tournament ID"
        />
        <button type="submit" disabled={loading}>{loading ? 'Loading...' : 'Load matches'}</button>
      </form>
      {error && <div className="notice notice-error" role="alert">{error}</div>}
      {fixtures.map((f) => <MatchRow key={f.id} fixture={f} />)}
    </section>
  )
}