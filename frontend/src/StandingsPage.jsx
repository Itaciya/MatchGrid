import RankingView from './RankingView.jsx'
import { getStandings } from './services/rankingApi'

export default function StandingsPage() {
  return (
    <RankingView
      title="Standings"
      intro="Team positions based on verified match results only. Use Refresh after new results are verified."
      loadRanking={getStandings}
    />
  )
}