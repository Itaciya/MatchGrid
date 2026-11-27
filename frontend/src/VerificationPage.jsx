import { useEffect, useState } from 'react'
import { finalizeResult, getFinalizedResult, getScoreForReview, reviewScore } from './services/resultsApi'
import { TournamentSelect } from './components/Pickers'
import { MATCH_STATUS_LABELS as STATUS_LABELS, matchLabel } from './components/pickerUtils'
import { useTournamentFixtures } from './components/useTournamentFixtures'
import { useMatchStatus } from './realtime/useMatchStatus'
import { useMatchSubscriptions } from './realtime/useMatchSubscriptions'

function MatchRow({ fixture, liveStatus }) {
  const [score, setScore] = useState(null)
  const [savedStatus, setMatchStatus] = useState(fixture.status)
  // A status pushed live (e.g. the scorer just ended the match) wins.
  const matchStatus = liveStatus || savedStatus
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
  }, [fixture.id, liveStatus])

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

  // Review only after the scorer ends the match: a verified score is locked,
  // so verifying mid-match would stop the scorer recording later points.
  const matchEnded = matchStatus === 'completed'
  const verification = score?.verification_status
  const canReview = Boolean(score) && verification === 'pending' && matchEnded && !published && !error
  const canFinalize = Boolean(score) && verification === 'verified' && matchStatus === 'completed' && !published && !error

  return (
    <div className="detail-card match-review-card">
      <div className="match-review-heading">
        <strong>{matchLabel(fixture)}</strong>
        <span className="status-pill">{STATUS_LABELS[matchStatus] || matchStatus}</span>
      </div>
      {loading && <p className="muted">Loading score...</p>}
      {note && <p className="muted">{note}</p>}
      {score && (
        <p>
          Submitted score: <b>{fixture.team_a_name || 'Team A'} {score.team_a_score} - {score.team_b_score} {fixture.team_b_name || 'Team B'}</b>
          {' '}<span className="status-pill">{published ? 'published' : verification}</span>
        </p>
      )}

      {score && !matchEnded && verification === 'pending' && (
        <p className="muted">You can review this score once the scorer ends the match.</p>
      )}
      {verification === 'rejected' && (
        <p className="muted">Rejected. Waiting for the scorer to submit a corrected score.</p>
      )}

      {canReview && (
        <div className="table-actions">
          <button type="button" className="button button-primary" disabled={busy} onClick={() => decide('verified')}>Verify score</button>
          <button type="button" className="button button-secondary" disabled={busy} onClick={() => decide('rejected')}>Reject</button>
        </div>
      )}
      {canFinalize && (
        <div className="table-actions">
          <button type="button" className="button button-primary" disabled={busy} onClick={finalize}>
            {busy ? 'Publishing...' : 'Finalize & publish result'}
          </button>
        </div>
      )}
      {published && <p className="muted">The official result is published.</p>}

      {error && <div className="notice notice-error" role="alert">{error}</div>}
      {ok && <div className="notice notice-success" role="status">{ok}</div>}
    </div>
  )
}

export default function VerificationPage({ currentUser, initialTournamentId = null }) {
  const [tournamentId, setTournamentId] = useState(initialTournamentId ? String(initialTournamentId) : '')
  const { fixtures, loading, error } = useTournamentFixtures(tournamentId)
  const playable = fixtures.filter((fixture) => fixture.status !== 'bye' && fixture.status !== 'cancelled')
  const liveStatuses = useMatchStatus()
  useMatchSubscriptions(playable.map((fixture) => fixture.id))

  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">ORGANISER WORKSPACE</p>
          <h1>Verify scores</h1>
          <p className="muted">Review the scores your scorers submitted, then finalize and publish official results.</p>
        </div>
      </div>
      <div className="lookup-card">
        <TournamentSelect
          id="verify-tournament"
          label="Your tournament"
          value={tournamentId}
          onChange={setTournamentId}
          ownerId={currentUser?.id ?? null}
          emptyText="You have not created any tournaments yet."
        />
      </div>
      {loading && <p className="muted">Loading matches...</p>}
      {error && <div className="notice notice-error" role="alert">{error}</div>}
      {tournamentId && !loading && !error && playable.length === 0 && (
        <div className="detail-card"><p>This tournament has no matches yet. Create and publish fixtures first.</p></div>
      )}
      {playable.map((f) => <MatchRow key={f.id} fixture={f} liveStatus={liveStatuses[f.id]} />)}
    </>
  )
}
