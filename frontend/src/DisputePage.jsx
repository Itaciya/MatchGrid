import { useState } from 'react'
import { createDispute } from './services/resultsApi'
import { MatchSelect, TournamentSelect } from './components/Pickers'

const CATEGORIES = ['Incorrect score', 'Wrong winner', 'Rule violation', 'Other']
const MAX_REASON = 5000

export default function DisputePage() {
  const [tournamentId, setTournamentId] = useState('')
  const [matchId, setMatchId] = useState('')
  const [category, setCategory] = useState(CATEGORIES[0])
  const [description, setDescription] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [created, setCreated] = useState(null)

  async function onSubmit(event) {
    event.preventDefault()
    setError('')
    setCreated(null)
    if (!matchId) return setError('Choose the match you want to dispute.')
    const text = description.trim()
    if (text.length < 10) return setError('Describe the problem in at least 10 characters.')
    const reason = `${category}: ${text}`
    if (reason.length > MAX_REASON) return setError(`Keep the description under ${MAX_REASON} characters.`)

    setLoading(true)
    try {
      setCreated(await createDispute(Number(matchId), reason))
      setDescription('')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">DISPUTES</p>
          <h1>Submit a dispute</h1>
          <p className="muted">Disagree with a result of a match your team played? Tell the organiser what went wrong.</p>
        </div>
      </div>

      <form className="form-card dispute-form" onSubmit={onSubmit}>
        <div className="form-grid">
          <TournamentSelect
            id="dispute-tournament"
            value={tournamentId}
            onChange={(value) => { setTournamentId(value); setMatchId('') }}
            filter={(tournament) => tournament.fixtures_published}
            emptyText="No tournaments have published fixtures yet."
          />
          <MatchSelect
            id="dispute-match"
            tournamentId={tournamentId}
            value={matchId}
            onChange={setMatchId}
            filter={(match) => match.status === 'completed'}
            emptyText="No ended matches to dispute in this tournament."
          />
        </div>
        <div className="field">
          <label htmlFor="dispute-category">Reason</label>
          <select id="dispute-category" value={category} onChange={(e) => setCategory(e.target.value)}>
            {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor="dispute-description">What happened?</label>
          <textarea id="dispute-description" rows="5" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="At least 10 characters" required />
        </div>
        <div className="form-footer">
          <p className="muted">The organiser reviews every dispute and you are notified of the decision.</p>
          <button className="button button-primary" type="submit" disabled={loading}>{loading ? 'Submitting...' : 'Submit dispute'}</button>
        </div>
      </form>
      {error && <div className="notice notice-error" role="alert">{error}</div>}
      {created && (
        <div className="notice notice-success" role="status">
          Your dispute was submitted and is now {String(created.status).replace('_', ' ')}.
        </div>
      )}
    </>
  )
}
