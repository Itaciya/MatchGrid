// Display helpers shared by the pickers and pages.

export function teamLabel(name, id) {
  if (name) return name
  return id ? 'Team to be confirmed' : 'TBD'
}

export function matchLabel(match) {
  const teams = `${teamLabel(match.team_a_name, match.team_a_id)} vs ${teamLabel(match.team_b_name, match.team_b_id)}`
  const round = match.round_name ? `${match.round_name} · ` : ''
  return `${round}Match ${match.match_number}: ${teams}`
}

export function playerName(player) {
  return [player?.first_name, player?.last_name].filter(Boolean).join(' ') || 'Unnamed player'
}

export const MATCH_STATUS_LABELS = {
  scheduled: 'Scheduled',
  live: 'Live',
  paused: 'Paused',
  completed: 'Ended',
  cancelled: 'Cancelled',
  bye: 'Bye',
}
