import { useCallback, useEffect, useMemo, useState } from 'react'
import { API_BASE_URL, apiRequest } from './services/api'
import ScorerPage from './ScorerPage.jsx'
import NotificationsPage from './NotificationsPage.jsx'
import VerificationPage from './VerificationPage.jsx'
import DisputePage from './DisputePage.jsx'
import ResultPage from './ResultPage.jsx'
import StandingsPage from './StandingsPage.jsx'
import LeaderboardPage from './LeaderboardPage.jsx'
import DisputeResolutionPage from './DisputeResolutionPage.jsx'
import './App.css'
import RegistrationPage from './RegistrationPage.jsx'
import RegistrationApprovalPage from './RegistrationApprovalPage.jsx'

const NAV_ITEMS = [
  ['overview', 'Overview'],
  ['tournaments', 'Tournaments'],
  ['create', 'Create tournament'],
  ['team', 'Teams'],
  ['scoring', 'Scoring'],
  ['notifications', 'Notifications'],
  ['verify', 'Verify scores'],
  ['dispute', 'Disputes'],
  ['result', 'Match results'],
  ['standings', 'Standings'],
  ['leaderboard', 'Leaderboard'],
  ['resolve', 'Resolve disputes'],
  ['registrations', 'Tournament registration'],
  ['registration-approvals', 'Registration approvals'],
]


const PUBLIC_PAGES = new Set([
  'login',
  'register',
  'tournaments',
  'details',
  'standings',
  'leaderboard',
])

const KNOWN_ROLES = new Set([
  'organiser',
  'captain',
  'player',
  'spectator',
  'scorer',
  'official',
])

const PAGE_ROLES = {
  create: ['organiser'],
  'registration-approvals': ['organiser'],
  resolve: ['organiser'],
  registrations: ['captain'],
  team: ['organiser', 'player'],
  scoring: ['scorer', 'official'],
  verify: ['organiser'],
  dispute: ['player'],
}

function dateLabel(value) {
  if (!value) return '-'
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? String(value)
    : date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

function dateInputValue(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000)
  return local.toISOString().slice(0, 16)
}

function statusClass(value) {
  return `status-pill status-${String(value || 'unknown').toLowerCase().replace(/[^a-z0-9]+/g, '-')}`
}

function ErrorNotice({ children }) {
  return children ? <div className="notice notice-error" role="alert">{children}</div> : null
}

function SuccessNotice({ children }) {
  return children ? <div className="notice notice-success" role="status">{children}</div> : null
}

function Loading({ label = 'Loading...' }) {
  return <div className="loading-state"><span className="spinner" />{label}</div>
}

function App() {
  const [page, setPage] = useState('overview')
  const [currentUser, setCurrentUser] = useState(null)
  const [authReady, setAuthReady] = useState(false)
  const [authLoading, setAuthLoading] = useState(false)
  const [authError, setAuthError] = useState('')
  const [authSuccess, setAuthSuccess] = useState('')
  const [theme, setTheme] = useState(() => localStorage.getItem('matchgrid-theme') || 'system')
  const [tournaments, setTournaments] = useState([])
  const [listStatus, setListStatus] = useState('')
  const [searchTerm, setSearchTerm] = useState('')
  const [currentPage, setCurrentPage] = useState(1)
  const [listLoading, setListLoading] = useState(false)
  const [listError, setListError] = useState('')
  const [selectedTournament, setSelectedTournament] = useState(null)
  const [standings, setStandings] = useState([])
  const [fixtures, setFixtures] = useState([])
  const [fixturesLoading, setFixturesLoading] = useState(false)
  const [fixturesError, setFixturesError] = useState('')
  const [fixtureStatusFilter, setFixtureStatusFilter] = useState('')
  const [fixtureTeamFilter, setFixtureTeamFilter] = useState('')
  const [fixtureVenueFilter, setFixtureVenueFilter] = useState('')
  const [fixturePage, setFixturePage] = useState(1)
  const [currentTime, setCurrentTime] = useState(0)
  useEffect(() => {
    const updateCurrentTime = () => setCurrentTime(Date.now())
    const initialTimerId = window.setTimeout(updateCurrentTime, 0)
    const intervalId = window.setInterval(updateCurrentTime, 30000)

    return () => {
      window.clearTimeout(initialTimerId)
      window.clearInterval(intervalId)
    }
  }, [])

  const [detailsLoading, setDetailsLoading] = useState(false)
  const [detailsError, setDetailsError] = useState('')
  const [formLoading, setFormLoading] = useState(false)
  const [formError, setFormError] = useState('')
  const [formSuccess, setFormSuccess] = useState('')
  const [editingId, setEditingId] = useState(null)
  const [teamId, setTeamId] = useState('')
  const [team, setTeam] = useState(null)
  const [teamLoading, setTeamLoading] = useState(false)
  const [teamError, setTeamError] = useState('')
  const [playerId, setPlayerId] = useState('')
  const [player, setPlayer] = useState(null)
  const [playerLoading, setPlayerLoading] = useState(false)
  const [playerError, setPlayerError] = useState('')
  const [rosterPlayerId, setRosterPlayerId] = useState('')
  const [rosterLoading, setRosterLoading] = useState(false)
  const [rosterError, setRosterError] = useState('')
  const [rosterSuccess, setRosterSuccess] = useState('')

  const [form, setForm] = useState({
    name: '',
    description: '',
    format: 'round_robin',
    start_date: '',
    end_date: '',
    number_of_teams: '4',
  })

  useEffect(() => {
    const root = document.documentElement
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const applyTheme = () => {
      const selected = localStorage.getItem('matchgrid-theme') || 'system'
      root.dataset.theme = selected === 'system' ? (media.matches ? 'dark' : 'light') : selected
    }
    applyTheme()
    if (media.addEventListener) media.addEventListener('change', applyTheme)
    else media.addListener(applyTheme)
    return () => {
      if (media.removeEventListener) media.removeEventListener('change', applyTheme)
      else media.removeListener(applyTheme)
    }
  }, [theme])

  useEffect(() => {
    let cancelled = false

    const clearStoredTokens = () => {
      localStorage.removeItem('access_token')
      localStorage.removeItem('accessToken')
      localStorage.removeItem('token')
      localStorage.removeItem('refresh_token')
      localStorage.removeItem('refreshToken')
    }

    const token =
      localStorage.getItem('access_token') ||
      localStorage.getItem('accessToken') ||
      localStorage.getItem('token')

    if (!token) {
      Promise.resolve().then(() => {
        if (!cancelled) setAuthReady(true)
      })

      return () => {
        cancelled = true
      }
    }

    apiRequest('/auth/me')
      .then((user) => {
        const role =
          typeof user?.role === 'string'
            ? user.role.toLowerCase()
            : ''

        if (!user || !KNOWN_ROLES.has(role)) {
          throw new Error('Missing or invalid user role.')
        }

        if (!cancelled) setCurrentUser({ ...user, role })
      })
      .catch(() => {
        clearStoredTokens()
        if (!cancelled) setCurrentUser(null)
      })
      .finally(() => {
        if (!cancelled) setAuthReady(true)
      })

    return () => {
      cancelled = true
    }
  }, [])

  const changeTheme = (value) => {
    localStorage.setItem('matchgrid-theme', value)
    setTheme(value)
    const systemDark = window.matchMedia('(prefers-color-scheme: dark)').matches
    document.documentElement.dataset.theme = value === 'system' ? (systemDark ? 'dark' : 'light') : value
  }

  const loadTournaments = useCallback(async () => {
    setListLoading(true)
    setListError('')
    try {
      const query = listStatus ? `?status=${encodeURIComponent(listStatus)}` : ''
      const result = await apiRequest(`/tournaments/${query}`)
      setTournaments(Array.isArray(result) ? result : [])
    } catch (error) {
      setListError(error.message || 'Could not load tournaments.')
    } finally {
      setListLoading(false)
    }
  }, [listStatus])

  useEffect(() => {
  if (page !== 'tournaments' && page !== 'overview') return

  let cancelled = false

  const fetchTournaments = async () => {
    setListLoading(true)
    setListError('')

    try {
      const query = listStatus
        ? `?status=${encodeURIComponent(listStatus)}`
        : ''

      const result = await apiRequest(`/tournaments/${query}`)

      if (!cancelled) {
        setTournaments(Array.isArray(result) ? result : [])
        setCurrentPage(1)
      }
    } catch (error) {
      if (!cancelled) {
        setListError(error.message || 'Could not load tournaments.')
      }
    } finally {
      if (!cancelled) {
        setListLoading(false)
      }
    }
  }

  fetchTournaments()

  return () => {
    cancelled = true
  }
}, [page, listStatus])

  const openTournament = async (id) => {
    if (!Number.isInteger(Number(id)) || Number(id) <= 0) {
      setDetailsError('Enter a valid tournament ID.')
      return
    }
    setPage('details')
    const tournamentId = Number(id)
    setSelectedTournament(null)
    setStandings([])
    setFixtures([])
    setFixturesError('')
    setFixtureStatusFilter('')
    setFixtureTeamFilter('')
    setFixtureVenueFilter('')
    setFixturePage(1)
    setDetailsError('')
    setDetailsLoading(true)
    setFixturesLoading(true)
    try {
      const [detail, ranking, fixtureResult] = await Promise.all([
        apiRequest(`/tournaments/${tournamentId}`),
        apiRequest(`/tournaments/${tournamentId}/standings`).catch(() => []),
        apiRequest(`/matches/tournaments/${tournamentId}/fixtures`).catch((error) => {
          setFixturesError(error.message || 'Could not load fixtures.')
          return []
        }),
      ])
      setSelectedTournament(detail)
      setStandings(Array.isArray(ranking) ? ranking : [])
      setFixtures(Array.isArray(fixtureResult) ? fixtureResult : [])
    } catch (error) {
      setDetailsError(error.message || 'Could not load tournament details.')
    } finally {
      setDetailsLoading(false)
      setFixturesLoading(false)
    }
  }

  const resetForm = () => {
    setForm({ name: '', description: '', format: 'round_robin', start_date: '', end_date: '', number_of_teams: '4' })
    setEditingId(null)
    setFormError('')
    setFormSuccess('')
  }

  const beginEdit = (tournament) => {
    setEditingId(tournament.id)
    setForm({
      name: tournament.name || '',
      description: tournament.description || '',
      format: tournament.format || 'round_robin',
      start_date: dateInputValue(tournament.start_date),
      end_date: dateInputValue(tournament.end_date),
      number_of_teams: String(tournament.format_config?.number_of_teams || 4),
    })
    setFormError('')
    setFormSuccess('')
    setPage('create')
  }

  const submitTournament = async (event) => {
    event.preventDefault()
    setFormError('')
    setFormSuccess('')

    if (form.name.trim().length < 3) return setFormError('Tournament name must be at least 3 characters.')
    if (!form.format || !form.start_date || !form.end_date) return setFormError('Format, start date, and end date are required.')
    const start = new Date(form.start_date)
    const end = new Date(form.end_date)
    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || end <= start) {
      return setFormError('End date must be after the start date.')
    }

    const body = {
      name: form.name.trim(),
      description: form.description.trim() || null,
      format: form.format,
      format_config: ['round_robin', 'single_elimination', 'double_elimination'].includes(form.format)
        ? { number_of_teams: Number(form.number_of_teams) }
        : null,
      start_date: start.toISOString(),
      end_date: end.toISOString(),
    }

    setFormLoading(true)
    try {
      const result = editingId
        ? await apiRequest(`/organiser/tournaments/${editingId}`, { method: 'PATCH', body: JSON.stringify(body) })
        : await apiRequest('/organiser/tournaments', { method: 'POST', body: JSON.stringify(body) })
      setFormSuccess(editingId ? 'Tournament updated successfully.' : 'Tournament created successfully.')
      setSelectedTournament(result)
      await loadTournaments()
      setPage('details')
      setForm({ name: '', description: '', format: 'round_robin', start_date: '', end_date: '', number_of_teams: '4' })
      setEditingId(null)
    } catch (error) {
      setFormError(`${error.message || 'Unable to save tournament.'} If this is an authorization error, sign in with an organiser account.`)
    } finally {
      setFormLoading(false)
    }
  }

  const loadTeam = async (event) => {
    event.preventDefault()
    setTeam(null)
    setTeamError('')
    if (!/^[1-9]\d*$/.test(teamId)) return setTeamError('Enter a valid positive team ID.')
    setTeamLoading(true)
    try {
      setTeam(await apiRequest(`/player-team/team/${Number(teamId)}`))
    } catch (error) {
      setTeamError(error.message || 'Could not load team.')
    } finally {
      setTeamLoading(false)
    }
  }

  const loadPlayer = async (event) => {
    event.preventDefault()
    setPlayer(null)
    setPlayerError('')

    if (!/^[1-9]\d*$/.test(playerId)) {
      setPlayerError('Enter a valid positive player ID.')
      return
    }

    setPlayerLoading(true)
    try {
      const result = await apiRequest(`/player-team/profile/${Number(playerId)}`)
      setPlayer(result)
    } catch (error) {
      setPlayerError(error.message || 'Could not load player profile.')
    } finally {
      setPlayerLoading(false)
    }
  }

  const changeRoster = async (action, id) => {
    if (!team?.id) return
    if (!/^[1-9]\d*$/.test(String(id))) {
      setRosterError('Enter a valid positive player ID.')
      return
    }

    setRosterError('')
    setRosterSuccess('')
    setRosterLoading(true)

    try {
      const endpoint = `/player-team/team/${team.id}/players/${Number(id)}`
      const updatedPlayer = action === 'add'
        ? await apiRequest(endpoint, { method: 'POST' })
        : await apiRequest(endpoint, { method: 'DELETE' })

      const refreshedTeam = await apiRequest(`/player-team/team/${team.id}`)
      setTeam(refreshedTeam)
      setRosterPlayerId('')
      setRosterSuccess(
        action === 'add'
          ? `Player #${updatedPlayer.id} added to the roster.`
          : `Player #${updatedPlayer.id} removed from the roster.`,
      )
    } catch (error) {
      setRosterError(error.message || 'Could not update the roster.')
    } finally {
      setRosterLoading(false)
    }
  }

  const handleAuthSubmit = async (event, mode, values) => {
    event.preventDefault()
    setAuthError('')
    setAuthSuccess('')
    setAuthLoading(true)

    try {
      if (mode === 'register') {
        await apiRequest('/auth/register', {
          method: 'POST',
          body: JSON.stringify({
            email: values.email.trim(),
            password: values.password,
            role: values.role,
          }),
        })

        setAuthSuccess('Registration successful! Please sign in.')
        setPage('login')
        return
      }

      const tokens = await apiRequest('/auth/login', {
        method: 'POST',
        body: JSON.stringify({
          email: values.email.trim(),
          password: values.password,
        }),
      })

      localStorage.setItem('access_token', tokens.access_token)
      localStorage.setItem('refresh_token', tokens.refresh_token)

      const user = await apiRequest('/auth/me')
      const role =
        typeof user?.role === 'string'
          ? user.role.toLowerCase()
          : ''

      if (!user || !KNOWN_ROLES.has(role)) {
        throw new Error('Missing or invalid user role.')
      }

      setCurrentUser({ ...user, role })
      setAuthReady(true)
      setPage('overview')
    } catch (error) {
      if (mode === 'login') {
        localStorage.removeItem('access_token')
        localStorage.removeItem('accessToken')
        localStorage.removeItem('token')
        localStorage.removeItem('refresh_token')
        localStorage.removeItem('refreshToken')
        setCurrentUser(null)
      }

      setAuthError(error.message || 'Authentication failed.')
    } finally {
      setAuthLoading(false)
    }
  }

  const handleLogout = async () => {
    setAuthError('')
    setAuthSuccess('')

    try {
      const token =
        localStorage.getItem('access_token') ||
        localStorage.getItem('accessToken') ||
        localStorage.getItem('token')

      if (token) {
        await apiRequest('/auth/logout', { method: 'POST' })
      }
    } catch (error) {
      console.warn('Server logout failed:', error.message)
    } finally {
      localStorage.removeItem('access_token')
      localStorage.removeItem('accessToken')
      localStorage.removeItem('token')
      localStorage.removeItem('refresh_token')
      localStorage.removeItem('refreshToken')

      setCurrentUser(null)
      setAuthReady(true)
      setPage('login')
      setAuthSuccess('You have been signed out.')
    }
  }

  useEffect(() => {
    if (!authReady || PUBLIC_PAGES.has(page)) return

    let cancelled = false

    Promise.resolve().then(() => {
      if (cancelled) return

      if (!currentUser) {
        setPage('login')
        return
      }

      const role =
        typeof currentUser.role === 'string'
          ? currentUser.role.toLowerCase()
          : ''

      if (
        !KNOWN_ROLES.has(role) ||
        (PAGE_ROLES[page] && !PAGE_ROLES[page].includes(role))
      ) {
        setPage('overview')
      }
    })

    return () => {
      cancelled = true
    }
  }, [page, currentUser, authReady])

  const visibleNavItems = NAV_ITEMS.filter(([id]) => {
    if (id === 'tournaments') return true
    if (!currentUser) return false

    const role =
      typeof currentUser.role === 'string'
        ? currentUser.role.toLowerCase()
        : ''

    if (!KNOWN_ROLES.has(role)) return false
    if (PAGE_ROLES[id] && !PAGE_ROLES[id].includes(role)) return false

    return true
  })

  const filteredTournaments = useMemo(() => {
    const term = searchTerm.trim().toLowerCase()
    return tournaments.filter((item) => {
      const matchesSearch =
        !term ||
        String(item.name || '').toLowerCase().includes(term) ||
        String(item.id || '').includes(term)
      return matchesSearch
    })
  }, [tournaments, searchTerm])

  const totalPages = Math.max(1, Math.ceil(filteredTournaments.length / 10))
  const filteredFixtures = useMemo(() => {
    const teamQuery = fixtureTeamFilter.trim()
    const venueQuery = fixtureVenueFilter.trim()

    return [...fixtures]
      .filter((fixture) => {
        if (fixtureStatusFilter && String(fixture.status || '').toLowerCase() !== fixtureStatusFilter) return false
        if (teamQuery && String(fixture.team_a_id ?? '') !== teamQuery && String(fixture.team_b_id ?? '') !== teamQuery) return false
        if (venueQuery && String(fixture.venue_id ?? '') !== venueQuery) return false
        return true
      })
      .sort((a, b) => {
        const aTime = a.scheduled_at ? new Date(a.scheduled_at).getTime() : Number.MAX_SAFE_INTEGER
        const bTime = b.scheduled_at ? new Date(b.scheduled_at).getTime() : Number.MAX_SAFE_INTEGER
        return aTime - bTime
      })
  }, [fixtures, fixtureStatusFilter, fixtureTeamFilter, fixtureVenueFilter])

  const fixturePageSize = 10
  const fixturePageCount = Math.max(1, Math.ceil(filteredFixtures.length / fixturePageSize))
  const effectiveFixturePage = Math.min(fixturePage, fixturePageCount)
  const paginatedFixtures = filteredFixtures.slice(
    (effectiveFixturePage - 1) * fixturePageSize,
    effectiveFixturePage * fixturePageSize,
  )

  const paginatedTournaments = filteredTournaments.slice(
    (currentPage - 1) * 10,
    currentPage * 10,
  )

  const activeCount = useMemo(
    () => tournaments.filter((item) => String(item.status).toLowerCase() === 'active').length,
    [tournaments],
  )

  if (!authReady && !PUBLIC_PAGES.has(page)) {
    return (
      <main className="app-shell">
        <p>Checking your session...</p>
      </main>
    )
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <button className="brand-button" onClick={() => setPage('overview')} aria-label="MatchGrid home">
          <span className="brand-mark">M</span>
          <span className="brand-copy"><strong>MatchGrid</strong><small>Sports management platform</small></span>
        </button>
        <div className="topbar-actions">
          <label className="theme-control">Theme
            <select value={theme} onChange={(event) => changeTheme(event.target.value)} aria-label="Color theme">
              <option value="system">System</option><option value="light">Light</option><option value="dark">Dark</option>
            </select>
          </label>
          {currentUser ? (
            <>
              <span className="user-badge">
                {currentUser.email} | {currentUser.role}
              </span>
              <button
                className="button button-secondary"
                onClick={handleLogout}
              >
                Sign out
              </button>
            </>
          ) : (
            <>
              <button
                className="button button-secondary"
                onClick={() => {
                  setAuthError('')
                  setAuthSuccess('')
                  setPage('login')
                }}
              >
                Sign in
              </button>
              <button
                className="button button-primary"
                onClick={() => {
                  setAuthError('')
                  setAuthSuccess('')
                  setPage('register')
                }}
              >
                Register
              </button>
            </>
          )}
          <span className="api-indicator"><i /> API configured</span>
        </div>
      </header>

      <div className="layout">
        <aside className="sidebar">
          <p className="nav-label">WORKSPACE</p>
          {visibleNavItems.map(([id, label]) => (
            <button key={id} className={`nav-item ${page === id ? 'active' : ''}`} onClick={() => { setPage(id); if (id === 'create') resetForm() }}>
              <span className="nav-dot" />{label}
            </button>
          ))}
          {page === 'details' && <button className="nav-item active" onClick={() => setPage('details')}><span className="nav-dot" />Tournament details</button>}
          <div className="sidebar-note"><span className="note-mark">i</span><p>Protected actions require a valid sign-in token. The backend remains responsible for authorization.</p></div>
        </aside>

        <section className="content">
          {(page === 'login' || page === 'register') && (
            <AuthPanel
              mode={page}
              loading={authLoading}
              error={authError}
              success={authSuccess}
              onSubmit={handleAuthSubmit}
              onSwitch={(nextMode) => {
                setAuthError('')
                setAuthSuccess('')
                setPage(nextMode)
              }}
            />
          )}

          {page === 'overview' && <>
            <div className="page-heading"><div><p className="eyebrow">YOUR SPORTS HUB</p><h1>Manage the game.</h1><p className="muted">Create tournaments, follow standings, and keep your competition organized.</p></div>{currentUser?.role === 'organiser' && <button className="button button-primary" onClick={() => { resetForm(); setPage('create') }}>+ Create tournament</button>}</div>
            <div className="hero-panel"><div><p className="eyebrow">MATCHGRID WORKSPACE</p><h2>Every competition.<br />One clear view.</h2><p>Keep tournament information and team performance in one place.</p><button className="button button-on-dark" onClick={() => setPage('tournaments')}>← Back to list</button></div><div className="hero-orbit" aria-hidden="true"><span>MG</span><i /><b /></div></div>
            <div className="stats-grid">
              <article className="stat-card"><span className="stat-icon">#</span><p>Total tournaments</p><strong>{tournaments.length}</strong><small>Returned by the API</small></article>
              <article className="stat-card"><span className="stat-icon green">OK</span><p>Active tournaments</p><strong>{activeCount}</strong><small>Based on current status</small></article>
              <article className="stat-card"><span className="stat-icon violet">*</span><p>Competition formats</p><strong>{new Set(tournaments.map((item) => item.format).filter(Boolean)).size}</strong><small>Formats in your list</small></article>
            </div>
            <div className="section-title"><div><h2>Recent tournaments</h2><p className="muted">Latest items returned by the tournament API.</p></div><button className="button button-secondary" onClick={() => setPage('tournaments')}>← Back to list</button></div>
            {listError && <ErrorNotice>{listError}</ErrorNotice>}
            {listLoading ? <Loading label="Loading tournaments..." /> : tournaments.length ? <TournamentTable items={tournaments.slice(0, 5)} onOpen={openTournament} onEdit={beginEdit} canManage={currentUser?.role === 'organiser'} /> : <EmptyState title="No tournaments to show" text="Create a tournament or check back when the API has data." action={() => { resetForm(); setPage('create') }} />}
          </>}

          {page === 'tournaments' && <>
            <div className="page-heading"><div><p className="eyebrow">COMPETITIONS</p><h1>Tournaments</h1><p className="muted">Browse tournament details and current standings.</p></div>{currentUser?.role === 'organiser' && <button className="button button-primary" onClick={() => { resetForm(); setPage('create') }}>+ Create tournament</button>}</div>
            <div className="filter-row">
              <label>
                Search tournaments
                <input
                  type="search"
                  value={searchTerm}
                  placeholder="Search by name or ID..."
                  onChange={(event) => {
                    setSearchTerm(event.target.value)
                    setCurrentPage(1)
                  }}
                  aria-label="Search tournaments by name or ID"
                />
              </label>
              <label>
                Filter by status
                <select
                  value={listStatus}
                  onChange={(event) => {
                    setListStatus(event.target.value)
                    setCurrentPage(1)
                  }}
                >
                  <option value="">All statuses</option>
                  <option value="draft">Draft</option>
                  <option value="active">Active</option>
                  <option value="published">Published</option>
                  <option value="completed">Completed</option>
                  <option value="archived">Archived</option>
                </select>
              </label>
              <button className="button button-secondary" onClick={loadTournaments}>Refresh</button>
            </div>
            <ErrorNotice>{listError}</ErrorNotice>
            {listLoading ? <Loading label="Loading tournaments..." /> : filteredTournaments.length ? (
              <>
                <p className="helper-text">
                  Showing {(currentPage - 1) * 10 + 1}-{Math.min(currentPage * 10, filteredTournaments.length)} of {filteredTournaments.length} tournaments
                </p>
                <TournamentTable items={paginatedTournaments} onOpen={openTournament} onEdit={beginEdit} canManage={currentUser?.role === 'organiser'} />
                <div className="pagination-row">
  <button
    className="button button-secondary"
    onClick={() => setCurrentPage((value) => Math.max(1, value - 1))}
    disabled={currentPage === 1}
  >
    Previous
  </button>
  <span>Page {currentPage} of {totalPages}</span>
  <button
    className="button button-secondary"
    onClick={() => setCurrentPage((value) => Math.min(totalPages, value + 1))}
    disabled={currentPage === totalPages}
  >
    Next
  </button>
</div>
              </>
            ) : <EmptyState title="No matching tournaments" text="Try another search or status filter, or create a tournament." action={() => { resetForm(); setPage('create') }} />}
          </>}

          {page === 'details' && <>
            <div className="page-heading"><div><p className="eyebrow">COMPETITION OVERVIEW</p><h1>Tournament details</h1><p className="muted">Tournament information and standings provided by the API.</p></div><button className="button button-secondary" onClick={() => setPage('tournaments')}>← Back to list</button></div>
            {detailsLoading && <Loading label="Loading tournament details..." />}
            <ErrorNotice>{detailsError}</ErrorNotice>
            {selectedTournament && <><div className="detail-card"><div className="detail-heading"><div><span className="eyebrow">TOURNAMENT #{selectedTournament.id}</span><h2>{selectedTournament.name}</h2><p>{selectedTournament.description || 'No description provided.'}</p></div><span className={statusClass(selectedTournament.status)}>{selectedTournament.status || 'Unknown'}</span></div><div className="detail-meta"><Meta label="Format" value={selectedTournament.format} /><Meta label="Starts" value={dateLabel(selectedTournament.start_date)} /><Meta label="Ends" value={dateLabel(selectedTournament.end_date)} /><Meta label="Organizer ID" value={selectedTournament.organizer_id} /></div><div className="detail-actions">{currentUser?.role === 'organiser' && <button className="button button-primary" onClick={() => beginEdit(selectedTournament)}>Edit tournament</button>}<button className="button button-secondary" onClick={() => openTournament(selectedTournament.id)}>Refresh details</button></div></div><div className="section-title"><div><h2>Fixtures</h2><p className="muted">Scheduled matches returned by the fixtures API.</p></div><button className="button button-secondary" onClick={() => openTournament(selectedTournament.id)} disabled={detailsLoading || fixturesLoading}>Refresh fixtures</button></div>{fixturesLoading ? <Loading label="Loading fixtures..." /> : <><ErrorNotice>{fixturesError}</ErrorNotice><div className="fixture-filters filter-row">
  <label>
    Status
    <select value={fixtureStatusFilter} onChange={(event) => { setFixtureStatusFilter(event.target.value); setFixturePage(1) }}>
      <option value="">All statuses</option>
      <option value="scheduled">Scheduled</option>
      <option value="completed">Completed</option>
      <option value="cancelled">Cancelled</option>
      <option value="postponed">Postponed</option>
    </select>
  </label>
  <label>
    Team ID
    <input type="number" min="1" placeholder="Any team" value={fixtureTeamFilter} onChange={(event) => { setFixtureTeamFilter(event.target.value); setFixturePage(1) }} />
  </label>
  <label>
    Venue ID
    <input type="number" min="1" placeholder="Any venue" value={fixtureVenueFilter} onChange={(event) => { setFixtureVenueFilter(event.target.value); setFixturePage(1) }} />
  </label>
  <button className="button button-secondary" onClick={() => { setFixtureStatusFilter(''); setFixtureTeamFilter(''); setFixtureVenueFilter(''); setFixturePage(1) }}>
    Clear filters
  </button>
</div>
{filteredFixtures.length ? <>
  <p className="helper-text">
    Showing {(fixturePage - 1) * fixturePageSize + 1}|{Math.min(fixturePage * fixturePageSize, filteredFixtures.length)} of {filteredFixtures.length} fixtures
  </p>
  <div className="table-wrap">
    <table>
      <thead><tr><th>Match</th><th>Team A ID</th><th>Team B ID</th><th>Venue ID</th><th>Scheduled at</th><th>Status</th><th>Live Stream</th></tr></thead>
      <tbody>{paginatedFixtures.map((fixture) => {
        const status = String(fixture.status || 'unknown').toLowerCase()
        const scheduledTime = fixture.scheduled_at ? new Date(fixture.scheduled_at).getTime() : NaN
        const isUpcoming = status === 'scheduled' && Number.isFinite(scheduledTime) && scheduledTime >= currentTime
        const displayStatus = isUpcoming ? 'Upcoming' : (status === 'scheduled' ? 'Scheduled' : (fixture.status || 'Unknown'))
        return <tr key={fixture.id}>
          <td><strong>#{fixture.match_number}</strong><small className="cell-subtitle">Fixture ID: {fixture.id}</small></td>
          <td>{fixture.team_a_id ?? 'TBD'}</td>
          <td>{fixture.team_b_id ?? 'TBD'}</td>
          <td>{fixture.venue_id ?? '|'}</td>
          <td>{dateLabel(fixture.scheduled_at)}</td>
          <td><span className={statusClass(isUpcoming ? 'upcoming' : status)}>{displayStatus}</span></td>
          <td><StreamUrlControl key={`${fixture.id}-${fixture.stream_url || ''}`} fixture={fixture} tournamentId={selectedTournament.id} canManage={currentUser?.role === 'organiser' || currentUser?.role === 'organizer'} onSaved={() => openTournament(selectedTournament.id)} /></td>
        </tr>
      })}</tbody>
    </table>
  </div>
  <div className="pagination-row">
    <button className="button button-secondary" onClick={() => setFixturePage((value) => Math.max(1, value - 1))} disabled={fixturePage <= 1}>← Previous</button>
    <span className="helper-text">Page {fixturePage} of {fixturePageCount}</span>
    <button className="button button-secondary" onClick={() => setFixturePage((value) => Math.min(fixturePageCount, value + 1))} disabled={fixturePage >= fixturePageCount}>Next →</button>
  </div>
</> : !fixturesError ? <EmptyState title="No matching fixtures" text="Try changing or clearing the fixture filters." /> : null}</>}<div className="section-title"><div><h2>Standings</h2><p className="muted">Calculated rankings returned by the standings endpoint.</p></div></div>{standings.length ? <div className="table-wrap"><table><thead><tr><th>Rank</th><th>Team</th><th>Played</th><th>W</th><th>D</th><th>L</th><th>Score diff.</th><th>Points</th></tr></thead><tbody>{standings.map((row) => <tr key={row.team_id}><td><span className="rank">#{row.rank}</span></td><td><strong>{row.team_name}</strong></td><td>{row.played}</td><td>{row.wins}</td><td>{row.draws}</td><td>{row.losses}</td><td>{row.score_difference}</td><td><strong>{row.points}</strong></td></tr>)}</tbody></table></div> : <EmptyState title="No standings available" text="The API returned no standings for this tournament yet." />}</>}
            {!detailsLoading && !selectedTournament && !detailsError && <IdLookup onSubmit={openTournament} />}
          </>}

          {page === 'create' && currentUser?.role === 'organiser' && <>
            <div className="page-heading"><div><p className="eyebrow">TOURNAMENT SETUP</p><h1>{editingId ? 'Edit tournament' : 'Create a tournament'}</h1><p className="muted">{editingId ? 'Update tournament details. The backend checks organizer ownership.' : 'Set the essentials before your competition begins.'}</p></div><button className="button button-secondary" onClick={() => { resetForm(); setPage('tournaments') }}>Cancel</button></div>
            <form className="form-card" onSubmit={submitTournament}>
              <div className="form-section-heading"><span className="step-number">01</span><div><h2>Basic information</h2><p>Give your tournament a clear identity.</p></div></div>
              <div className="field"><label htmlFor="tournament-name">Tournament name <span>*</span></label><input id="tournament-name" value={form.name} minLength={3} maxLength={150} required placeholder="e.g. Spring Championship" onChange={(event) => setForm({ ...form, name: event.target.value })} /><small>3ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“150 characters</small></div>
              <div className="field"><label htmlFor="tournament-description">Description</label><textarea id="tournament-description" rows="3" value={form.description} placeholder="What should participants know?" onChange={(event) => setForm({ ...form, description: event.target.value })} /></div>
              <div className="form-grid"><div className="field"><label htmlFor="tournament-format">Tournament format <span>*</span></label><select id="tournament-format" value={form.format} required onChange={(event) => setForm({ ...form, format: event.target.value })}><option value="round_robin">Round robin</option><option value="single_elimination">Single elimination</option><option value="double_elimination">Double elimination</option></select></div><div className="field"><label htmlFor="number-teams">Number of teams</label><input id="number-teams" type="number" min="2" max="256" value={form.number_of_teams} required onChange={(event) => setForm({ ...form, number_of_teams: event.target.value })} /><small>At least 2 teams</small></div></div>
              <div className="form-section-heading second"><span className="step-number">02</span><div><h2>Schedule</h2><p>Choose the start and end of the competition.</p></div></div>
              <div className="form-grid"><div className="field"><label htmlFor="start-date">Start date and time <span>*</span></label><input id="start-date" type="datetime-local" value={form.start_date} required onChange={(event) => setForm({ ...form, start_date: event.target.value })} /></div><div className="field"><label htmlFor="end-date">End date and time <span>*</span></label><input id="end-date" type="datetime-local" value={form.end_date} min={form.start_date || undefined} required onChange={(event) => setForm({ ...form, end_date: event.target.value })} /></div></div>
              <ErrorNotice>{formError}</ErrorNotice><SuccessNotice>{formSuccess}</SuccessNotice>
              <div className="form-footer"><p><span>*</span> Required fields. Sign in as an organiser to submit.</p><button className="button button-primary" type="submit" disabled={formLoading}>{formLoading ? 'Saving...' : editingId ? 'Save changes ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢' : 'Create tournament ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢'}</button></div>
            </form>
          </>}

          {page === 'scoring' && <ScorerPage />}
          {page === 'notifications' && <NotificationsPage onOpenPage={setPage} />}
          {page === 'verify' && <VerificationPage />}
          {page === 'dispute' && <DisputePage />}
          {page === 'result' && <ResultPage />}
          {page === 'standings' && <StandingsPage />}
          {page === 'leaderboard' && <LeaderboardPage />}
          {page === 'resolve' && <DisputeResolutionPage />}
          {page === 'registrations' && currentUser?.role === 'captain' && <RegistrationPage />}
          {page === 'registration-approvals' && currentUser?.role === 'organiser' && <RegistrationApprovalPage />}
      {page === 'team' && <>
            <div className="page-heading"><div><p className="eyebrow">TEAM DIRECTORY</p><h1>Team lookup</h1><p className="muted">Look up an existing team using its numeric ID.</p></div></div>
            <form className="lookup-card" onSubmit={loadTeam}><div className="field"><label htmlFor="team-id">Team ID</label><input id="team-id" inputMode="numeric" pattern="[1-9][0-9]*" value={teamId} onChange={(event) => setTeamId(event.target.value)} placeholder="e.g. 12" required /></div><button className="button button-primary" type="submit" disabled={teamLoading}>{teamLoading ? 'Searching...' : 'Find team'}</button></form>
            <ErrorNotice>{teamError}</ErrorNotice>
            {teamLoading && <Loading label="Loading team..." />}
            {team && <div className="detail-card"><div className="detail-heading"><div><span className="eyebrow">TEAM #{team.id}</span><h2>{team.name}</h2><p>Captain ID: {team.captain_id ?? team.captain?.id ?? 'Not provided'}</p></div><span className={statusClass(team.status)}>{team.status || 'Unknown'}</span></div><div className="detail-meta"><Meta label="Created" value={dateLabel(team.created_at)} /><Meta label="Updated" value={dateLabel(team.updated_at)} /><Meta label="Roster members" value={Array.isArray(team.players) ? team.players.length : 'Not provided'} /></div></div>}
            {team && <>
              <div className="section-title">
                <div>
                  <h2>Team roster</h2>
                  <p className="muted">Active, eligible players can be added. The API checks captain permissions.</p>
                </div>
              </div>
              <form className="lookup-card" onSubmit={(event) => { event.preventDefault(); changeRoster('add', rosterPlayerId) }}>
                <div className="field">
                  <label htmlFor="roster-player-id">Player ID to add</label>
                  <input id="roster-player-id" inputMode="numeric" pattern="[1-9][0-9]*" value={rosterPlayerId} onChange={(event) => setRosterPlayerId(event.target.value)} placeholder="e.g. 7" required />
                </div>
                <button className="button button-primary" type="submit" disabled={rosterLoading}>{rosterLoading ? 'Updating...' : 'Add player'}</button>
              </form>
              <ErrorNotice>{rosterError}</ErrorNotice>
              <SuccessNotice>{rosterSuccess}</SuccessNotice>
              {rosterLoading && <Loading label="Updating team roster..." />}
              {Array.isArray(team.players) && team.players.length > 0 ? (
                <div className="table-wrap">
                  <table>
                    <thead><tr><th>Player</th><th>Player ID</th><th>User ID</th><th>Status</th><th>Actions</th></tr></thead>
                    <tbody>
                      {team.players.map((rosterPlayer) => (
                        <tr key={rosterPlayer.id}>
                          <td><strong>{[rosterPlayer.first_name, rosterPlayer.last_name].filter(Boolean).join(' ') || `Player #${rosterPlayer.id}`}</strong></td>
                          <td>{rosterPlayer.id}</td>
                          <td>{rosterPlayer.user_id ?? '-'}</td>
                          <td><span className={statusClass(rosterPlayer.status)}>{rosterPlayer.status || 'Unknown'}</span></td>
                          <td><div className="table-actions">
                            <button type="button" onClick={() => { setPlayerId(String(rosterPlayer.id)); setPlayer(null); setPlayerError(''); }} disabled={rosterLoading}>Use ID</button>
                            <button type="button" onClick={() => changeRoster('remove', rosterPlayer.id)} disabled={rosterLoading}>Remove</button>
                          </div></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : <EmptyState title="Roster is empty" text="No players are currently assigned to this team. Add a player using their player ID above." />}
            </>}

            <div className="section-title">
              <div>
                <h2>Player profile lookup</h2>
                <p className="muted">Find a player by player ID and view their team assignment.</p>
              </div>
            </div>
            <form className="lookup-card" onSubmit={loadPlayer}>
              <div className="field">
                <label htmlFor="player-id">Player ID</label>
                <input id="player-id" inputMode="numeric" pattern="[1-9][0-9]*" value={playerId} onChange={(event) => setPlayerId(event.target.value)} placeholder="e.g. 7" required />
              </div>
              <button className="button button-primary" type="submit" disabled={playerLoading}>{playerLoading ? 'Searching...' : 'Find player'}</button>
            </form>
            <ErrorNotice>{playerError}</ErrorNotice>
            {playerLoading && <Loading label="Loading player profile..." />}
            {player && <div className="detail-card">
              <div className="detail-heading">
                <div><span className="eyebrow">PLAYER #{player.id}</span><h2>{[player.first_name, player.last_name].filter(Boolean).join(' ') || 'Player profile'}</h2><p>User ID: {player.user_id ?? 'Not provided'}</p></div>
                <span className={statusClass(player.status)}>{player.status || 'Unknown'}</span>
              </div>
              <div className="detail-meta">
                <Meta label="Player ID" value={player.id} />
                <Meta label="Team assignment" value={player.team_id ? `Team #${player.team_id}` : 'Not assigned'} />
                <Meta label="Created" value={dateLabel(player.created_at)} />
                <Meta label="Updated" value={dateLabel(player.updated_at)} />
              </div>
            </div>}
            <div className="section-title">
              <div>
                <h2>Create a team</h2>
                <p className="muted">Enter a team name and the captain's user ID. Organiser access is required.</p>
              </div>
            </div>
            <TeamCreationForm
              onCreated={(createdTeam) => {
                setTeam(createdTeam)
                setTeamId(String(createdTeam.id))
              }}
            />
          </>}

          <footer className="footer"><span>© MatchGrid 2026</span><span>Sports management, made clearer.</span><span className="footer-api">{API_BASE_URL || 'API URL missing'}</span></footer>
        </section>
      </div>
    </main>
  )
}

function TournamentTable({ items, onOpen, onEdit, canManage }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Tournament</th>
            <th>Format</th>
            <th>Schedule</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td>
                <button className="table-link" onClick={() => onOpen(item.id)}>
                  {item.name}
                </button>
                <small className="cell-subtitle">ID: {item.id}</small>
              </td>
              <td>{item.format || '|'}</td>
              <td>
                <span>{dateLabel(item.start_date)}</span>
                <small className="cell-subtitle">to {dateLabel(item.end_date)}</small>
              </td>
              <td>
                <span className={statusClass(item.status)}>
                  {item.status || 'Unknown'}
                </span>
              </td>
              <td>
                <div className="table-actions">
                  <button onClick={() => onOpen(item.id)}>Details</button>
                  {canManage && (
                    <button onClick={() => onEdit(item)}>Edit</button>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Meta({ label, value }) {
  return <div className="meta-item"><span>{label}</span><strong>{value ?? '-'}</strong></div>
}

function EmptyState({ title, text, action }) {
  return <div className="empty-state"><span className="empty-icon">#</span><h3>{title}</h3><p>{text}</p>{action && <button className="button button-secondary" onClick={action}>Create tournament</button>}</div>
}

function IdLookup({ onSubmit }) {
  const [id, setId] = useState('')
  return <form className="lookup-card" onSubmit={(event) => { event.preventDefault(); onSubmit(id) }}><div className="field"><label htmlFor="tournament-id">Tournament ID</label><input id="tournament-id" inputMode="numeric" pattern="[1-9][0-9]*" value={id} onChange={(event) => setId(event.target.value)} placeholder="Enter tournament ID" required /></div><button className="button button-primary" type="submit">Load tournament</button></form>
}


function TeamCreationForm({ onCreated }) {
  const [name, setName] = useState('')
  const [captainId, setCaptainId] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const submitTeam = async (event) => {
    event.preventDefault()
    setError('')
    setSuccess('')

    const cleanName = name.trim()
    if (!cleanName) {
      setError('Team name is required.')
      return
    }

    if (!/^[1-9]\d*$/.test(captainId)) {
      setError('Enter a valid positive captain user ID.')
      return
    }

    setLoading(true)
    try {
      const createdTeam = await apiRequest('/player-team/team', {
        method: 'POST',
        body: JSON.stringify({
          name: cleanName,
          captain_id: Number(captainId),
        }),
      })

      setSuccess(`Team "${createdTeam.name}" created successfully. Team ID: ${createdTeam.id}`)
      setName('')
      setCaptainId('')
      if (onCreated) onCreated(createdTeam)
    } catch (requestError) {
      setError(
        `${requestError.message || 'Could not create team.'} If access is denied, sign in with an organiser account.`,
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <form className="form-card" onSubmit={submitTeam}>
      <div className="field">
        <label htmlFor="new-team-name">Team name *</label>
        <input
          id="new-team-name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          maxLength={100}
          placeholder="e.g. Dhaka Strikers"
          required
        />
        <small>Maximum 100 characters. Duplicate team names are rejected by the API.</small>
      </div>

      <div className="field">
        <label htmlFor="new-team-captain">Captain user ID *</label>
        <input
          id="new-team-captain"
          type="number"
          min="1"
          step="1"
          value={captainId}
          onChange={(event) => setCaptainId(event.target.value)}
          placeholder="e.g. 12"
          required
        />
      </div>

      {error && <ErrorNotice>{error}</ErrorNotice>}
      {success && <SuccessNotice>{success}</SuccessNotice>}

      <div className="form-footer">
        <p>Sign in as an organiser to create a team.</p>
        <button className="button button-primary" type="submit" disabled={loading}>
          {loading ? 'Creating team...' : 'Create team'}
        </button>
      </div>
    </form>
  )
}

function AuthPanel({ mode, loading, error, success, onSubmit, onSwitch }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [role, setRole] = useState('player')

  const isRegister = mode === 'register'

  return (
    <div className="auth-page">
      <form
        className="auth-card"
        onSubmit={(event) => onSubmit(event, mode, { email, password, role })}
      >
        <p className="eyebrow">MATCHGRID ACCOUNT</p>
        <h1>{isRegister ? 'Create your account' : 'Welcome back'}</h1>
        <p className="muted">
          {isRegister
            ? 'Register to get started with MatchGrid.'
            : 'Sign in to access your account.'}
        </p>

        {success && <SuccessNotice>{success}</SuccessNotice>}
        {error && <ErrorNotice>{error}</ErrorNotice>}

        <div className="field">
          <label htmlFor="auth-email">Email address</label>
          <input
            id="auth-email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@example.com"
            required
          />
        </div>

                <div className="field">
          <label htmlFor="auth-password">Password</label>
          <div className="password-input-wrapper">
            <input
              id="auth-password"
              type={showPassword ? 'text' : 'password'}
              autoComplete={isRegister ? 'new-password' : 'current-password'}
              minLength={isRegister ? 8 : undefined}
              maxLength={72}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder={isRegister ? 'At least 8 characters' : 'Enter your password'}
              required
            />
            <button
              type="button"
              className="text-button password-toggle"
              onClick={() => setShowPassword((current) => !current)}
              aria-label={showPassword ? 'Hide password' : 'Show password'}
              title={showPassword ? 'Hide password' : 'Show password'}
            >
              {showPassword ? (
                <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M3 3l18 18" />
                  <path d="M10.6 10.6a2 2 0 0 0 2.8 2.8" />
                  <path d="M9.9 5.2A11 11 0 0 1 12 5c5 0 9 5 9 7a10 10 0 0 1-2.1 3.2" />
                  <path d="M6.2 6.2C4.2 7.5 3 9.5 3 12c0 2 4 7 9 7 1 0 2-.2 2.9-.6" />
                </svg>
              ) : (
                <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7Z" />
                  <circle cx="12" cy="12" r="3" />
                </svg>
              )}
            </button>
          </div>
        </div>
{isRegister && (
          <div className="field">
            <label htmlFor="auth-role">Account role</label>
            <select
              id="auth-role"
              value={role}
              onChange={(event) => setRole(event.target.value)}
            >
              <option value="player">Player</option>
              <option value="spectator">Spectator</option>
              <option value="scorer">Scorer</option>
              <option value="official">Official</option>
              <option value="organiser">Organiser</option>
            </select>
          </div>
        )}
        <button
          className="button button-primary auth-submit"
          type="submit"
          disabled={loading}
        >
          {loading
            ? 'Please wait...'
            : isRegister
              ? 'Create account'
              : 'Sign in'}
        </button>

        <p className="auth-switch">
          {isRegister
            ? 'Already have an account?'
            : "Don't have an account?"}{' '}
          <button
            type="button"
            className="text-button"
            onClick={() => onSwitch(isRegister ? 'login' : 'register')}
          >
            {isRegister ? 'Sign in' : 'Register'}
          </button>
        </p>

        <button
          type="button"
          className="text-button auth-home"
          onClick={() => onSwitch('tournaments')}
        >
          Back to dashboard
        </button>
        {!isRegister && <button type="button" className="button button-secondary auth-submit" onClick={() => onSwitch('tournaments')}>Continue as guest</button>}
      </form>
    </div>
  )
}


function StreamUrlControl({ fixture, tournamentId, canManage, onSaved }) {
  const [url, setUrl] = useState(fixture.stream_url || '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  async function saveStream(event) {
    event.preventDefault()
    setSaving(true)
    setError('')
    try {
      await apiRequest(
        `/matches/tournaments/${tournamentId}/fixtures/${fixture.id}/stream`,
        {
          method: 'PATCH',
          body: JSON.stringify({ stream_url: url.trim() || null }),
        }
      )
      await onSaved()
    } catch (err) {
      setError(err.message || 'Could not save stream URL.')
    } finally {
      setSaving(false)
    }
  }

  if (!canManage) {
    return fixture.stream_url
      ? <a href={fixture.stream_url} target="_blank" rel="noreferrer">Watch Live</a>
      : <span className="muted">Not available</span>
  }

  return (
    <form onSubmit={saveStream} className="stream-url-form">
      <input
        type="url"
        value={url}
        onChange={(event) => setUrl(event.target.value)}
        placeholder="https://stream-link"
        aria-label={`Stream URL for fixture ${fixture.id}`}
      />
      <button className="button button-secondary" type="submit" disabled={saving}>
        {saving ? 'Saving...' : 'Save'}
      </button>
      {error && <small role="alert">{error}</small>}
      {fixture.stream_url && <a href={fixture.stream_url} target="_blank" rel="noreferrer">Preview</a>}
    </form>
  )
}

export default App








