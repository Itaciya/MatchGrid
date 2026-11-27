import { createContext, useContext } from 'react'

export const NotificationContext = createContext({
  unread: 0,
  latest: null,
  markRead: async () => {},
  markAllRead: async () => {},
  refreshUnread: () => {},
})

export const useNotifications = () => useContext(NotificationContext)

// Fired by the API client when tokens change (sign-in, refresh, sign-out),
// so the live connection can re-authenticate.
export const AUTH_CHANGED_EVENT = 'matchgrid:auth-changed'

export function announceAuthChange() {
  window.dispatchEvent(new Event(AUTH_CHANGED_EVENT))
}
