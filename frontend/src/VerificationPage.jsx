import { useEffect, useState } from 'react'
import { finalizeResult, getFinalizedResult, getFixtures, getScoreForReview, reviewScore } from './services/resultsApi'

const box = { border: '1px solid rgba(128,128,128,.4)', borderRadius: 8, padding: 16, marginBottom: 12 }

const STATUS_LABELS = {
  scheduled: 'Scheduled',
  live: 'Live',
  paused: 'Paused',
  completed: 'Ended',
  cancelled: 'Cancelled',
}

function MatchRow({ fixture }) {
  const [score, setScore] = useState(null)
  const [matchStatus, setMatchStatus] = useState(fixture.status)
  const [published, setPublished] = useState(false)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState('')
  const [error, setError] = useState('')
  const [ok, setOk] = useState('')

  useEffect(() => {
    let cancelled = false

    async function loadMatchData() {
      const [scoreResult, publishedResult] = await Promise.allSettled([
        getScoreForReview(fixture.id),
        getFinalizedResult(fixture.id),
      ])

      if (cancelled) return

      if (scoreResult.status === 'fulfilled') {
        setScore(scoreResult.value)
      } else if (scoreResult.reason?.status === 404) {
        setNote('No score has been submitted yet.')
      } else {
        setError(scoreResult.reason?.message || 'Could not load the score.')
      }

      if (publishedResult.status === 'fulfilled') {
        setPublished(true)
      } else if (publishedResult.reason?.status === 404) {
        setPublished(false)
      } else {
        setError((current) => current || publishedResult.reason?.message || 'Could not check the published result.')
      }

      setLoading(false)
    }

    loadMatchData()
    return () => { cancelled = true }
  }, [fixture.id])

  async function decide(status) {
    setBusy(true)
    setError('')
    setOk('')
    try {
      setScore(await reviewScore(fixture.id, status))
      setOk(status === 'verified' ? 'Score verified. You can now finalize and publish the result.' : 'Score rejected. The scorer needs to correct it.')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function finalize() {
    if (!window.confirm('Finalize and publish this result? It becomes official and public.')) return
    setBusy(true)
    setError('')
    setOk('')
    try {
      await finalizeResult(fixture.id)
      setMatchStatus('completed')
      setPublished(true)
      setOk('Result finalized and published.')
    } catch (err) {
      setError(err.message)
      // Already finalized earlier: reflect that instead of offering the button again.
      if (err.status === 409 && /already been finalized/i.test(err.serverMessage || '')) setPublished(true)
    } finally {
      setBusy(false)
    }
  }

  const matchStarted = matchStatus === 'live' || matchStatus === 'completed'
  const verification = score?.verification_status
  const canReview = Boolean(score) && verification === 'pending' && matchStarted && !published && !error
  const canFinalize = Boolean(score) && verification === 'verified' && matchStatus === 'completed' && !published && !error

  return (
    <div style={box}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
        <span>
          <strong>Match {fixture.match_number}</strong>
          {' '}(Team {fixture.team_a_id ?? 'TBD'} vs Team {fixture.team_b_id ?? 'TBD'})
        </span>
        <span className="status-pill">Match: {STATUS_LABELS[matchStatus] || matchStatus}</span>
      </div>
      {loading && <div>Loading score...</div>}
      {note && <div style={{ opacity: 0.7 }}>{note}</div>}
      {score && (
        <div style={{ margin: '8px 0' }}>
          Submitted score: <b>{score.team_a_score} - {score.team_b_score}</b>
          {' '}<span className="status-pill">{published ? 'published' : verification}</span>
        </div>
      )}

      {score && !matchStarted && (
        <div style={{ fontSize: 13, opacity: 0.7 }}>Scores can be reviewed once the match has started.</div>
      )}
      {matchStatus === 'live' && canReview && (
        <div style={{ fontSize: 13, opacity: 0.7, marginBottom: 6 }}>
          The match is still live. You can verify now or wait until the scorer ends it.
        </div>
      )}
      {verification === 'verified' && matchStatus === 'live' && !published && (
        <div style={{ fontSize: 13, opacity: 0.7 }}>
          Score verified. The result can be finalized once the scorer ends the match.
        </div>
      )}
      {verification === 'rejected' && (
        <div style={{ fontSize: 13, opacity: 0.7 }}>Rejected. Waiting for the scorer to submit a corrected score.</div>
      )}

      {canReview && (
        <div style={{ display: 'flex', gap: 8 }}>
          <button type="button" disabled={busy} onClick={() => decide('verified')}>Verify score</button>
          <button type="button" disabled={busy} onClick={() => decide('rejected')}>Reject</button>
        </div>
      )}
      {canFinalize && (
        <div style={{ display: 'flex', gap: 8 }}>
          <button type="button" disabled={busy} onClick={finalize}>
            {busy ? 'Publishing...' : 'Finalize & publish result'}
          </button>
        </div>
      )}
      {published && <div style={{ fontSize: 13, opacity: 0.7 }}>The official result is published.</div>}

      {error && <div className="notice notice-error" role="alert">{error}</div>}
      {ok && <div className="notice notice-success" role="status">{ok}</div>}
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