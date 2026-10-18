import { useCallback, useEffect, useState } from 'react'
import { getTournaments } from './services/rankingApi'

export default function RankingView({ title, intro, loadRanking }) {
  const [tournaments, setTournaments] = useState([])
  const [tournamentId, setTournamentId] = useState('')
  const [rows, setRows] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    getTournaments()
      .then((list) => { if (!cancelled) setTournaments(Array.isArray(list) ? list : []) })
      .catch((err) => { if (!cancelled) setError(err.message) })
    return () => { cancelled = true }
  }, [])

  const load = useCallback(async (id) => {
    setError('')
    setRows(null)
    if (!id) return
    setLoading(true)
    try {
      const result = await loadRanking(Number(id))
      setRows(Array.isArray(result) ? result : [])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [loadRanking])

  function onSelect(event) {
    setTournamentId(event.target.value)
    load(event.target.value)
  }

  return (
    <section>
      <h2>{title}</h2>
      <p style={{ fontSize: 13, opacity: 0.7 }}>{intro}</p>
      <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        <select value={tournamentId} onChange={onSelect} aria-label="Tournament">
          <option value="">Select a tournament</option>
          {tournaments.map((t) => (
            <option key={t.id} value={t.id}>{t.name} (#{t.id})</option>
          ))}
        </select>
        <button type="button" disabled={!tournamentId || loading} onClick={() => load(tournamentId)}>
          {loading ? 'Loading...' : 'Refresh'}
        </button>
      </div>

      {error && <div className="notice notice-error" role="alert">{error}</div>}
      {loading && <div className="loading-state"><span className="spinner" />Loading...</div>}
      {rows && rows.length === 0 && <p>No verified results yet for this tournament.</p>}
      {rows && rows.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Rank</th><th>Team</th><th>Played</th><th>W</th><th>D</th><th>L</th>
                <th>Score diff.</th><th>Points</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.team_id}>
                  <td><span className="rank">#{row.rank}</span></td>
                  <td><strong>{row.team_name}</strong></td>
                  <td>{row.played}</td>
                  <td>{row.wins}</td>
                  <td>{row.draws}</td>
                  <td>{row.losses}</td>
                  <td>{row.score_difference}</td>
                  <td><strong>{row.points}</strong></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}