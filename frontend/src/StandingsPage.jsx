import RankingView from './RankingView.jsx'
import { getStandings } from './services/rankingApi'

export default function StandingsPage() {
  return (
    <RankingView
      variant="standings"
      eyebrow="LEAGUE TABLE"
      title="Standings"
      intro="Points, goal difference and recent form for every team. Only verified results count."
      loadRanking={getStandings}
    />
  )
}
