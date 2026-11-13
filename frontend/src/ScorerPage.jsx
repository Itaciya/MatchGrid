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
    teamA: m.team_a_id ? 'Team ' + m.team_a_id : 'TBD',
    teamB: m.team_b_id ? 'Team ' + m.team_b_id : 'TBD',
    role: m.assignment_type ?? '',
    scheduled: m.scheduled_at ?? null,
    status: m.status ?? '',
    a: '',
    b: '',
  }
}

const toScore = (v) => (/^\d+$/.test(String(v).trim()) ? Number(v) : null)
const box = { border: '1px solid rgba(128,128,128,.4)', borderRadius: 8, padding: 16, marginBottom: 12 }

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
    if (!window.confirm('End this match? You will not be able to change the score afterwards unless the organiser rejects it.')) return
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
    <div style={box}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
        <strong>Match {match.number}: {match.teamA} vs {match.teamB}</strong>
        <span className="status-pill">{STATUS_LABELS[status] || status}</span>
      </div>
      {match.scheduled && <div style={{ fontSize: 13, opacity: 0.7 }}>{new Date(match.scheduled).toLocaleString()}</div>}
      {match.role && <div style={{ fontSize: 13, opacity: 0.7 }}>Your role: {match.role}</div>}

      {isScheduled && (
        <div style={{ margin: '12px 0' }}>
          <button type="button" onClick={onStart} disabled={changingStatus || !hasTeams}>
            {changingStatus ? 'Starting...' : 'Start match'}
          </button>
          {!hasTeams && (
            <div style={{ fontSize: 13, opacity: 0.7, marginTop: 6 }}>Both teams must be assigned before the match can start.</div>
          )}
        </div>
      )}

      {isLive && (
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', margin: '12px 0', flexWrap: 'wrap' }}>
          <label>{match.teamA}{' '}
            <input type="number" min="0" step="1" value={a} onChange={(e) => setA(e.target.value)} style={{ width: 70 }} />
          </label>
          <label>{match.teamB}{' '}
            <input type="number" min="0" step="1" value={b} onChange={(e) => setB(e.target.value)} style={{ width: 70 }} />
          </label>
          <button type="button" onClick={onSave} disabled={saving || changingStatus || Boolean(match.scoreLoadError)}>{saving ? 'Saving...' : (saved ? 'Update score' : 'Submit score')}</button>
          <button type="button" onClick={onEnd} disabled={saving || changingStatus || Boolean(match.scoreLoadError)}>{changingStatus ? 'Ending...' : 'End match'}</button>
        </div>
      )}

      {isEnded && (
        <div style={{ margin: '12px 0' }}>
          {saved && <div>Final score: <b>{a} - {b}</b></div>}
          <div style={{ fontSize: 13, opacity: 0.7 }}>This match has ended. Waiting for the organiser to verify the score and publish the result.</div>
        </div>
      )}

      {status === 'paused' && <div style={{ fontSize: 13, opacity: 0.7, margin: '12px 0' }}>This match is paused.</div>}
      {status === 'cancelled' && <div style={{ fontSize: 13, opacity: 0.7, margin: '12px 0' }}>This match was cancelled.</div>}

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
      <h2>Match scoring</h2>
      <p style={{ fontSize: 13, opacity: 0.7 }}>Live connection: {wsStatus}</p>
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
