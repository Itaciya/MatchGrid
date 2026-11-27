/** Score cell: the live score while a match is played, else the published one. */
export function LiveFixtureScore({ fixture, live }) {
  const status = live.statuses[fixture.id] || fixture.status
  const liveScore = live.scores[fixture.id]
  const home = liveScore ? liveScore.home : fixture.team_a_score
  const away = liveScore ? liveScore.away : fixture.team_b_score
  const isLive = status === 'live' || status === 'paused'

  if (home == null || away == null) {
    return <span className="muted">{status === 'completed' ? 'Awaiting result' : '–'}</span>
  }

  return (
    <span className={`fixture-score ${isLive ? 'is-live' : ''}`} key={liveScore?.updatedAt || 'static'}>
      {home} – {away}
    </span>
  )
}
