import { useEffect, useState } from 'react'
import { getMyMatches, getScore, saveScore } from './services/scorerApi'
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

function MatchCard({ match, live, liveStatus }) {
  const [a, setA] = useState(String(match.a))
  const [b, setB] = useState(String(match.b))
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(match.a !== '' && match.b !== '')
  const [error, setError] = useState('')
  const [ok, setOk] = useState('')

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

  return (
    <div style={box}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
        <strong>Match {match.number}: {match.teamA} vs {match.teamB}</strong>
        <span className="status-pill">{liveStatus || match.status || 'scheduled'}</span>
      </div>
      {match.scheduled && <div style={{ fontSize: 13, opacity: 0.7 }}>{new Date(match.scheduled).toLocaleString()}</div>}
      {match.role && <div style={{ fontSize: 13, opacity: 0.7 }}>Your role: {match.role}</div>}

      <div style={{ display: 'flex', gap: 12, alignItems: 'center', margin: '12px 0', flexWrap: 'wrap' }}>
        <label>{match.teamA}{' '}
          <input type="number" min="0" step="1" value={a} onChange={(e) => setA(e.target.value)} style={{ width: 70 }} />
        </label>
        <label>{match.teamB}{' '}
          <input type="number" min="0" step="1" value={b} onChange={(e) => setB(e.target.value)} style={{ width: 70 }} />
        </label>
        <button type="button" onClick={onSave} disabled={saving}>{saving ? 'Saving...' : (saved ? 'Update score' : 'Submit score')}</button>
      </div>

      {live && <div>Live score: <b>{live.home} - {live.away}</b></div>}
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
      .then(async (rows) => { const list = (rows || []).map(normalize); const withScores = await Promise.all(list.map(async (m) => { try { const s = await getScore(m.id); return { ...m, a: String(s.team_a_score), b: String(s.team_b_score) } } catch { return m } })); if (!cancelled) setMatches(withScores) })
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
