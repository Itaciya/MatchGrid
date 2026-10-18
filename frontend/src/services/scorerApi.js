import { apiRequest } from './api'

export function getMyMatches() {
  return apiRequest('/official-assignments/my-matches')
}

export function submitScore(matchId, teamA, teamB) {
  return apiRequest(`/matches/${matchId}/score`, {
    method: 'POST',
    body: JSON.stringify({ match_id: matchId, team_a_score: teamA, team_b_score: teamB }),
  })
}

export function updateScore(matchId, teamA, teamB) {
  return apiRequest(`/matches/${matchId}/score`, {
    method: 'PATCH',
    body: JSON.stringify({ team_a_score: teamA, team_b_score: teamB }),
  })
}

// First save creates the score; later saves update it.
export async function saveScore(matchId, teamA, teamB, alreadySaved = false) {
  if (alreadySaved) return updateScore(matchId, teamA, teamB)
  try {
    return await submitScore(matchId, teamA, teamB)
  } catch (err) {
    if (/already|exist|duplicate|conflict/i.test(err.message)) {
      return updateScore(matchId, teamA, teamB)
    }
    throw err
  }
}


export function getScore(matchId) {
  return apiRequest(`/matches/${matchId}/score`)
}