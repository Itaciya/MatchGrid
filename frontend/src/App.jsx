import { useCallback, useEffect, useMemo, useState } from 'react'
import { API_BASE_URL, apiRequest } from './services/api'
import ScorerPage from './ScorerPage.jsx'
import VerificationPage from './VerificationPage.jsx'
import DisputePage from './DisputePage.jsx'
import ResultPage from './ResultPage.jsx'
import './App.css'

const NAV_ITEMS = [
  ['overview', 'Overview'],
  ['tournaments', 'Tournaments'],
  ['create', 'Create tournament'],
  ['team', 'Teams'],
  ['scoring', 'Scoring'],
  ['verify', 'Verify scores'],
  ['dispute', 'Disputes'],
  ['result', 'Match results'],
]

function dateLabel(value) {
  if (!value) return 'â€”'
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

function Loading({ label = 'Loadingâ€¦' }) {
  return <div className="loading-state"><span className="spinner" />{label}</div>
}

function App() {
  const [page, setPage] = useState('overview')
  const [currentUser, setCurrentUser] = useState(null)
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
    const token = localStorage.getItem('access_token')
    if (!token) return

    let cancelled = false

    apiRequest('/auth/me')
      .then((user) => {
        if (!cancelled) setCurrentUser(user)
      })
      .catch(() => {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        if (!cancelled) setCurrentUser(null)
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
      setCurrentUser(user)
      setPage('overview')
    } catch (error) {
      if (mode === 'login') {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
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
      if (localStorage.getItem('access_token')) {
        await apiRequest('/auth/logout', { method: 'POST' })
      }
    } catch (error) {
      console.warn('Server logout failed:', error.message)
    } finally {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      setCurrentUser(null)
      setPage('login')
      setAuthSuccess('You have been signed out.')
    }
  }

  const visibleNavItems = NAV_ITEMS.filter(([id]) => {
    if (id === 'create') {
      return currentUser?.role === 'organiser'
    }

    if (id === 'team') {
      return ['organiser', 'player'].includes(currentUser?.role)
    }

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
  const paginatedTournaments = filteredTournaments.slice(
    (currentPage - 1) * 10,
    currentPage * 10,
  )

  const activeCount = useMemo(
    () => tournaments.filter((item) => String(item.status).toLowerCase() === 'active').length,
    [tournaments],
  )

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
                {currentUser.email} · {currentUser.role}
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
            <div className="page-heading"><div><p className="eyebrow">YOUR SPORTS HUB</p><h1>Manage the game.</h1><p className="muted">Create tournaments, follow standings, and keep your competition organized.</p></div><button className="button button-primary" onClick={() => { resetForm(); setPage('create') }}>ï¼‹ Create tournament</button></div>
            <div className="hero-panel"><div><p className="eyebrow">MATCHGRID WORKSPACE</p><h2>Every competition.<br />One clear view.</h2><p>Keep tournament information and team performance in one place.</p><button className="button button-on-dark" onClick={() => setPage('tournaments')}>Browse tournaments <span>â†’</span></button></div><div className="hero-orbit" aria-hidden="true"><span>MG</span><i /><b /></div></div>
            <div className="stats-grid">
              <article className="stat-card"><span className="stat-icon">â–¦</span><p>Total tournaments</p><strong>{tournaments.length}</strong><small>Returned by the API</small></article>
              <article className="stat-card"><span className="stat-icon green">â†—</span><p>Active tournaments</p><strong>{activeCount}</strong><small>Based on current status</small></article>
              <article className="stat-card"><span className="stat-icon violet">â—Ž</span><p>Competition formats</p><strong>{new Set(tournaments.map((item) => item.format).filter(Boolean)).size}</strong><small>Formats in your list</small></article>
            </div>
            <div className="section-title"><div><h2>Recent tournaments</h2><p className="muted">Latest items returned by the tournament API.</p></div><button className="button button-secondary" onClick={() => setPage('tournaments')}>View all</button></div>
            {listError && <ErrorNotice>{listError}</ErrorNotice>}
            {listLoading ? <Loading label="Loading tournamentsâ€¦" /> : tournaments.length ? <TournamentTable items={tournaments.slice(0, 5)} onOpen={openTournament} onEdit={beginEdit} canManage={currentUser?.role === 'organiser'} /> : <EmptyState title="No tournaments to show" text="Create a tournament or check back when the API has data." action={() => { resetForm(); setPage('create') }} />}
          </>}

          {page === 'tournaments' && <>
            <div className="page-heading"><div><p className="eyebrow">COMPETITIONS</p><h1>Tournaments</h1><p className="muted">Browse tournament details and current standings.</p></div><button className="button button-primary" onClick={() => { resetForm(); setPage('create') }}>ï¼‹ Create tournament</button></div>
            <div className="filter-row">
              <label>
                Search tournaments
                <input
                  type="search"
                  value={searchTerm}
                  placeholder="Search by name or IDâ€¦"
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
            {listLoading ? <Loading label="Loading tournamentsâ€¦" /> : filteredTournaments.length ? (
              <>
                <p className="helper-text">
                  Showing {(currentPage - 1) * 10 + 1}â€“{Math.min(currentPage * 10, filteredTournaments.length)} of {filteredTournaments.length} tournaments
                </p>
                <TournamentTable items={paginatedTournaments} onOpen={openTournament} onEdit={beginEdit} canManage={currentUser?.role === 'organiser'} />
                <div className="pagination-row">
                  <button
                    className="button button-secondary"
                    onClick={() => setCurrentPage((value) => Math.max(1, value - 1))}
                    disabled={currentPage === 1}
                  >
                    â† Previous
                  </button>
                  <span>Page {currentPage} of {totalPages}</span>
                  <button
                    className="button button-secondary"
                    onClick={() => setCurrentPage((value) => Math.min(totalPages, value + 1))}
                    disabled={currentPage >= totalPages}
                  >
                    Next â†’
                  </button>
                </div>
              </>
            ) : <EmptyState title="No matching tournaments" text="Try another search or status filter, or create a tournament." action={() => { resetForm(); setPage('create') }} />}
          </>}

          {page === 'details' && <>
            <div className="page-heading"><div><p className="eyebrow">COMPETITION OVERVIEW</p><h1>Tournament details</h1><p className="muted">Tournament information and standings provided by the API.</p></div><button className="button button-secondary" onClick={() => setPage('tournaments')}>â† Back to list</button></div>
            {detailsLoading && <Loading label="Loading tournament detailsâ€¦" />}
            <ErrorNotice>{detailsError}</ErrorNotice>
            {selectedTournament && <><div className="detail-card"><div className="detail-heading"><div><span className="eyebrow">TOURNAMENT #{selectedTournament.id}</span><h2>{selectedTournament.name}</h2><p>{selectedTournament.description || 'No description provided.'}</p></div><span className={statusClass(selectedTournament.status)}>{selectedTournament.status || 'Unknown'}</span></div><div className="detail-meta"><Meta label="Format" value={selectedTournament.format} /><Meta label="Starts" value={dateLabel(selectedTournament.start_date)} /><Meta label="Ends" value={dateLabel(selectedTournament.end_date)} /><Meta label="Organizer ID" value={selectedTournament.organizer_id} /></div><div className="detail-actions">{currentUser?.role === 'organiser' && <button className="button button-primary" onClick={() => beginEdit(selectedTournament)}>Edit tournament</button>}<button className="button button-secondary" onClick={() => openTournament(selectedTournament.id)}>Refresh details</button></div></div><div className="section-title"><div><h2>Fixtures</h2><p className="muted">Scheduled matches returned by the fixtures API.</p></div><button className="button button-secondary" onClick={() => openTournament(selectedTournament.id)} disabled={detailsLoading || fixturesLoading}>Refresh fixtures</button></div>{fixturesLoading ? <Loading label="Loading fixturesâ€¦" /> : <><ErrorNotice>{fixturesError}</ErrorNotice>{fixtures.length ? <div className="table-wrap"><table><thead><tr><th>Match</th><th>Team A ID</th><th>Team B ID</th><th>Venue ID</th><th>Scheduled at</th><th>Status</th></tr></thead><tbody>{fixtures.map((fixture) => <tr key={fixture.id}><td><strong>#{fixture.match_number}</strong><small className="cell-subtitle">Fixture ID: {fixture.id}</small></td><td>{fixture.team_a_id ?? 'TBD'}</td><td>{fixture.team_b_id ?? 'TBD'}</td><td>{fixture.venue_id ?? 'â€”'}</td><td>{dateLabel(fixture.scheduled_at)}</td><td><span className={statusClass(fixture.status)}>{fixture.status || 'Unknown'}</span></td></tr>)}</tbody></table></div> : !fixturesError ? <EmptyState title="No fixtures available" text="No fixtures have been returned for this tournament yet." /> : null}</>}<div className="section-title"><div><h2>Standings</h2><p className="muted">Calculated rankings returned by the standings endpoint.</p></div></div>{standings.length ? <div className="table-wrap"><table><thead><tr><th>Rank</th><th>Team</th><th>Played</th><th>W</th><th>D</th><th>L</th><th>Score diff.</th><th>Points</th></tr></thead><tbody>{standings.map((row) => <tr key={row.team_id}><td><span className="rank">#{row.rank}</span></td><td><strong>{row.team_name}</strong></td><td>{row.played}</td><td>{row.wins}</td><td>{row.draws}</td><td>{row.losses}</td><td>{row.score_difference}</td><td><strong>{row.points}</strong></td></tr>)}</tbody></table></div> : <EmptyState title="No standings available" text="The API returned no standings for this tournament yet." />}</>}
            {!detailsLoading && !selectedTournament && !detailsError && <IdLookup onSubmit={openTournament} />}
          </>}

          {page === 'create' && currentUser?.role === 'organiser' && <>
            <div className="page-heading"><div><p className="eyebrow">TOURNAMENT SETUP</p><h1>{editingId ? 'Edit tournament' : 'Create a tournament'}</h1><p className="muted">{editingId ? 'Update tournament details. The backend checks organizer ownership.' : 'Set the essentials before your competition begins.'}</p></div><button className="button button-secondary" onClick={() => { resetForm(); setPage('tournaments') }}>Cancel</button></div>
            <form className="form-card" onSubmit={submitTournament}>
              <div className="form-section-heading"><span className="step-number">01</span><div><h2>Basic information</h2><p>Give your tournament a clear identity.</p></div></div>
              <div className="field"><label htmlFor="tournament-name">Tournament name <span>*</span></label><input id="tournament-name" value={form.name} minLength={3} maxLength={150} required placeholder="e.g. Spring Championship" onChange={(event) => setForm({ ...form, name: event.target.value })} /><small>3â€“150 characters</small></div>
              <div className="field"><label htmlFor="tournament-description">Description</label><textarea id="tournament-description" rows="3" value={form.description} placeholder="What should participants know?" onChange={(event) => setForm({ ...form, description: event.target.value })} /></div>
              <div className="form-grid"><div className="field"><label htmlFor="tournament-format">Tournament format <span>*</span></label><select id="tournament-format" value={form.format} required onChange={(event) => setForm({ ...form, format: event.target.value })}><option value="round_robin">Round robin</option><option value="single_elimination">Single elimination</option><option value="double_elimination">Double elimination</option></select></div><div className="field"><label htmlFor="number-teams">Number of teams</label><input id="number-teams" type="number" min="2" max="256" value={form.number_of_teams} required onChange={(event) => setForm({ ...form, number_of_teams: event.target.value })} /><small>At least 2 teams</small></div></div>
              <div className="form-section-heading second"><span className="step-number">02</span><div><h2>Schedule</h2><p>Choose the start and end of the competition.</p></div></div>
              <div className="form-grid"><div className="field"><label htmlFor="start-date">Start date and time <span>*</span></label><input id="start-date" type="datetime-local" value={form.start_date} required onChange={(event) => setForm({ ...form, start_date: event.target.value })} /></div><div className="field"><label htmlFor="end-date">End date and time <span>*</span></label><input id="end-date" type="datetime-local" value={form.end_date} min={form.start_date || undefined} required onChange={(event) => setForm({ ...form, end_date: event.target.value })} /></div></div>
              <ErrorNotice>{formError}</ErrorNotice><SuccessNotice>{formSuccess}</SuccessNotice>
              <div className="form-footer"><p><span>*</span> Required fields. Sign in as an organiser to submit.</p><button className="button button-primary" type="submit" disabled={formLoading}>{formLoading ? 'Savingâ€¦' : editingId ? 'Save changes â†’' : 'Create tournament â†’'}</button></div>
            </form>
          </>}

          {page === 'scoring' && <ScorerPage />}
          {page === 'verify' && <VerificationPage />}
          {page === 'dispute' && <DisputePage />}
          {page === 'result' && <ResultPage />}
      {page === 'team' && <>
            <div className="page-heading"><div><p className="eyebrow">TEAM DIRECTORY</p><h1>Team lookup</h1><p className="muted">Look up an existing team using its numeric ID.</p></div></div>
            <form className="lookup-card" onSubmit={loadTeam}><div className="field"><label htmlFor="team-id">Team ID</label><input id="team-id" inputMode="numeric" pattern="[1-9][0-9]*" value={teamId} onChange={(event) => setTeamId(event.target.value)} placeholder="e.g. 12" required /></div><button className="button button-primary" type="submit" disabled={teamLoading}>{teamLoading ? 'Searchingâ€¦' : 'Find team'}</button></form>
            <ErrorNotice>{teamError}</ErrorNotice>
            {teamLoading && <Loading label="Loading teamâ€¦" />}
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
                <button className="button button-primary" type="submit" disabled={rosterLoading}>{rosterLoading ? 'Updatingâ€¦' : 'Add player'}</button>
              </form>
              <ErrorNotice>{rosterError}</ErrorNotice>
              <SuccessNotice>{rosterSuccess}</SuccessNotice>
              {rosterLoading && <Loading label="Updating team rosterâ€¦" />}
              {Array.isArray(team.players) && team.players.length > 0 ? (
                <div className="table-wrap">
                  <table>
                    <thead><tr><th>Player</th><th>Player ID</th><th>User ID</th><th>Status</th><th>Actions</th></tr></thead>
                    <tbody>
                      {team.players.map((rosterPlayer) => (
                        <tr key={rosterPlayer.id}>
                          <td><strong>{[rosterPlayer.first_name, rosterPlayer.last_name].filter(Boolean).join(' ') || `Player #${rosterPlayer.id}`}</strong></td>
                          <td>{rosterPlayer.id}</td>
                          <td>{rosterPlayer.user_id ?? 'â€”'}</td>
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
              <button className="button button-primary" type="submit" disabled={playerLoading}>{playerLoading ? 'Searchingâ€¦' : 'Find player'}</button>
            </form>
            <ErrorNotice>{playerError}</ErrorNotice>
            {playerLoading && <Loading label="Loading player profileâ€¦" />}
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

          <footer className="footer"><span>Â© MatchGrid 2026</span><span>Sports management, made clearer.</span><span className="footer-api">{API_BASE_URL || 'API URL missing'}</span></footer>
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
              <td>{item.format || '—'}</td>
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
  return <div className="meta-item"><span>{label}</span><strong>{value ?? 'â€”'}</strong></div>
}

function EmptyState({ title, text, action }) {
  return <div className="empty-state"><span className="empty-icon">â–¦</span><h3>{title}</h3><p>{text}</p>{action && <button className="button button-secondary" onClick={action}>Create tournament</button>}</div>
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
          {loading ? 'Creating teamâ€¦' : 'Create team'}
        </button>
      </div>
    </form>
  )
}

function AuthPanel({ mode, loading, error, success, onSubmit, onSwitch }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState('player')

  const isRegister = mode === 'register'

  return (
    <div className="auth-page">
      <form
        className="auth-card"
        onSubmit={(event) =>
          onSubmit(event, mode, { email, password, role })
        }
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
          <input
            id="auth-password"
            type="password"
            autoComplete={isRegister ? 'new-password' : 'current-password'}
            minLength={isRegister ? 8 : undefined}
            maxLength={72}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder={isRegister ? 'At least 8 characters' : 'Enter your password'}
            required
          />
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
          onClick={() => onSwitch('overview')}
        >
          Back to dashboard
        </button>
      </form>
    </div>
  )
}

export default App




