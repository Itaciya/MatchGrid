import { useEffect, useState } from 'react'
import { endMatch, getMyMatches, getScore, saveScore, startMatch } from './services/scorerApi'
import { useLiveScores } from './realtime/useLiveScores'
import { useMatchStatus } from './realtime/useMatchStatus'
import { useRealtimeStatus } from './realtime/useRealtime'
import { wsClient } from './realtime/websocketClient'

// Adapter: the only place that knows the backend's match field names.
function normalize(m) {
  return {
    id: m.id,
    number: m.match_number,
    teamA: m.team_a_name || (m.team_a_id ? 'Team to be confirmed' : 'TBD'),
    teamB: m.team_b_name || (m.team_b_id ? 'Team to be confirmed' : 'TBD'),
    tournament: m.tournament_name ?? '',
    venue: m.venue_name ?? '',
    role: m.assignment_type ?? '',
    scheduled: m.scheduled_at ?? null,
    status: m.status ?? '',
    a: '',
    b: '',
  }
}

const toScore = (v) => (/^\d+$/.test(String(v).trim()) ? Number(v) : null)

const STATUS_LABELS = {
  scheduled: 'Scheduled',
  live: 'Live',
  paused: 'Paused',
  completed: 'Ended',
  cancelled: 'Cancelled',
}

function MatchCard({ match, live, liveStatus }) {
  const [a, setA] = useState(String(match.a))
  const [b, setB] = useState(String(match.b))
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(match.a !== '' && match.b !== '')
  const [localStatus, setStatus] = useState(match.status || 'scheduled')
  const [changingStatus, setChangingStatus] = useState(false)
  const [error, setError] = useState('')
  const [ok, setOk] = useState('')

  // Status pushed over the websocket wins; the local value covers the moment
  // right after a button press and any time the socket is offline.
  const status = liveStatus || localStatus

  const hasTeams = match.teamA !== 'TBD' && match.teamB !== 'TBD'
  const isLive = status === 'live'
  const isScheduled = status === 'scheduled'
  const isEnded = status === 'completed'

  async function onSave() {
    setError(''); setOk('')
    const ta = toScore(a), tb = toScore(b)
    if (ta === null || tb === null) {
      setError('Enter whole numbers of 0 or more for both teams.')
      return
    }
    setSaving(true)
    try {
      await saveScore(match.id, ta, tb, saved)
      setSaved(true)
      setOk(`Saved ${ta} - ${tb}`)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  async function onStart() {
    setError(''); setOk('')
    setChangingStatus(true)
    try {
      const updated = await startMatch(match.id)
      setStatus(updated?.status || 'live')
      setOk('Match started. It is now live and you can enter scores.')
    } catch (err) {
      setError(err.message)
    } finally {
      setChangingStatus(false)
    }
  }

  async function onEnd() {
    setError(''); setOk('')
    if (!saved) {
      setError('Submit the final score before ending the match.')
      return
    }
    if (!window.confirm(`End ${match.teamA} vs ${match.teamB}? You will not be able to change the score afterwards unless the organiser rejects it.`)) return
    setChangingStatus(true)
    try {
      const updated = await endMatch(match.id)
      setStatus(updated?.status || 'completed')
      setOk('Match ended. The organiser will now verify the score and publish the result.')
    } catch (err) {
      setError(err.message)
    } finally {
      setChangingStatus(false)
    }
  }

  return (
    <div className="detail-card match-review-card">
      <div className="match-review-heading">
        <strong>Match {match.number}: {match.teamA} vs {match.teamB}</strong>
        <span className="status-pill">{STATUS_LABELS[status] || status}</span>
      </div>
      {(match.tournament || match.venue) && <div className="muted small">{[match.tournament, match.venue].filter(Boolean).join(' · ')}</div>}
      {match.scheduled && <div className="muted small">{new Date(match.scheduled).toLocaleString()}</div>}
      {match.role && <div className="muted small">Your role: {match.role}</div>}

      {isScheduled && (
        <div className="stack-gap">
          <button type="button" className="button button-primary" onClick={onStart} disabled={changingStatus || !hasTeams}>
            {changingStatus ? 'Starting...' : 'Start match'}
          </button>
          {!hasTeams && (
            <div className="muted small">Both teams must be assigned before the match can start.</div>
          )}
        </div>
      )}

      {isLive && (
        <div className="score-entry">
          <label>{match.teamA}{' '}
            <input type="number" min="0" step="1" value={a} onChange={(e) => setA(e.target.value)} />
          </label>
          <label>{match.teamB}{' '}
            <input type="number" min="0" step="1" value={b} onChange={(e) => setB(e.target.value)} />
          </label>
          <button type="button" className="button button-primary" onClick={onSave} disabled={saving || changingStatus || Boolean(match.scoreLoadError)}>{saving ? 'Saving...' : (saved ? 'Update score' : 'Submit score')}</button>
          <button type="button" className="button button-secondary" onClick={onEnd} disabled={saving || changingStatus || Boolean(match.scoreLoadError)}>{changingStatus ? 'Ending...' : 'End match'}</button>
        </div>
      )}

      {isEnded && (
        <div className="stack-gap">
          {saved && <div>Final score: <b>{a} - {b}</b></div>}
          <div className="muted small">This match has ended. Waiting for the organiser to verify the score and publish the result.</div>
        </div>
      )}

      {status === 'paused' && <div className="muted small">This match is paused.</div>}
      {status === 'cancelled' && <div className="muted small">This match was cancelled.</div>}

      {live && <div>Live score: <b>{live.home} - {live.away}</b></div>}
      {match.scoreLoadError && <div className="notice notice-error" role="alert">{match.scoreLoadError}</div>}
      {error && <div className="notice notice-error" role="alert">{error}</div>}
      {ok && <div className="notice notice-success" role="status">{ok}</div>}
    </div>
  )
}

export default function ScorerPage() {
  const [matches, setMatches] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const live = useLiveScores()
  const liveStatus = useMatchStatus()
  const wsStatus = useRealtimeStatus()

  useEffect(() => {
    let cancelled = false
    getMyMatches()
      .then(async (rows) => {
        const list = (rows || []).map(normalize)
        const withScores = await Promise.all(list.map(async (m) => {
          try {
            const score = await getScore(m.id)
            return { ...m, a: String(score.team_a_score), b: String(score.team_b_score) }
          } catch (err) {
            if (err.status === 404) return m
            return {
              ...m,
              scoreLoadError: 'Could not load the saved score. Refresh this page before editing or ending this match.',
            }
          }
        }))
        if (!cancelled) setMatches(withScores)
      })
      .catch((err) => { if (!cancelled) setError(err.message) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    if (wsStatus !== 'open' || matches.length === 0) return

    const matchIds = matches.map((match) => match.id)

    matchIds.forEach((match_id) => {
      wsClient.send('subscribe_match', { match_id })
    })

    return () => {
      if (wsClient.status === 'open') {
        matchIds.forEach((match_id) => {
          wsClient.send('unsubscribe_match', { match_id })
        })
      }
    }
  }, [matches, wsStatus])
  const hasToken = Boolean(localStorage.getItem('access_token') || localStorage.getItem('accessToken') || localStorage.getItem('token'))

  return (
    <section>
      <div className="page-heading">
        <div>
          <p className="eyebrow">SCORER WORKSPACE</p>
          <h1>Match scoring</h1>
          <p className="muted">Start your assigned matches, record the score and end the match when play finishes.</p>
        </div>
        <span className={`status-pill status-${wsStatus === 'open' ? 'live' : 'unknown'}`}>{wsStatus === 'open' ? 'Live updates on' : 'Live updates offline'}</span>
      </div>
      {loading && <div className="loading-state"><span className="spinner" />Loading your matches...</div>}
      {error && (
        <div className="notice notice-error" role="alert">
          {error}{!hasToken && ' (You are not signed in as a referee or scorer.)'}
        </div>
      )}
      {!loading && !error && matches.length === 0 && <p>No matches are assigned to you.</p>}
      {matches.map((m) => (
        <MatchCard key={m.id} match={m} live={live[m.id]} liveStatus={liveStatus[m.id]} />
      ))}
    </section>
  )
}
