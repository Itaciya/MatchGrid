import { useState } from 'react'
import { createDispute } from './services/resultsApi'

const CATEGORIES = ['Incorrect score', 'Wrong winner', 'Rule violation', 'Other']
const MAX_REASON = 5000

export default function DisputePage() {
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
    if (!/^[1-9]\d*$/.test(matchId)) return setError('Enter a valid match ID.')
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
    <section>
      <h2>Submit a dispute</h2>
      <p style={{ fontSize: 13, opacity: 0.7 }}>
        Players can dispute the result of a match they took part in.
      </p>
      <form onSubmit={onSubmit} style={{ display: 'grid', gap: 12, maxWidth: 480 }}>
        <label>Match ID
          <input inputMode="numeric" value={matchId} onChange={(e) => setMatchId(e.target.value)} required />
        </label>
        <label>Reason
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </label>
        <label>Description
          <textarea rows="5" value={description} onChange={(e) => setDescription(e.target.value)} required />
        </label>
        <button type="submit" disabled={loading}>{loading ? 'Submitting...' : 'Submit dispute'}</button>
      </form>
      {error && <div className="notice notice-error" role="alert">{error}</div>}
      {created && (
        <div className="notice notice-success" role="status">
          Dispute #{created.id} submitted for match {created.match_id} (status: {created.status}).
        </div>
      )}
    </section>
  )
}