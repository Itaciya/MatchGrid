import RankingView from './RankingView.jsx'
import { getLeaderboard } from './services/rankingApi'

export default function LeaderboardPage() {
  return (
    <RankingView
      title="Leaderboard"
      intro="Public tournament rankings, filtered by tournament. Only verified results count."
      loadRanking={getLeaderboard}
    />
  )
}