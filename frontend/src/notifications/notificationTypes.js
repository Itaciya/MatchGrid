// Friendly titles, icons and tones for each notification type.

export const TYPE_INFO = {
  registration_submitted: { title: 'New application', icon: '📝', tone: 'action' },
  registration_status: { title: 'Application update', icon: '✅', tone: 'info' },
  fixture_published: { title: 'Fixtures published', icon: '📅', tone: 'info' },
  fixture_changed: { title: 'Fixture changed', icon: '🔁', tone: 'info' },
  upcoming_match_reminder: { title: 'Match reminder', icon: '⏰', tone: 'info' },
  tournament_scorer_assignment: { title: 'Scoring assignment', icon: '🎯', tone: 'info' },
  match_live: { title: 'Match is live', icon: '🔴', tone: 'live' },
  match_completed: { title: 'Action needed: finalize result', icon: '🏁', tone: 'action' },
  score_rejected: { title: 'Score rejected', icon: '✏️', tone: 'action' },
  result_published: { title: 'Result published', icon: '📣', tone: 'success' },
  tournament_completed: { title: 'Tournament finished', icon: '🏆', tone: 'success' },
  team_advanced: { title: 'Through to the next round', icon: '⬆️', tone: 'success' },
  team_eliminated: { title: 'Knocked out', icon: '⬇️', tone: 'info' },
  tournament_final: { title: 'Champions!', icon: '🏆', tone: 'success' },
  dispute_submitted: { title: 'New dispute', icon: '⚖️', tone: 'action' },
  dispute_update: { title: 'Dispute update', icon: '⚖️', tone: 'info' },
}

export function describe(type) {
  if (TYPE_INFO[type]) return TYPE_INFO[type]
  const text = String(type || 'notification').replace(/_/g, ' ')
  return { title: text.charAt(0).toUpperCase() + text.slice(1), icon: '🔔', tone: 'info' }
}
