import { apiRequest } from './api'

const BASE = '/notifications'

// SCRUM-235: the signed-in user's own notifications, newest first, paginated.
export function getNotifications({ limit, offset = 0, unreadOnly = false }) {
  const query = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  if (unreadOnly) query.set('unread_only', 'true')
  return apiRequest(`${BASE}/?${query}`)
}

export function getUnreadCount() {
  return apiRequest(`${BASE}/unread-count`)
}

// SCRUM-237: only the owner can mark a notification as read.
export function markNotificationRead(notificationId) {
  return apiRequest(`${BASE}/${notificationId}/read`, { method: 'PATCH' })
}