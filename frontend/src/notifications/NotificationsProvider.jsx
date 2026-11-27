import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { getUnreadCount, markAllNotificationsRead, markNotificationRead } from '../services/notificationApi'
import { wsClient } from '../realtime/websocketClient'
import { useRealtimeStatus } from '../realtime/useRealtime'
import { AUTH_CHANGED_EVENT, NotificationContext } from './notificationContext'
import { describe } from './notificationTypes'

const TOAST_MS = 7000
// Safety net if the live connection is down: re-check the count now and then.
const FALLBACK_POLL_MS = 60000


function Toasts({ toasts, onOpen, onDismiss }) {
  if (!toasts.length) return null
  return (
    <div className="toast-stack" role="region" aria-label="New notifications">
      {toasts.map((toast) => (
        <div key={toast.id} className={`toast toast-${describe(toast.notification_type).tone}`} role="status">
          <span className="toast-dot" aria-hidden="true" />
          <div className="toast-body">
            <strong>{toast.title}</strong>
            <p>{toast.message}</p>
            {toast.link && (
              <button type="button" className="toast-link" onClick={() => onOpen(toast)}>Open</button>
            )}
          </div>
          <button type="button" className="toast-close" aria-label="Dismiss" onClick={() => onDismiss(toast.id)}>×</button>
        </div>
      ))}
    </div>
  )
}

/**
 * Keeps the signed-in user's unread count and newest notifications in sync
 * with the server in real time, and shows a short toast for each new one.
 */
export function NotificationsProvider({ user, children }) {
  const signedIn = Boolean(user?.id)
  const status = useRealtimeStatus()
  const [unread, setUnread] = useState(0)
  const [latest, setLatest] = useState(null)
  const [toasts, setToasts] = useState([])
  const timers = useRef(new Map())

  const refreshUnread = useCallback(() => {
    if (!signedIn) return
    getUnreadCount()
      .then((result) => {
        const count = Number(result?.unread_count)
        if (Number.isFinite(count)) setUnread(count)
      })
      .catch(() => {})
  }, [signedIn])

  const dismiss = useCallback((id) => {
    setToasts((list) => list.filter((toast) => toast.id !== id))
    window.clearTimeout(timers.current.get(id))
    timers.current.delete(id)
  }, [])

  // Re-authenticate the live connection whenever the signed-in user changes.
  useEffect(() => {
    wsClient.reconnect()
  }, [user?.id])

  useEffect(() => {
    const onAuthChanged = () => wsClient.reconnect()
    window.addEventListener(AUTH_CHANGED_EVENT, onAuthChanged)
    return () => window.removeEventListener(AUTH_CHANGED_EVENT, onAuthChanged)
  }, [])

  // Catch up on connect/reconnect, then fall back to occasional polling.
  useEffect(() => {
    if (!signedIn) return undefined
    const first = window.setTimeout(refreshUnread, 0)
    const poll = window.setInterval(refreshUnread, FALLBACK_POLL_MS)
    return () => { window.clearTimeout(first); window.clearInterval(poll) }
  }, [signedIn, status, refreshUnread])

  useEffect(() => {
    if (!signedIn) return undefined
    return wsClient.on('notification:new', (payload) => {
      if (!payload || payload.recipient_id !== user.id) return
      const item = {
        id: payload.notification_id,
        title: describe(payload.notification_type).title,
        message: payload.message,
        notification_type: payload.notification_type,
        link: payload.link,
        content: payload.message,
        is_read: false,
        created_at: payload.created_at,
      }
      setUnread((count) => count + 1)
      setLatest(item)
      setToasts((list) => [item, ...list.filter((toast) => toast.id !== item.id)].slice(0, 3))
      timers.current.set(item.id, window.setTimeout(() => dismiss(item.id), TOAST_MS))
    })
  }, [signedIn, user?.id, dismiss])

  useEffect(() => {
    const pending = timers.current
    return () => pending.forEach((timer) => window.clearTimeout(timer))
  }, [])

  const markRead = useCallback(async (notification) => {
    const updated = await markNotificationRead(notification.id)
    if (!notification.is_read) setUnread((count) => Math.max(0, count - 1))
    return updated
  }, [])

  const markAllRead = useCallback(async () => {
    await markAllNotificationsRead()
    setUnread(0)
  }, [])

  const openToast = useCallback((toast) => {
    dismiss(toast.id)
    if (!toast.is_read) {
      markNotificationRead(toast.id).then(() => setUnread((count) => Math.max(0, count - 1))).catch(() => {})
    }
    if (toast.link) window.location.assign(toast.link)
  }, [dismiss])

  const value = useMemo(() => ({
    unread: signedIn ? unread : 0,
    latest: signedIn ? latest : null,
    markRead,
    markAllRead,
    refreshUnread,
  }), [signedIn, unread, latest, markRead, markAllRead, refreshUnread])

  return (
    <NotificationContext.Provider value={value}>
      {children}
      {signedIn && <Toasts toasts={toasts} onOpen={openToast} onDismiss={dismiss} />}
    </NotificationContext.Provider>
  )
}
