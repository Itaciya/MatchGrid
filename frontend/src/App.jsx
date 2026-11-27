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
import './theme.css'
import RegistrationPage from './RegistrationPage.jsx'
import RegistrationApprovalPage from './RegistrationApprovalPage.jsx'
import TeamPage from './TeamPage.jsx'
import { NotificationsProvider } from './notifications/NotificationsProvider.jsx'
import { useNotifications } from './notifications/notificationContext'
import { LiveFixtureScore } from './LiveFixtures.jsx'
import { useLiveFixtures } from './realtime/useLiveFixtures'
import { FollowButton } from './FollowButton.jsx'

const NAV_ITEMS = [
  ['overview', 'Overview'],
  ['tournaments', 'Tournaments'],
  ['create', 'Create tournament'],
  ['team', 'My teams'],
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
  'home',
  'login',
  'register',
  'tournaments',
  'details',
  'standings',
  'leaderboard',
  'result',
])

const KNOWN_ROLES = new Set([
  'organiser',
  'captain',
  'player',
  'spectator',
  'scorer',
  'official',
])

const ROLE_HINTS = {
  player: 'Join or captain a team and register for tournaments.',
  spectator: 'Follow fixtures, live scores and standings.',
  organiser: 'Create tournaments, approve teams and choose the scorers for your matches.',
  scorer: 'Score the matches an organiser assigns to you.',
}

const PAGE_ROLES = {
  create: ['organiser'],
  'registration-approvals': ['organiser'],
  resolve: ['organiser'],
  registrations: ['player', 'captain'],
  team: ['player'],
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

const FIXTURE_STATUS_LABELS = {
  scheduled: 'Scheduled',
  live: 'Live',
  paused: 'Paused',
  completed: 'Ended',
  cancelled: 'Cancelled',
  bye: 'Bye',
}

function statusClass(value) {
  return `status-pill status-${String(value || 'unknown').toLowerCase().replace(/[^a-z0-9]+/g, '-')}`
}

function UnreadBadge() {
  const { unread } = useNotifications()
  if (!unread) return null
  return <span className="nav-badge" aria-label={`${unread} unread`}>{unread > 99 ? '99+' : unread}</span>
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


function TournamentScorerAssignment({ tournamentId }) {
  const [available, setAvailable] = useState([])
  const [assigned, setAssigned] = useState([])
  const [scorerId, setScorerId] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const loadScorers = useCallback(async () => {
    try {
      const [all, current] = await Promise.all([
        apiRequest(`/official-assignments/tournaments/${tournamentId}/available-scorers`),
        apiRequest(`/official-assignments/tournaments/${tournamentId}/scorers`),
      ])
      setAvailable(Array.isArray(all) ? all : [])
      setAssigned(Array.isArray(current) ? current : [])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [tournamentId])

  useEffect(() => {
    const timer = window.setTimeout(loadScorers, 0)
    return () => window.clearTimeout(timer)
  }, [loadScorers])

  async function assignScorer(event) {
    event.preventDefault()
    if (!scorerId) return
    setSaving(true)
    setError('')
    setSuccess('')
    try {
      await apiRequest(`/official-assignments/tournaments/${tournamentId}/scorers`, {
        method: 'POST',
        body: JSON.stringify({ scorer_id: Number(scorerId) }),
      })
      const added = available.find((item) => String(item.id) === scorerId)
      setSuccess(`${added?.email || 'Scorer'} can now score this tournament's matches.`)
      setScorerId('')
      await loadScorers()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  async function removeScorer(scorer) {
    if (!window.confirm(`Remove ${scorer.email} as a scorer for this tournament?`)) return
    setSaving(true)
    setError('')
    setSuccess('')
    try {
      await apiRequest(`/official-assignments/tournaments/${tournamentId}/scorers/${scorer.id}`, { method: 'DELETE' })
      setSuccess(`${scorer.email} was removed.`)
      await loadScorers()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const assignedIds = new Set(assigned.map((item) => item.id))
  const choices = available.filter((item) => !assignedIds.has(item.id))

  return (
    <section className="form-card scorer-panel">
      <div className="section-title">
        <div>
          <h2>Scorers</h2>
          <p className="muted">Scorers you add here can start matches and record scores for this tournament.</p>
        </div>
      </div>
      {loading ? <Loading label="Loading scorers..." /> : (
        <>
          {assigned.length > 0 ? (
            <ul className="chip-list">
              {assigned.map((scorer) => (
                <li key={scorer.id} className="chip">
                  <span className="chip-avatar">{scorer.email.slice(0, 1).toUpperCase()}</span>
                  {scorer.email}
                  <button type="button" className="chip-remove" onClick={() => removeScorer(scorer)} disabled={saving} aria-label={`Remove ${scorer.email}`}>×</button>
                </li>
              ))}
            </ul>
          ) : <p className="muted">No scorers yet. Add at least one so your matches can be played.</p>}
          {choices.length ? (
            <form className="filter-row" onSubmit={assignScorer}>
              <label>
                Add a scorer
                <select value={scorerId} onChange={(event) => setScorerId(event.target.value)} required>
                  <option value="">Choose a scorer account</option>
                  {choices.map((scorer) => (
                    <option key={scorer.id} value={scorer.id}>{scorer.email}</option>
                  ))}
                </select>
              </label>
              <button className="button button-primary" type="submit" disabled={!scorerId || saving}>
                {saving ? 'Saving...' : 'Add scorer'}
              </button>
            </form>
          ) : !error && <p className="muted small">{available.length ? 'Every scorer account is already on this tournament.' : 'No scorer accounts exist yet. Ask your scorers to sign up with the Scorer role.'}</p>}
        </>
      )}
      <ErrorNotice>{error}</ErrorNotice>
      <SuccessNotice>{success}</SuccessNotice>
    </section>
  )
}

// matchgrid-route-sync-v5
// Pages whose URL can name a tournament, e.g. "#/verify/12" from a
// notification opens score verification with that tournament selected.
const ROUTES_WITH_TOURNAMENT = new Set(["details", "verify", "registration-approvals"]);

function readMatchGridRoute() {
  const raw = window.location.hash.replace(/^#\/?/, "");
  const parts = raw.split("/");
  const page = parts[0] || "home";

  const allowed = new Set([
    "home", "login", "register", "tournaments", "details",
    "standings", "leaderboard", "overview", "create", "team",
    "scoring", "notifications", "verify", "dispute", "result",
    "resolve", "registrations", "registration-approvals"
  ]);

  if (!allowed.has(page)) return { page: "home", tournamentId: null };

  if (ROUTES_WITH_TOURNAMENT.has(page)) {
    const id = Number(parts[1]);
    return {
      page,
      tournamentId: Number.isInteger(id) && id > 0 ? String(id) : null
    };
  }

  return { page, tournamentId: null };
}

function buildMatchGridHash(page, tournamentId) {
  if (ROUTES_WITH_TOURNAMENT.has(page) && tournamentId) {
    return "#/" + page + "/" + encodeURIComponent(tournamentId);
  }
  return "#/" + (page || "home");
}

function App() {
const [page, setPage] = useState(() => readMatchGridRoute().page)
  const [routeTournamentId, setRouteTournamentId] = useState(
    () => readMatchGridRoute().tournamentId
  )
  const [currentUser, setCurrentUser] = useState(null)
  const [authReady, setAuthReady] = useState(false)
  const [authLoading, setAuthLoading] = useState(false)
  const [authError, setAuthError] = useState('')
  const [authSuccess, setAuthSuccess] = useState('')
  const [theme, setTheme] = useState(() => localStorage.getItem('matchgrid-theme') || 'system')
  const [tournaments, setTournaments] = useState([])
  const [listStatus, setListStatus] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [tournamentView, setTournamentView] = useState('grid')
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
  const [tournamentImage, setTournamentImage] = useState(null)
  const [imagePreview, setImagePreview] = useState('')

  const [form, setForm] = useState({
    category: 'sports',
    participation_type: 'team',
    name: '',
    description: '',
    format: 'round_robin',
    start_date: '',
    end_date: '',
    registration_open_at: '',
    registration_close_at: '',
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
      setTournaments(Array.isArray(result) ? result : (Array.isArray(result?.value) ? result.value : []))
    } catch (error) {
      setListError(error.message || 'Could not load tournaments.')
    } finally {
      setListLoading(false)
    }
  }, [listStatus])

  useEffect(() => {
  if (page !== 'home' && page !== 'tournaments' && page !== 'overview') return

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
        setTournaments(Array.isArray(result) ? result : (Array.isArray(result?.value) ? result.value : []))
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

  const openTournament = useCallback(async (id) => {
    if (!Number.isInteger(Number(id)) || Number(id) <= 0) {
      setDetailsError('Enter a valid tournament ID.')
      return
    }
    setPage('details')
    const tournamentId = Number(id)
    setRouteTournamentId(String(tournamentId))
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
  }, [])



  // matchgrid-route-sync-v5
  useEffect(() => {
    const syncFromBrowser = () => {
      const route = readMatchGridRoute();
      setPage(route.page);
      setRouteTournamentId(route.tournamentId);
    };

    window.addEventListener("popstate", syncFromBrowser);
    window.addEventListener("hashchange", syncFromBrowser);

    return () => {
      window.removeEventListener("popstate", syncFromBrowser);
      window.removeEventListener("hashchange", syncFromBrowser);
    };
  }, []);

  useEffect(() => {
    const nextHash = buildMatchGridHash(
      page,
      ROUTES_WITH_TOURNAMENT.has(page) ? routeTournamentId : null
    );

    if (window.location.hash !== nextHash) {
      const method = window.location.hash ? "pushState" : "replaceState";
      window.history[method]({ matchGrid: true }, "", nextHash);
    }
  }, [page, routeTournamentId]);

  useEffect(() => {
    if (
      page !== "details" ||
      !routeTournamentId ||
      selectedTournament?.id === Number(routeTournamentId)
    ) {
      return;
    }

    const timer = window.setTimeout(() => {
      openTournament(routeTournamentId);
    }, 0);

    return () => window.clearTimeout(timer);
  }, [page, routeTournamentId, selectedTournament?.id, openTournament]);

  useEffect(() => {
    return () => {
      if (imagePreview.startsWith('blob:')) {
        URL.revokeObjectURL(imagePreview)
      }
    }
  }, [imagePreview])

  const resetForm = () => {
    setForm({ category: 'sports', participation_type: 'team', name: '', description: '', format: 'round_robin', start_date: '', end_date: '', registration_open_at: '', registration_close_at: '', number_of_teams: '4' })
    setEditingId(null)
    setTournamentImage(null)
    setImagePreview('')
    setFormError('')
    setFormSuccess('')
  }

  const beginEdit = (tournament) => {
    setTournamentImage(null)
    setImagePreview(tournament.image_url ? `${API_BASE_URL}${tournament.image_url}` : '')
    setEditingId(tournament.id)
    setForm({
      category: tournament.category || 'sports',
      participation_type: tournament.participation_type || 'team',
      name: tournament.name || '',
      description: tournament.description || '',
      format: tournament.format || 'round_robin',
      start_date: dateInputValue(tournament.start_date),
      end_date: dateInputValue(tournament.end_date),
      registration_open_at: dateInputValue(tournament.registration_open_at),
      registration_close_at: dateInputValue(tournament.registration_close_at),
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
    if (!form.format || !form.start_date || !form.end_date || !form.registration_open_at || !form.registration_close_at) return setFormError('All tournament and registration dates are required.')

    const start = new Date(form.start_date)
    const end = new Date(form.end_date)
    const registrationOpen = new Date(form.registration_open_at)
    const registrationClose = new Date(form.registration_close_at)

    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || end <= start) {
      return setFormError('End date must be after the start date.')
    }

    if (Number.isNaN(registrationOpen.getTime()) || Number.isNaN(registrationClose.getTime()) || registrationClose <= registrationOpen) return setFormError('Registration closing must be after registration opening.')
    if (registrationClose > start) return setFormError('Registration must close before the tournament starts.')

    const body = {
      category: form.category,
      participation_type: form.participation_type,
      name: form.name.trim(),
      description: form.description.trim() || null,
      format: form.format,
      format_config: ['round_robin', 'single_elimination', 'double_elimination'].includes(form.format)
        ? { number_of_teams: Number(form.number_of_teams) }
        : null,
      start_date: start.toISOString(),
      end_date: end.toISOString(),
      registration_open_at: registrationOpen.toISOString(),
      registration_close_at: registrationClose.toISOString(),
    }

    setFormLoading(true)

    try {
      const result = editingId
        ? await apiRequest(`/organiser/tournaments/${editingId}`, { method: 'PATCH', body: JSON.stringify(body) })
        : await apiRequest('/organiser/tournaments', { method: 'POST', body: JSON.stringify(body) })

      let savedTournament = result

      if (tournamentImage) {
        const imageFormData = new FormData()
        imageFormData.append('file', tournamentImage)

        await apiRequest(`/organiser/tournaments/${result.id}/image`, {
          method: 'POST',
          body: imageFormData,
        })

        savedTournament = await apiRequest(`/tournaments/${result.id}`)
      }

      setFormSuccess(editingId ? 'Tournament updated successfully.' : 'Tournament created successfully.')
      setSelectedTournament(savedTournament)
      setRouteTournamentId(String(savedTournament.id))
      await loadTournaments()
      setPage('details')
      setForm({ category: 'sports', participation_type: 'team', name: '', description: '', format: 'round_robin', start_date: '', end_date: '', registration_open_at: '', registration_close_at: '', number_of_teams: '4' })
      setEditingId(null)
      setTournamentImage(null)
      setImagePreview('')
    } catch (error) {
      setFormError(
        error.status === 401 || error.status === 403
          ? `${error.message} Sign in with an organiser account to create tournaments.`
          : error.message || 'Unable to save the tournament.',
      )
    } finally {
      setFormLoading(false)
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

  // Only the organiser who created a tournament may manage it.
  const isOwner = (tournament) => currentUser?.role === 'organiser'
    && tournament?.organizer_id === currentUser?.id

  const visibleNavItems = NAV_ITEMS.filter(([id]) => {
    // Fixtures, standings and results are public: show them to everyone.
    if (['tournaments', 'standings', 'leaderboard', 'result'].includes(id)) return true
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
      const matchesCategory =
        !categoryFilter || String(item.category || 'sports').toLowerCase() === categoryFilter
      return matchesSearch && matchesCategory
    })
  }, [tournaments, searchTerm, categoryFilter])

  const totalPages = Math.max(1, Math.ceil(filteredTournaments.length / 10))
  // Live scores and statuses for the open tournament (also for guests).
  const liveFixtures = useLiveFixtures(page === 'details' ? fixtures : [])

  // The first match going live makes an upcoming tournament ongoing; show
  // that straight away instead of waiting for a reload.
  const anyMatchLive = Object.values(liveFixtures.statuses).some((value) => value === 'live' || value === 'paused')
  const tournamentStatus = selectedTournament?.status === 'upcoming' && anyMatchLive
    ? 'ongoing'
    : selectedTournament?.status

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

  // Filter choices come from the fixtures themselves, labelled by name.
  const fixtureTeamOptions = useMemo(() => {
    const teams = new Map()
    fixtures.forEach((fixture) => {
      if (fixture.team_a_id) teams.set(fixture.team_a_id, fixture.team_a_name || 'Unnamed team')
      if (fixture.team_b_id) teams.set(fixture.team_b_id, fixture.team_b_name || 'Unnamed team')
    })
    return [...teams].sort((a, b) => a[1].localeCompare(b[1]))
  }, [fixtures])

  const fixtureVenueOptions = useMemo(() => {
    const venues = new Map()
    fixtures.forEach((fixture) => {
      if (fixture.venue_id) venues.set(fixture.venue_id, fixture.venue_name || 'Unnamed venue')
    })
    return [...venues].sort((a, b) => a[1].localeCompare(b[1]))
  }, [fixtures])

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
    () => tournaments.filter((item) => String(item.status).toLowerCase() === 'ongoing').length,
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
    <NotificationsProvider user={currentUser}>
    <main className="app-shell">
      <header className="topbar">
        <button className="brand-button" onClick={() => setPage('home')} aria-label="MatchGrid home">
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

      <div className={page === 'home' ? 'layout public-home-layout' : 'layout'}>
        {page !== 'home' && <aside className="sidebar">
          <p className="nav-label">WORKSPACE</p>
          {visibleNavItems.map(([id, label]) => (
            <button key={id} className={`nav-item ${page === id ? 'active' : ''}`} onClick={() => { setRouteTournamentId(null); setPage(id); if (id === 'create') resetForm() }}>
              <span className="nav-dot" />{label}
              {id === 'notifications' && <UnreadBadge />}
            </button>
          ))}
          {page === 'details' && <button className="nav-item active" onClick={() => setPage('details')}><span className="nav-dot" />Tournament details</button>}
          <div className="sidebar-note"><span className="note-mark">i</span><p>{currentUser ? `Signed in as ${currentUser.role}. Menu items match what your role can do.` : 'Browse tournaments, standings and results freely. Sign in to play, organise or score.'}</p></div>
        </aside>}

        <section className="content">
          {page === 'home' && (
            <div className="public-home">
              <section className="home-hero">
                                <div className="hero-slideshow" aria-hidden="true">
                  <img className="hero-slide" src="/images/ss1.jpeg" alt="" />
                  <img className="hero-slide" src="/images/ss2.jpeg" alt="" />
                  <img className="hero-slide" src="/images/ss3.jpg" alt="" />
                  <img className="hero-slide" src="/images/ss5.jpg" alt="" />
                  <img className="hero-slide" src="/images/ss6.jpg" alt="" />
                </div>

                <p className="eyebrow">WELCOME TO MATCHGRID</p>
                <h1>Where every competition finds its place.</h1>
                <p>Create tournaments, discover games, and follow every competition in one place.</p>
                <div className="home-hero-actions">
                  <button className="button button-primary" onClick={() => setPage('tournaments')}>Explore tournaments</button>
                  <button className="button button-secondary" onClick={() => setPage('register')}>Get started</button>
                  <button className="button button-secondary" onClick={() => setPage('tournaments')}>Continue as Guest</button>
                </div>
              </section>

              <section className="home-section" id="games">
                <div className="section-title">
                  <div><p className="eyebrow">EXPLORE</p><h2>Discover games</h2><p className="muted">Choose a game and find competitions around it.</p></div>
                </div>
                <div className="game-card-grid">
  <article className="game-placeholder">
    <img className="game-cover-image" src="/images/AUProBasketball_600x600_General.jpg" alt="Basketball" />
  </article>
  <article className="game-placeholder">
    <img className="game-cover-image" src="/images/cricket-ball-and-bat-on-grass-photo.jpg" alt="Cricket" />
  </article>
  <article className="game-placeholder">
    <img className="game-cover-image" src="/images/EGS_EASPORTSFC26StandardEdition_EACANADA_S2_1200x1600-effee280c00b9890a0c5249d4b0e5c97.jpeg" alt="Football" />
  </article>
  <article className="game-placeholder">
    <img className="game-cover-image" src="/images/fortnite-hero-december.avif" alt="Fortnite" />
  </article>
  <article className="game-placeholder">
    <img className="game-cover-image" src="/images/images.jpeg" alt="Game cover" />
  </article>
  <article className="game-placeholder">
    <img className="game-cover-image" src="/images/MV5BODhlZDk5Y2EtMGFhOS00MTQ5LTgwNjgtYTI2ZmE1Y2ZjMDE2XkEyXkFqcGc@._V1_FMjpg_UX1000_.jpg" alt="Game cover" />
  </article>
  <article className="game-placeholder">
    <img className="game-cover-image" src="/images/ping-pong-lautre-usine-cholet.png" alt="Table tennis" />
  </article>
  <article className="game-placeholder">
    <img className="game-cover-image" src="/images/PlayerUnknown's_Battlegrounds_Mobile.webp" alt="PUBG Mobile" />
  </article>
</div>
              </section>

              <section className="home-section" id="featured-tournaments">
                <div className="section-title">
                  <div><p className="eyebrow">WHAT'S HAPPENING</p><h2>Featured tournaments</h2><p className="muted">Explore competitions hosted by the MatchGrid community.</p></div>
                  <button className="button button-secondary" onClick={() => setPage('tournaments')}>View all</button>
                </div>
                <div className="featured-grid">
                  {tournaments.slice(0, 3).map((item) => (
                    <article
                      className="featured-card featured-card-clickable"
                      key={item.id}
                      role="button"
                      tabIndex={0}
                      aria-label={`View ${item.name} tournament details`}
                      onClick={() => openTournament(item.id)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter' || event.key === ' ') {
                          event.preventDefault()
                          openTournament(item.id)
                        }
                      }}
                    >
                      {item.image_url ? (
  <img className="featured-banner-image" src={`${API_BASE_URL}${item.image_url}`} alt={`${item.name} tournament banner`} />
) : (
  <div className="featured-banner-placeholder">Tournament banner</div>
)}
                      <div className="featured-card-body">
                        <span className={statusClass(item.status)}>{item.status || 'Upcoming'}</span>
                        <h3>{item.name}</h3>
                        <button className="button button-secondary" onClick={(event) => { event.stopPropagation(); openTournament(item.id) }}>View details</button>
                      </div>
                    </article>
                  ))}
                  {!tournaments.length && <p className="muted">No featured tournaments available yet.</p>}
                </div>
              </section>

              <section className="home-about" id="about">
                <p className="eyebrow">ABOUT MATCHGRID</p>
                <h2>One platform. Every competition.</h2>
                <p>MatchGrid helps organisers and participants manage tournaments, fixtures, results, and standings.</p>
              </section>

              <footer className="public-home-footer">
                <strong>MatchGrid</strong>
                <span>Sports and esports tournament management.</span>
              </footer>
            </div>
          )}

          {(page === 'login' || page === 'register') && (
            <AuthPanel
              // A fresh form per mode: details typed while registering
              // (including the password) must not carry over to sign-in.
              key={page}
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
            <div className="hero-panel"><div><p className="eyebrow">MATCHGRID WORKSPACE</p><h2>Every competition.<br />One clear view.</h2><p>Keep tournament information and team performance in one place.</p></div><div className="hero-orbit" aria-hidden="true"><span>MG</span><i /><b /></div></div>
            <div className="stats-grid">
              <article className="stat-card"><span className="stat-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m8 21 4-7 4 7"/><path d="M12 14 5 3h14l-7 11Z"/><path d="M5 3 3 8h18l-2-5"/></svg></span><p>Total tournaments</p><strong>{tournaments.length}</strong><small>All competitions in MatchGrid</small></article>
              <article className="stat-card"><span className="stat-icon green" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 12h4l3-8 4 16 3-8h4"/></svg></span><p>Active tournaments</p><strong>{activeCount}</strong><small>Currently in progress</small></article>
              <article className="stat-card"><span className="stat-icon violet" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg></span><p>Competition formats</p><strong>{new Set(tournaments.map((item) => item.format).filter(Boolean)).size}</strong><small>Different formats available</small></article>
            </div>
            <div className="section-title"><div><h2>Recent tournaments</h2><p className="muted">Latest items returned by the tournament API.</p></div><button className="button button-secondary" onClick={() => setPage('tournaments')}>← Back to list</button></div>
            {listError && <ErrorNotice>{listError}</ErrorNotice>}
            {listLoading ? <Loading label="Loading tournaments..." /> : tournaments.length ? <TournamentTable items={tournaments.slice(0, 5)} onOpen={openTournament} onEdit={beginEdit} canManage={isOwner} /> : <EmptyState title="No tournaments to show" text="Create a tournament or check back when the API has data." action={() => { resetForm(); setPage('create') }} />}
          </>}

          {page === 'tournaments' && <>
            <div className="page-heading"><div><p className="eyebrow">COMPETITIONS</p><h1>Tournaments</h1><p className="muted">Browse tournament details and current standings.</p></div>{currentUser?.role === 'organiser' && <button className="button button-primary" onClick={() => { resetForm(); setPage('create') }}>+ Create tournament</button>}</div>
            <div className="tournament-search-simple">
              <span aria-hidden="true">?</span>
              <input
                type="search"
                value={searchTerm}
                placeholder="Search tournaments by name or ID..."
                onChange={(event) => {
                  setSearchTerm(event.target.value)
                  setCurrentPage(1)
                }}
                aria-label="Search tournaments by name or ID"
              />
            </div>
            <div className="filter-row">
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
                  <option value="upcoming">Upcoming</option>
                  <option value="ongoing">Ongoing</option>
                  <option value="completed">Completed</option>
                </select>
              </label>
              <label>
                Filter by category
                <select
                  value={categoryFilter}
                  onChange={(event) => {
                    setCategoryFilter(event.target.value)
                    setCurrentPage(1)
                  }}
                >
                  <option value="">All categories</option>
                  <option value="sports">Sports</option>
                  <option value="esports">Esports</option>
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
                <div className="view-toggle" role="group" aria-label="Tournament view">
                  <button className={`button ${tournamentView === 'grid' ? 'button-primary' : 'button-secondary'}`} onClick={() => setTournamentView('grid')}>Grid</button>
                  <button className={`button ${tournamentView === 'list' ? 'button-primary' : 'button-secondary'}`} onClick={() => setTournamentView('list')}>List</button>
                </div>
                {tournamentView === 'list' ? (
                  <TournamentTable items={paginatedTournaments} onOpen={openTournament} onEdit={beginEdit} canManage={isOwner} />
                ) : (
                  <div className="tournament-grid">
                    {paginatedTournaments.map((item) => (
                      <article className="tournament-grid-card" key={item.id}>
                        {item.image_url ? (
                          <img
                            src={`${API_BASE_URL}${item.image_url}`}
                            alt={item.name}
                          />
                        ) : (
                          <div className="tournament-grid-image-placeholder">No image</div>
                        )}
                        <div className="tournament-grid-card-body">
                          <span className={statusClass(item.status)}>{item.status || 'Upcoming'}</span>
                          <h3>{item.name}</h3>
                          <p>{item.category === 'esports' ? 'Esports' : 'Sports'}</p>
                          <button className="button button-secondary" onClick={() => openTournament(item.id)}>View details</button>
                          {isOwner(item) && (
                            <button className="button button-secondary" onClick={() => beginEdit(item)}>Edit</button>
                          )}
                        </div>
                      </article>
                    ))}
                  </div>
                )}
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
            {selectedTournament && <><div className="detail-top-cards"><div className="detail-card">
{selectedTournament.image_url ? (
  <img className="tournament-detail-image" src={`${API_BASE_URL}${selectedTournament.image_url}`} alt={`${selectedTournament.name} banner`} />
) : (
  <div className="tournament-detail-image-placeholder">No tournament image available</div>
)}
<div className="detail-heading"><div><span className="eyebrow">TOURNAMENT</span><h2>{selectedTournament.name}</h2><p>{selectedTournament.description || 'No description provided.'}</p></div><span className={statusClass(tournamentStatus)}>{tournamentStatus || 'Unknown'}</span></div><div className="detail-meta"><Meta label="Format" value={selectedTournament.format} /><Meta label="Starts" value={dateLabel(selectedTournament.start_date)} /><Meta label="Ends" value={dateLabel(selectedTournament.end_date)} /></div><div className="detail-actions">{['player', 'captain'].includes(currentUser?.role) && <button className="button button-primary" onClick={() => setPage('registrations')}>Register for this tournament</button>}{isOwner(selectedTournament) && <><button className="button button-primary" onClick={async () => {
  if (!window.confirm(`Create and publish fixtures for ${selectedTournament.name}? Fixtures are generated from approved teams and become public immediately. This cannot be undone.`)) return
  try {
    setFixturesError('')
    await apiRequest(`/matches/tournaments/${selectedTournament.id}/fixtures/auto-generate`, { method: 'POST' })
    await openTournament(selectedTournament.id)
  } catch (error) {
    setFixturesError(error.message || 'Could not generate and publish fixtures.')
  }
}}>Create & Publish Fixtures</button><button className="button button-primary" onClick={() => beginEdit(selectedTournament)}>Edit tournament</button>{selectedTournament.status === 'ongoing' && <button className="button button-secondary" onClick={async () => { if (!window.confirm('End this tournament? It will be marked as completed.')) return; try { await apiRequest(`/organiser/tournaments/${selectedTournament.id}/end`, { method: 'POST' }); await openTournament(selectedTournament.id) } catch (error) { window.alert(error.message) } }}>End tournament</button>}{selectedTournament.status !== 'archived' && <button className="button button-secondary" style={{ color: '#c0392b' }} onClick={async () => { if (!window.confirm('Delete this tournament? It will be hidden from everyone.')) return; try { await apiRequest(`/organiser/tournaments/${selectedTournament.id}/archive`, { method: 'PATCH' }); setPage('tournaments') } catch (error) { window.alert(error.message) } }}>Delete tournament</button>}</>}<button className="button button-secondary" onClick={() => openTournament(selectedTournament.id)}>Refresh details</button>{currentUser && <FollowButton tournamentId={selectedTournament.id} />}</div></div>{isOwner(selectedTournament) && <TournamentScorerAssignment tournamentId={selectedTournament.id} />}</div><div className="section-title"><div><h2>Fixtures</h2><p className="muted">Scheduled matches returned by the fixtures API.</p></div><button className="button button-secondary" onClick={() => openTournament(selectedTournament.id)} disabled={detailsLoading || fixturesLoading}>Refresh fixtures</button></div>{fixturesLoading ? <Loading label="Loading fixtures..." /> : <><ErrorNotice>{fixturesError}</ErrorNotice><div className="fixture-filters filter-row">
  <label>
    Status
    <select value={fixtureStatusFilter} onChange={(event) => { setFixtureStatusFilter(event.target.value); setFixturePage(1) }}>
      <option value="">All statuses</option>
      <option value="scheduled">Scheduled</option>
      <option value="live">Live</option>
      <option value="paused">Paused</option>
      <option value="completed">Ended</option>
      <option value="cancelled">Cancelled</option>
      <option value="bye">Bye</option>
    </select>
  </label>
  <label>
    Team
    <select value={fixtureTeamFilter} onChange={(event) => { setFixtureTeamFilter(event.target.value); setFixturePage(1) }}>
      <option value="">All teams</option>
      {fixtureTeamOptions.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
    </select>
  </label>
  <label>
    Venue
    <select value={fixtureVenueFilter} onChange={(event) => { setFixtureVenueFilter(event.target.value); setFixturePage(1) }}>
      <option value="">All venues</option>
      {fixtureVenueOptions.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
    </select>
  </label>
  <button className="button button-secondary" onClick={() => { setFixtureStatusFilter(''); setFixtureTeamFilter(''); setFixtureVenueFilter(''); setFixturePage(1) }}>
    Clear filters
  </button>
</div>
{filteredFixtures.length ? <>
  <p className="helper-text">
    Showing {(fixturePage - 1) * fixturePageSize + 1}–{Math.min(fixturePage * fixturePageSize, filteredFixtures.length)} of {filteredFixtures.length} fixtures
  </p>
  <div className="table-wrap">
    <table>
      <thead><tr><th>Match</th><th>Team A</th><th>Score</th><th>Team B</th><th>Venue</th><th>Scheduled at</th><th>Status</th><th>Live Stream</th></tr></thead>
      <tbody>{paginatedFixtures.map((fixture) => {
        const status = String(liveFixtures.statuses[fixture.id] || fixture.status || 'unknown').toLowerCase()
        const scheduledTime = fixture.scheduled_at ? new Date(fixture.scheduled_at).getTime() : NaN
        const isUpcoming = status === 'scheduled' && Number.isFinite(scheduledTime) && scheduledTime >= currentTime
        const displayStatus = isUpcoming ? 'Upcoming' : (FIXTURE_STATUS_LABELS[status] || fixture.status || 'Unknown')
        return <tr key={fixture.id}>
          <td><strong>Match {fixture.match_number}</strong>{fixture.round_name && <small className="cell-subtitle">{fixture.round_name}</small>}</td>
          <td>{fixture.team_a_id ? (fixture.team_a_name || 'Unnamed team') : (fixture.status === 'bye' ? 'Bye' : 'TBD')}</td>
          <td><LiveFixtureScore fixture={fixture} live={liveFixtures} /></td>
          <td>{fixture.team_b_id ? (fixture.team_b_name || 'Unnamed team') : (fixture.status === 'bye' ? 'Bye' : 'TBD')}</td>
          <td>{fixture.venue_name || 'Not set'}</td>
          <td>{dateLabel(fixture.scheduled_at)}</td>
          <td><span className={statusClass(isUpcoming ? 'upcoming' : status)}>{displayStatus}</span></td>
          <td><StreamUrlControl key={`${fixture.id}-${fixture.stream_url || ''}`} fixture={fixture} tournamentId={selectedTournament.id} canManage={isOwner(selectedTournament)} onSaved={() => openTournament(selectedTournament.id)} /></td>
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
              <div className="field"><label htmlFor="tournament-name">Tournament name <span>*</span></label><input id="tournament-name" value={form.name} minLength={3} maxLength={150} required placeholder="e.g. Spring Championship" onChange={(event) => setForm({ ...form, name: event.target.value })} /><small>3-150 characters</small></div>
              <div className="field"><label htmlFor="tournament-description">Description</label><textarea id="tournament-description" rows="3" value={form.description} placeholder="What should participants know?" onChange={(event) => setForm({ ...form, description: event.target.value })} /></div>
              <div className="field">
                <label htmlFor="tournament-category">Category <span>*</span></label>
                <select
                  id="tournament-category"
                  value={form.category}
                  required
                  onChange={(event) => setForm({ ...form, category: event.target.value })}
                >
                  <option value="sports">Sports</option>
                  <option value="esports">Esports</option>
                </select>
              </div>

              <div className="field"><label htmlFor="participation-type">Participation type <span>*</span></label><select id="participation-type" value={form.participation_type} required onChange={(event) => setForm({ ...form, participation_type: event.target.value })}><option value="team">Team</option><option value="individual">Individual</option></select><small>{form.participation_type === "team" ? "Players register through their team captain." : "Each player registers individually."}</small></div>

              <div className="field tournament-image-field">
                <label htmlFor="tournament-image">Tournament picture</label>
                {imagePreview && <div className="tournament-image-preview"><img src={imagePreview} alt="Tournament preview" /></div>}
                <input id="tournament-image" type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => {
                  const file = event.target.files?.[0] || null
                  if (!file) return
                  if (file.size > 5 * 1024 * 1024) {
                    setFormError('Image size must not exceed 5 MB.')
                    event.target.value = ''
                    return
                  }
                  setFormError('')
                  const previewUrl = URL.createObjectURL(file)
                  setImagePreview(previewUrl)
                  setTournamentImage(file)
                }} />
                <small>JPEG, PNG, or WebP. Maximum size 5 MB.</small>
              </div>
              <div className="form-grid"><div className="field"><label htmlFor="tournament-format">Tournament format <span>*</span></label><select id="tournament-format" value={form.format} required onChange={(event) => setForm({ ...form, format: event.target.value })}><option value="round_robin">Round robin</option><option value="single_elimination">Single elimination</option></select></div>{form.participation_type === "team" && <div className="field"><label htmlFor="number-teams">Number of teams</label><input id="number-teams" type="number" min="2" max="256" value={form.number_of_teams} required onChange={(event) => setForm({ ...form, number_of_teams: event.target.value })} /><small>At least 2 teams</small></div>}</div>
              <div className="form-section-heading second"><span className="step-number">02</span><div><h2>Schedule</h2><p>Choose the start and end of the competition.</p></div></div>
              <div className="form-grid"><div className="field"><label htmlFor="registration-open">Registration opens <span>*</span></label><input id="registration-open" type="datetime-local" value={form.registration_open_at} required onChange={(event) => setForm({ ...form, registration_open_at: event.target.value })} /></div><div className="field"><label htmlFor="registration-close">Registration closes <span>*</span></label><input id="registration-close" type="datetime-local" value={form.registration_close_at} min={form.registration_open_at || undefined} required onChange={(event) => setForm({ ...form, registration_close_at: event.target.value })} /><small>After registration opens, and before the tournament starts.</small></div></div>
              <div className="form-grid"><div className="field"><label htmlFor="start-date">Start date and time <span>*</span></label><input id="start-date" type="datetime-local" value={form.start_date} min={form.registration_close_at || undefined} required onChange={(event) => setForm({ ...form, start_date: event.target.value })} /><small>On or after registration closes.</small></div><div className="field"><label htmlFor="end-date">End date and time <span>*</span></label><input id="end-date" type="datetime-local" value={form.end_date} min={form.start_date || undefined} required onChange={(event) => setForm({ ...form, end_date: event.target.value })} /></div></div>
              <ErrorNotice>{formError}</ErrorNotice><SuccessNotice>{formSuccess}</SuccessNotice>
              <div className="form-footer"><p><span>*</span> Required fields. Sign in as an organiser to submit.</p><button className="button button-primary" type="submit" disabled={formLoading}>{formLoading ? 'Saving...' : editingId ? 'Save changes ?' : 'Create tournament +'}</button></div>
            </form>
          </>}

          {page === 'scoring' && <ScorerPage />}
          {page === 'notifications' && <NotificationsPage />}
          {page === 'verify' && currentUser?.role === 'organiser' && <VerificationPage key={routeTournamentId || 'none'} currentUser={currentUser} initialTournamentId={routeTournamentId} />}
          {page === 'dispute' && <DisputePage />}
          {page === 'result' && <ResultPage />}
          {page === 'standings' && <StandingsPage />}
          {page === 'leaderboard' && <LeaderboardPage />}
          {page === 'resolve' && <DisputeResolutionPage />}
          {page === 'registrations' && ['player', 'captain'].includes(currentUser?.role) && <RegistrationPage initialTournamentId={selectedTournament?.id} />}
          {page === 'registration-approvals' && currentUser?.role === 'organiser' && <RegistrationApprovalPage key={routeTournamentId || 'none'} currentUser={currentUser} initialTournamentId={routeTournamentId} />}
          {page === 'team' && currentUser?.role === 'player' && <TeamPage />}

          <footer className="footer"><span>© MatchGrid 2026</span><span>Sports management, made clearer.</span></footer>
        </section>
      </div>
    </main>
    </NotificationsProvider>
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
                <div className="tournament-list-info">
                  {item.image_url ? (
                    <img
                      className="tournament-list-thumbnail"
                      src={`${API_BASE_URL}${item.image_url}`}
                      alt={item.name}
                    />
                  ) : (
                    <div className="tournament-list-thumbnail tournament-list-image-placeholder">🏆</div>
                  )}
                  <div>
                    <button className="table-link" onClick={() => onOpen(item.id)}>
                      {item.name}
                    </button>
                    <small className="cell-subtitle">ID: {item.id}</small>
                  </div>
                </div>
              </td>
              <td>{item.format ? item.format.replace('_', ' ') : '-'}</td>
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
                  {canManage(item) && (
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
            <label htmlFor="auth-role">I want to</label>
            <select
              id="auth-role"
              value={role}
              onChange={(event) => setRole(event.target.value)}
            >
              <option value="player">Play in tournaments (Player)</option>
              <option value="spectator">Follow matches (Spectator)</option>
              <option value="organiser">Run tournaments (Organiser)</option>
              <option value="scorer">Keep score for matches (Scorer)</option>
            </select>
            <small>{ROLE_HINTS[role]}</small>
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


function getEmbedStreamUrl(rawUrl) {
  try {
    const url = new URL(rawUrl)
    const host = url.hostname.replace(/^www\./, '')
    let videoId = ''

    if (host === 'youtu.be') {
      videoId = url.pathname.slice(1).split('/')[0]
    } else if (host === 'youtube.com' || host === 'm.youtube.com') {
      const parts = url.pathname.split('/').filter(Boolean)

      if (url.pathname === '/watch') {
        videoId = url.searchParams.get('v') || ''
      } else if (['live', 'shorts', 'embed'].includes(parts[0])) {
        videoId = parts[1] || ''
      }
    }

    return videoId
      ? `https://www.youtube.com/embed/${videoId}?autoplay=0`
      : rawUrl
  } catch {
    return ''
  }
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
    if (!fixture.stream_url) {
      return <span className="muted">Stream not available</span>
    }

    const embedUrl = getEmbedStreamUrl(fixture.stream_url)

    return (
      <div className="live-stream-player">
        {embedUrl ? (
          <iframe
            src={embedUrl}
            title={`Live stream for match ${fixture.match_number}`}
            width="320"
            height="180"
            allow="autoplay; encrypted-media; picture-in-picture; fullscreen"
            allowFullScreen
            referrerPolicy="strict-origin-when-cross-origin"
          />
        ) : (
          <a href={fixture.stream_url} target="_blank" rel="noreferrer">
            Open live stream
          </a>
        )}
        <p>Match #{fixture.match_number}</p>
      </div>
    )
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














