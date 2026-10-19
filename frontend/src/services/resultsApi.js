import { apiRequest } from './api'

// SCRUM-225: organiser reads, approves or rejects a submitted score.
export function getFixtures(tournamentId) {
  return apiRequest(`/matches/tournaments/${tournamentId}/fixtures`)
}

export function getScoreForReview(matchId) {
  return apiRequest(`/matches/${matchId}/score/review`)
}

export function reviewScore(matchId, status) {
  return apiRequest(`/matches/${matchId}/score/verification`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  })
}

// SCRUM-227: a player submits a dispute for a match they played in.
export function createDispute(matchId, reason) {
  return apiRequest('/disputes/', {
    method: 'POST',
    body: JSON.stringify({ match_id: matchId, reason }),
  })
}

// SCRUM-226: public result, available only for completed matches with a verified score.
export function getPublicResult(matchId) {
  return apiRequest(`/spectator/matches/${matchId}/result`)
}

// SCRUM-228: organiser reviews and resolves disputes.
export function getOpenDisputes() {
  return apiRequest('/disputes/open')
}

export function startDisputeReview(disputeId) {
  return apiRequest(`/disputes/${disputeId}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ status: 'under_review' }),
  })
}

export function resolveDispute(disputeId, body) {
  return apiRequest(`/disputes/${disputeId}/resolve`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  })
}