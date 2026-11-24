import RankingView from './RankingView.jsx'
import { getLeaderboard } from './services/rankingApi'

export default function LeaderboardPage() {
  return (
    <RankingView
      variant="leaderboard"
      eyebrow="HALL OF FAME"
      title="Leaderboard"
      intro="The podium, the champions and every result of the tournament."
      loadRanking={getLeaderboard}
    />
  )
}
