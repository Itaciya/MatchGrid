import { useEffect, useState } from 'react'
import { getNotifications } from './services/notificationApi'
import { useNotifications } from './notifications/notificationContext'
import { describe } from './notifications/notificationTypes'

const PAGE_SIZE = 15

function timeAgo(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const seconds = Math.max(0, Math.round((Date.now() - date.getTime()) / 1000))
  if (seconds < 60) return 'just now'
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} h ago`
  return date.toLocaleDateString()
}

export default function NotificationsPage() {
  const { unread, latest, markRead, markAllRead } = useNotifications()
  const [filter, setFilter] = useState('all')
  const [page, setPage] = useState(0)
  const [items, setItems] = useState([])
  const [hasNext, setHasNext] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let cancelled = false
    const timer = window.setTimeout(() => {
      setLoading(true)
      getNotifications({ limit: PAGE_SIZE + 1, offset: page * PAGE_SIZE, unreadOnly: filter === 'unread' })
        .then((rows) => {
          if (cancelled) return
          const list = Array.isArray(rows) ? rows : []
          setItems(list.slice(0, PAGE_SIZE))
          setHasNext(list.length > PAGE_SIZE)
          setError('')
        })
        .catch((err) => { if (!cancelled) setError(err.message) })
        .finally(() => { if (!cancelled) setLoading(false) })
    }, 0)
    return () => { cancelled = true; window.clearTimeout(timer) }
  }, [page, filter])

  // New notifications arrive live: put them on top of the first page.
  useEffect(() => {
    if (!latest || page !== 0) return undefined
    const timer = window.setTimeout(() => {
      setItems((list) => (list.some((item) => item.id === latest.id) ? list : [latest, ...list].slice(0, PAGE_SIZE)))
    }, 0)
    return () => window.clearTimeout(timer)
  }, [latest, page])

  async function open(notification) {
    if (!notification.is_read) {
      try {
        await markRead(notification)
        setItems((list) => list.map((item) => (item.id === notification.id ? { ...item, is_read: true } : item)))
      } catch {
        // Opening the link matters more than the read flag.
      }
    }
    if (notification.link) window.location.assign(notification.link)
  }

  async function onMarkRead(notification) {
    setBusy(true)
    try {
      await markRead(notification)
      setItems((list) => (filter === 'unread'
        ? list.filter((item) => item.id !== notification.id)
        : list.map((item) => (item.id === notification.id ? { ...item, is_read: true } : item))))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function onMarkAll() {
    setBusy(true)
    try {
      await markAllRead()
      setItems((list) => (filter === 'unread' ? [] : list.map((item) => ({ ...item, is_read: true }))))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section>
      <div className="page-heading">
        <div>
          <p className="eyebrow">INBOX</p>
          <h1>Notifications</h1>
          <p className="muted">
            {unread > 0 ? `You have ${unread} unread ${unread === 1 ? 'notification' : 'notifications'}.` : 'You are all caught up.'}
            {' '}New updates appear here instantly.
          </p>
        </div>
        <button className="button button-secondary" type="button" onClick={onMarkAll} disabled={busy || unread === 0}>
          Mark all as read
        </button>
      </div>

      <div className="segmented" role="tablist" aria-label="Filter notifications">
        {[['all', 'All'], ['unread', `Unread${unread ? ` (${unread})` : ''}`]].map(([value, label]) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={filter === value}
            className={filter === value ? 'active' : ''}
            onClick={() => { setFilter(value); setPage(0) }}
          >
            {label}
          </button>
        ))}
      </div>

      {error && <div className="notice notice-error" role="alert">{error}</div>}
      {loading && <div className="loading-state"><span className="spinner" />Loading notifications...</div>}

      {!loading && !error && items.length === 0 && (
        <div className="empty-state">
          <span className="empty-icon">🔔</span>
          <h3>{filter === 'unread' ? 'No unread notifications' : 'No notifications yet'}</h3>
          <p>Applications, match updates and results for you will show up here as they happen.</p>
        </div>
      )}

      <ul className="notification-list">
        {items.map((notification) => {
          const info = describe(notification.notification_type)
          return (
            <li key={notification.id} className={`notification-item tone-${info.tone} ${notification.is_read ? 'is-read' : 'is-unread'}`}>
              <span className="notification-icon" aria-hidden="true">{info.icon}</span>
              <div className="notification-body">
                <div className="notification-top">
                  <strong>{info.title}</strong>
                  <span className="muted small">{timeAgo(notification.created_at)}</span>
                </div>
                <p>{notification.content}</p>
                <div className="table-actions">
                  {notification.link && (
                    <button type="button" className="button button-primary" onClick={() => open(notification)}>Open</button>
                  )}
                  {!notification.is_read && (
                    <button type="button" className="button button-secondary" onClick={() => onMarkRead(notification)} disabled={busy}>Mark as read</button>
                  )}
                </div>
              </div>
              {!notification.is_read && <span className="unread-dot" aria-label="Unread" />}
            </li>
          )
        })}
      </ul>

      {(page > 0 || hasNext) && (
        <div className="pagination-row">
          <button className="button button-secondary" type="button" onClick={() => setPage((p) => Math.max(0, p - 1))} disabled={page === 0 || loading}>← Newer</button>
          <span className="helper-text">Page {page + 1}</span>
          <button className="button button-secondary" type="button" onClick={() => setPage((p) => p + 1)} disabled={!hasNext || loading}>Older →</button>
        </div>
      )}
    </section>
  )
}
