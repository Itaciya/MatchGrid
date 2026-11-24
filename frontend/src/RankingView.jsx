import { useCallback, useEffect, useRef, useState } from 'react'
import { apiRequest } from './services/api'
import { TournamentSelect } from './components/Pickers'

// Last five results for each team, newest last, from verified fixture scores.
function buildForm(fixtures) {
  const form = new Map()
  const played = fixtures
    .filter((fixture) => fixture.team_a_score != null && fixture.team_b_score != null)
    .sort((a, b) => new Date(a.scheduled_at) - new Date(b.scheduled_at))

  played.forEach((fixture) => {
    const { team_a_id: a, team_b_id: b, team_a_score: sa, team_b_score: sb } = fixture
    const outcome = (mine, theirs) => (mine > theirs ? 'W' : mine < theirs ? 'L' : 'D')
    form.set(a, [...(form.get(a) || []), outcome(sa, sb)].slice(-5))
    form.set(b, [...(form.get(b) || []), outcome(sb, sa)].slice(-5))
  })
  return form
}

function FormGuide({ results = [] }) {
  if (!results.length) return <span className="muted small">-</span>
  return (
    <span className="form-guide" aria-label={`Recent form: ${results.join(' ')}`}>
      {results.map((result, index) => <i key={index} className={`form-${result}`}>{result}</i>)}
    </span>
  )
}

function signed(value) {
  return value > 0 ? `+${value}` : String(value)
}

function LeagueTable({ rows, form }) {
  return (
    <div className="table-wrap league-table">
      <table>
        <thead>
          <tr>
            <th>#</th><th>Team</th><th title="Played">P</th><th title="Won">W</th><th title="Drawn">D</th><th title="Lost">L</th>
            <th title="Goals for">GF</th><th title="Goals against">GA</th><th title="Goal difference">GD</th><th>Form</th><th>Pts</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.team_id} className={row.rank === 1 ? 'is-leader' : ''}>
              <td><span className={`rank-badge rank-${Math.min(row.rank, 4)}`}>{row.rank}</span></td>
              <td><strong>{row.team_name}</strong></td>
              <td>{row.played}</td>
              <td>{row.wins}</td>
              <td>{row.draws}</td>
              <td>{row.losses}</td>
              <td>{row.score_for}</td>
              <td>{row.score_against}</td>
              <td className={row.score_difference > 0 ? 'positive' : row.score_difference < 0 ? 'negative' : ''}>{signed(row.score_difference)}</td>
              <td><FormGuide results={form.get(row.team_id)} /></td>
              <td><strong className="points">{row.points}</strong></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Podium({ rows, tournament }) {
  const [first, second, third] = rows
  const finished = tournament?.status === 'completed'
  const place = (row, position) => row && (
    <div className={`podium-step podium-${position}`}>
      <span className="podium-medal">{position === 1 ? '🏆' : position === 2 ? '🥈' : '🥉'}</span>
      <strong>{row.team_name}</strong>
      <span className="podium-points">{row.points} pts</span>
      <span className="muted small">{row.wins}W · {row.draws}D · {row.losses}L</span>
      <div className="podium-block">{position}</div>
    </div>
  )

  return (
    <>
      {finished && first && (
        <div className="champion-banner">
          <span className="champion-trophy">🏆</span>
          <div>
            <p className="eyebrow">CHAMPIONS</p>
            <h2>{first.team_name}</h2>
            <p>{tournament.name} winners with {first.points} points and a goal difference of {signed(first.score_difference)}.</p>
          </div>
        </div>
      )}
      <div className="podium">
        {place(second, 2)}
        {place(first, 1)}
        {place(third, 3)}
      </div>
    </>
  )
}

function ResultsList({ fixtures }) {
  const results = fixtures
    .filter((fixture) => fixture.team_a_score != null && fixture.team_b_score != null)
    .sort((a, b) => new Date(b.scheduled_at) - new Date(a.scheduled_at))
  if (!results.length) return null

  return (
    <>
      <div className="section-title"><div><h2>Results</h2><p className="muted">Every verified score in this tournament.</p></div></div>
      <div className="results-grid">
        {results.map((fixture) => {
          const aWon = fixture.team_a_score > fixture.team_b_score
          const bWon = fixture.team_b_score > fixture.team_a_score
          return (
            <div key={fixture.id} className="result-tile">
              <span className="muted small">{fixture.round_name || `Match ${fixture.match_number}`} · {new Date(fixture.scheduled_at).toLocaleDateString()}</span>
              <div className={`result-row ${aWon ? 'winner' : ''}`}><span>{fixture.team_a_name}</span><strong>{fixture.team_a_score}</strong></div>
              <div className={`result-row ${bWon ? 'winner' : ''}`}><span>{fixture.team_b_name}</span><strong>{fixture.team_b_score}</strong></div>
            </div>
          )
        })}
      </div>
    </>
  )
}

export default function RankingView({ variant, eyebrow, title, intro, loadRanking }) {
  const [tournamentId, setTournamentId] = useState('')
  const [tournament, setTournament] = useState(null)
  const [rows, setRows] = useState(null)
  const [fixtures, setFixtures] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const requestId = useRef(0)

  useEffect(() => () => {
    requestId.current += 1
  }, [])

  const load = useCallback(async (id) => {
    const currentRequest = ++requestId.current
    setError('')
    setRows(null)
    setFixtures([])
    if (!id) {
      setLoading(false)
      return
    }

    setLoading(true)
    try {
      const [ranking, fixtureRows, details] = await Promise.all([
        loadRanking(Number(id)),
        apiRequest(`/matches/tournaments/${Number(id)}/fixtures`).catch(() => []),
        apiRequest(`/tournaments/${Number(id)}`).catch(() => null),
      ])
      if (currentRequest !== requestId.current) return
      setRows(Array.isArray(ranking) ? ranking : [])
      setFixtures(Array.isArray(fixtureRows) ? fixtureRows : [])
      setTournament(details)
    } catch (err) {
      if (currentRequest === requestId.current) setError(err.message)
    } finally {
      if (currentRequest === requestId.current) setLoading(false)
    }
  }, [loadRanking])

  function onSelect(value) {
    setTournamentId(value)
    load(value)
  }

  const hasPlayed = rows?.some((row) => row.played > 0)

  return (
    <section>
      <div className="page-heading">
        <div>
          <p className="eyebrow">{eyebrow}</p>
          <h1>{title}</h1>
          <p className="muted">{intro}</p>
        </div>
        <button className="button button-secondary" type="button" disabled={!tournamentId || loading} onClick={() => load(tournamentId)}>
          {loading ? 'Loading...' : 'Refresh'}
        </button>
      </div>

      <div className="lookup-card">
        <TournamentSelect
          id={`${variant}-tournament`}
          value={tournamentId}
          onChange={onSelect}
          filter={(item) => item.fixtures_published}
          emptyText="No tournaments have published fixtures yet."
        />
      </div>

      {error && <div className="notice notice-error" role="alert">{error}</div>}
      {loading && <div className="loading-state"><span className="spinner" />Loading...</div>}
      {rows && !hasPlayed && !loading && (
        <div className="empty-state"><h3>No results yet</h3><p className="muted">Rankings appear once the first match result is verified.</p></div>
      )}
      {rows && hasPlayed && variant === 'leaderboard' && <Podium rows={rows} tournament={tournament} />}
      {rows && hasPlayed && <LeagueTable rows={rows} form={buildForm(fixtures)} />}
      {rows && hasPlayed && <ResultsList fixtures={fixtures} />}
    </section>
  )
}
