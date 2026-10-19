import { apiRequest } from './api'

export function getTournaments() {
  return apiRequest('/tournaments/')
}

// SCRUM-229: standings built from verified official results.
export function getStandings(tournamentId) {
  return apiRequest(`/tournaments/${tournamentId}/standings`)
}

// SCRUM-230: public leaderboard for a tournament.
export function getLeaderboard(tournamentId) {
  return apiRequest(`/tournaments/${tournamentId}/leaderboard`)
}