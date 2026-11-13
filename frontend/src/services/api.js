const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
).replace(/\/+$/, '')

function getAccessToken() {
  return (
    localStorage.getItem('access_token') ||
    localStorage.getItem('accessToken') ||
    localStorage.getItem('token') ||
    ''
  )
}

/**
 * Error thrown by apiRequest. `message` is always a human-readable sentence
 * that is safe to show to the user. The raw details stay available for
 * debugging and for callers that need to branch on them.
 */
class ApiError extends Error {
  constructor(message, { status = 0, serverMessage = '', endpoint = '', method = 'GET' } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.serverMessage = serverMessage
    this.endpoint = endpoint
    this.method = method
  }
}

// Backend messages that are technically correct but not friendly.
// First match wins. `$1`, `$2` refer to regex groups.
const SERVER_MESSAGE_REWRITES = [
  [
    /cannot transition from status '(\w+)' to 'live'/i,
    (m) => m[1] === 'live'
      ? 'This match is already live.'
      : `A match that is ${m[1]} cannot be started.`,
  ],
  [
    /cannot transition from status '(\w+)' to 'completed'/i,
    (m) => m[1] === 'completed'
      ? 'This match has already ended.'
      : `Only a live match can be ended (this match is ${m[1]}).`,
  ],
  [
    /cannot transition from status '(\w+)' to '(\w+)'/i,
    (m) => `This match is ${m[1]}, so it cannot be changed to ${m[2]}.`,
  ],
  [/both teams must be assigned/i, () => 'Both teams must be assigned before this can be done.'],
  [/invalid or expired token/i, () => 'Your session has expired. Please sign in again.'],
  [/account is inactive/i, () => 'Your account is inactive. Please contact the organiser or support.'],
  [/you are not assigned to this match/i, () => 'You are not assigned to this match, so you cannot manage it.'],
  [/you do not own this tournament/i, () => 'This tournament belongs to another organiser, so you cannot change it.'],
  [/your role does not permit this action/i, () => 'Your account type is not allowed to do this.'],
  [/player profile not found/i, () => 'Your account does not have a player profile yet. Please complete your player profile first.'],
  [/only player registration is allowed/i, () => 'This tournament accepts individual registrations only.'],
  [/only team registration is allowed/i, () => 'This tournament accepts team registrations only.'],
  [/only the team captain can register the team/i, () => 'Only the team captain can register this team.'],
  [/already registered for this tournament/i, () => 'You are already registered for this tournament.'],
  [/registration has not opened yet/i, () => 'Registration has not opened yet. Please check the opening date.'],
  [/registration deadline has passed/i, () => 'The registration deadline has passed.'],
  [/only active teams can register/i, () => 'Your team is not active. Please contact the organiser.'],
  [/only active players can register/i, () => 'Your player profile is not active. Please contact the organiser.'],
]

// What to say when the server gave no usable message at all.
const STATUS_FALLBACKS = {
  400: 'The request was not valid. Please check what you entered and try again.',
  401: 'Your session has expired or you are not signed in. Please sign in again.',
  403: 'You do not have permission to do this.',
  404: 'We could not find what you were looking for. It may have been removed or the link may be wrong.',
  405: 'This action is not supported.',
  408: 'The request took too long. Please try again.',
  409: 'This action conflicts with the current state. Refresh the page and try again.',
  413: 'The data you sent is too large.',
  422: 'Some of the information you entered is not valid. Please review it and try again.',
  429: 'Too many requests. Please wait a moment and try again.',
  500: 'Something went wrong on our side. Please try again in a moment.',
  502: 'The server is temporarily unavailable. Please try again shortly.',
  503: 'The service is temporarily unavailable. Please try again shortly.',
  504: 'The server took too long to respond. Please try again.',
}

// Used only for generic 404s, so the user learns *what* was not found.
const NOT_FOUND_BY_ENDPOINT = [
  [/\/result(\/|$|\?)/, 'No published result exists for this match yet.'],
  [/\/score(\/review)?(\?|$)/, 'No score has been submitted for this match yet.'],
  [/\/matches\/tournaments\/\d+\/fixtures/, 'No fixtures were found for this tournament.'],
  [/\/official-assignments\/tournaments\/\d+\/available-scorers/, 'We could not load the available scorers. Please refresh and try again.'],
  [/\/official-assignments\/tournaments\/\d+\/scorers/, 'We could not assign the scorer. Please check your access and try again.'],
  [/\/tournaments\/\d+/, 'This tournament could not be found.'],
  [/\/matches\/\d+/, 'This match could not be found.'],
  [/\/teams?\//, 'This team could not be found.'],
  [/\/disputes?\//, 'This dispute could not be found.'],
]

function formatValidationDetails(details) {
  if (!Array.isArray(details) || details.length === 0) return ''
  return details
    .map((item) => {
      const field = Array.isArray(item.loc)
        ? item.loc.filter((part) => part !== 'body' && part !== 'query' && part !== 'path').join(' > ')
        : ''
      const text = item.message || item.msg || 'is invalid'
      return field ? `${field}: ${text}` : text
    })
    .join('; ')
}

// Pull a message out of any of the error shapes this API produces:
//   { success:false, error:{ message, details } }   (app handlers)
//   { detail: "..." | [{msg}] }                      (FastAPI defaults)
//   { message: "..." }  or plain text
function extractServerMessage(payload) {
  if (!payload) return ''
  if (typeof payload === 'string') {
    // Don't show raw HTML error pages from proxies.
    return /<\s*html/i.test(payload) ? '' : payload.trim().slice(0, 300)
  }

  const nested = payload.error
  if (nested && typeof nested === 'object') {
    const detailText = formatValidationDetails(nested.details)
    if (detailText) return detailText
    if (typeof nested.message === 'string') return nested.message
  }
  if (typeof nested === 'string') return nested

  const detail = payload.detail ?? payload.message
  if (Array.isArray(detail)) {
    return detail
      .map((item) => item?.msg || item?.message || '')
      .filter(Boolean)
      .join('; ')
  }
  return typeof detail === 'string' ? detail : ''
}

// Generic messages the backend sends that say nothing useful on their own.

function toFriendlyMessage({ status, serverMessage, endpoint }) {
  const trimmed = (serverMessage || '').trim()

  // Only explicitly reviewed messages are allowed through.
  if (trimmed) {
    for (const [pattern, rewrite] of SERVER_MESSAGE_REWRITES) {
      const match = trimmed.match(pattern)
      if (match) return rewrite(match)
    }
  }

  if (status === 404) {
    const hit = NOT_FOUND_BY_ENDPOINT.find(([pattern]) => pattern.test(endpoint))
    if (hit) return hit[1]
  }

  if (status === 403 && /not authenticated/i.test(trimmed)) {
    return STATUS_FALLBACKS[401]
  }

  if (STATUS_FALLBACKS[status]) return STATUS_FALLBACKS[status]
  if (status >= 500) return STATUS_FALLBACKS[500]
  if (status >= 400) return 'The request could not be completed. Please try again.'
  return 'Something unexpected happened. Please try again.'
}

async function apiRequest(endpoint, options = {}) {
  if (!API_BASE_URL) {
    throw new ApiError(
      'The app is not configured correctly (missing API address). Please contact support.',
      { endpoint }
    )
  }

  const method = (options.method || 'GET').toUpperCase()
  const token = getAccessToken()
  const isFormData = options.body instanceof FormData

  const headers = {
    ...(options.body && !isFormData
      ? { 'Content-Type': 'application/json' }
      : {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers || {}),
  }

  let response

  try {
    response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers,
    })
  } catch {
    throw new ApiError(
      'Could not reach the server. Check your internet connection and try again.',
      { endpoint, method }
    )
  }

  if (response.status === 204) return null

  const contentType = response.headers.get('content-type') || ''

  const payload = contentType.includes('application/json')
    ? await response.json().catch(() => null)
    : await response.text().catch(() => '')

  if (!response.ok) {
    const serverMessage = extractServerMessage(payload)

    throw new ApiError(
      toFriendlyMessage({ status: response.status, serverMessage, endpoint }),
      { status: response.status, serverMessage, endpoint, method }
    )
  }

  return payload
}

export { API_BASE_URL, ApiError, apiRequest }

