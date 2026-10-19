import { useEffect, useState } from 'react'
import { getNotifications, getUnreadCount, markNotificationRead } from './services/notificationApi'

const PAGE_SIZE = 10
const box = { border: '1px solid rgba(128,128,128,.4)', borderRadius: 8, padding: 16, marginBottom: 12 }

// The API sends a type and a message, so titles and links are derived from the type.
const TYPE_INFO = {
  fixture_published: { title: 'Fixtures published', page: 'tournaments', linkLabel: 'View tournaments' },
  fixture_changed: { title: 'Fixture changed', page: 'tournaments', linkLabel: 'View tournaments' },
}

function describe(type) {
  if (TYPE_INFO[type]) return TYPE_INFO[type]
  const text = String(type || 'notification').replace(/_/g, ' ')
  return { title: text.charAt(0).toUpperCase() + text.slice(1), page: null }
}

export default function NotificationsPage({ onOpenPage }) {
  const [page, setPage] = useState(0)
  const [reloadKey, setReloadKey] = useState(0)
  const [items, setItems] = useState([])
  const [hasNext, setHasNext] = useState(false)
  const [unread, setUnread] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState(null)
  const [actionError, setActionError] = useState('')

  useEffect(() => {
    let cancelled = false
    // One extra row tells us whether a next page exists.
    getNotifications({ limit: PAGE_SIZE + 1, offset: page * PAGE_SIZE })
      .then((rows) => {
        if (cancelled) return
        const list = Array.isArray(rows) ? rows : []
        setItems(list.slice(0, PAGE_SIZE))
        setHasNext(list.length > PAGE_SIZE)
      })
      .catch((err) => { if (!cancelled) setError(err.message) })
      .finally(() => { if (!cancelled) setLoading(false) })
    getUnreadCount()
      .then((result) => { if (!cancelled) setUnread(result.unread_count) })
      .catch(() => {})
    return () => { cancelled = true }
  }, [page, reloadKey])

  function goTo(next) {
    setLoading(true); setError(''); setActionError('')
    setPage(next)
  }

  function refresh() {
    setLoading(true); setError(''); setActionError('')
    setReloadKey((key) => key + 1)
  }

  async function markRead(notification) {
    setBusyId(notification.id)
    setActionError('')
    try {
      const updated = await markNotificationRead(notification.id)
      setItems((list) => list.map((n) => (n.id === notification.id ? { ...n, ...updated } : n)))
      if (!notification.is_read) setUnread((count) => (count == null ? count : Math.max(0, count - 1)))
    } catch (err) {
      setActionError(err.message)
    } finally {
      setBusyId(null)
    }
  }

  const hasToken = Boolean(localStorage.getItem('access_token'))

  return (
    <section>
      <h2>Notifications{unread != null && unread > 0 ? ` (${unread} unread)` : ''}</h2>
      <p style={{ fontSize: 13, opacity: 0.7 }}>
        Only your own notifications are shown. Use Refresh to check for new ones.
      </p>
      <button type="button" onClick={refresh} disabled={loading}>{loading ? 'Loading...' : 'Refresh'}</button>

      {error && (
        <div className="notice notice-error" role="alert">
          {error}{!hasToken && ' (Sign in to see your notifications.)'}
        </div>
      )}
      {actionError && <div className="notice notice-error" role="alert">{actionError}</div>}

      {!loading && !error && items.length === 0 && <p style={{ marginTop: 12 }}>You have no notifications.</p>}

      <div style={{ marginTop: 12 }}>
        {items.map((n) => {
          const info = describe(n.notification_type)
          return (
            <div key={n.id} style={{ ...box, borderLeft: n.is_read ? box.border : '4px solid #3b82f6' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
                <strong>{info.title}</strong>
                <span className="status-pill">{n.is_read ? 'Read' : 'Unread'}</span>
              </div>
              <p style={{ margin: '8px 0', whiteSpace: 'pre-wrap' }}>{n.content}</p>
              <div style={{ fontSize: 13, opacity: 0.7 }}>{new Date(n.created_at).toLocaleString()}</div>
              <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                {info.page && onOpenPage && (
                  <button type="button" onClick={() => onOpenPage(info.page)}>{info.linkLabel}</button>
                )}
                {!n.is_read && (
                  <button type="button" disabled={busyId === n.id} onClick={() => markRead(n)}>
                    {busyId === n.id ? 'Saving...' : 'Mark as read'}
                  </button>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {(page > 0 || hasNext) && (
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <button type="button" disabled={page === 0 || loading} onClick={() => goTo(page - 1)}>Previous</button>
          <span>Page {page + 1}</span>
          <button type="button" disabled={!hasNext || loading} onClick={() => goTo(page + 1)}>Next</button>
        </div>
      )}
    </section>
  )
}