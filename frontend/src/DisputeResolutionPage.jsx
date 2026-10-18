import { useCallback, useEffect, useState } from 'react'
import { getOpenDisputes, resolveDispute, startDisputeReview } from './services/resultsApi'

const box = { border: '1px solid rgba(128,128,128,.4)', borderRadius: 8, padding: 16, marginBottom: 12 }
const isScore = (v) => /^\d+$/.test(String(v).trim())

function DisputeCard({ dispute, onChanged }) {
  const [decision, setDecision] = useState('resolved')
  const [resolution, setResolution] = useState('')
  const [a, setA] = useState('')
  const [b, setB] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function begin() {
    setBusy(true); setError('')
    try { onChanged(await startDisputeReview(dispute.id)) }
    catch (err) { setError(err.message) }
    finally { setBusy(false) }
  }

  async function submit(event) {
    event.preventDefault()
    setError('')
    if (resolution.trim().length < 3) return setError('Enter the resolution details.')
    const body = { decision, resolution: resolution.trim() }
    const hasA = a.trim() !== '', hasB = b.trim() !== ''
    if (decision === 'resolved' && (hasA || hasB)) {
      if (!(hasA && hasB) || !isScore(a) || !isScore(b)) {
        return setError('Corrected scores need whole numbers (0 or more) for both teams.')
      }
      body.corrected_team_a_score = Number(a)
      body.corrected_team_b_score = Number(b)
    }
    setBusy(true)
    try { onChanged(await resolveDispute(dispute.id, body)) }
    catch (err) { setError(err.message) }
    finally { setBusy(false) }
  }

  const m = dispute.match
  const open = dispute.status === 'pending' || dispute.status === 'under_review'

  return (
    <div style={box}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
        <strong>Dispute #{dispute.id} · Match {m ? m.match_number : dispute.match_id}</strong>
        <span className="status-pill">{dispute.status}</span>
      </div>
      {m && <div>{m.team_a_name} vs {m.team_b_name} <span style={{ opacity: 0.7 }}>({m.status})</span></div>}
      {dispute.result
        ? <div>Current score: <b>{dispute.result.team_a_score} - {dispute.result.team_b_score}</b> ({dispute.result.verification_status})</div>
        : <div style={{ opacity: 0.7 }}>No score on record.</div>}
      <p style={{ whiteSpace: 'pre-wrap' }}><b>Reason:</b> {dispute.reason}</p>

      {dispute.resolution && <p><b>Resolution:</b> {dispute.resolution}</p>}

      {dispute.status === 'pending' && (
        <button type="button" disabled={busy} onClick={begin}>{busy ? 'Working...' : 'Start review'}</button>
      )}

      {dispute.status === 'under_review' && (
        <form onSubmit={submit} style={{ display: 'grid', gap: 8, maxWidth: 480 }}>
          <label>Decision
            <select value={decision} onChange={(e) => setDecision(e.target.value)}>
              <option value="resolved">Approve dispute (resolved)</option>
              <option value="rejected">Reject dispute</option>
            </select>
          </label>
          <label>Resolution details
            <textarea rows="3" value={resolution} onChange={(e) => setResolution(e.target.value)} required />
          </label>
          {decision === 'resolved' && (
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <span>Corrected score (optional):</span>
              <input type="number" min="0" step="1" value={a} onChange={(e) => setA(e.target.value)} style={{ width: 70 }} aria-label="Corrected team A score" />
              <input type="number" min="0" step="1" value={b} onChange={(e) => setB(e.target.value)} style={{ width: 70 }} aria-label="Corrected team B score" />
            </div>
          )}
          <button type="submit" disabled={busy}>{busy ? 'Saving...' : 'Save decision'}</button>
        </form>
      )}

      {!open && <p style={{ opacity: 0.7 }}>This dispute is closed and cannot be reopened.</p>}
      {error && <div className="notice notice-error" role="alert">{error}</div>}
    </div>
  )
}

export default function DisputeResolutionPage() {
  const [disputes, setDisputes] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const rows = await getOpenDisputes()
      setDisputes(Array.isArray(rows) ? rows : [])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    getOpenDisputes()
      .then((rows) => { if (!cancelled) setDisputes(Array.isArray(rows) ? rows : []) })
      .catch((err) => { if (!cancelled) setError(err.message) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  function onChanged(updated) {
    setDisputes((list) => list.map((d) => (d.id === updated.id ? { ...d, ...updated } : d)))
  }

  return (
    <section>
      <h2>Dispute resolution</h2>
      <p style={{ fontSize: 13, opacity: 0.7 }}>
        Organisers review disputes for their own tournaments. Start a review, then approve or reject. The server enforces access and blocks reopening.
      </p>
      <button type="button" onClick={load} disabled={loading}>{loading ? 'Loading...' : 'Refresh'}</button>
      {error && <div className="notice notice-error" role="alert">{error}</div>}
      {!loading && !error && disputes.length === 0 && <p>No open disputes.</p>}
      <div style={{ marginTop: 12 }}>
        {disputes.map((d) => <DisputeCard key={d.id} dispute={d} onChanged={onChanged} />)}
      </div>
    </section>
  )
}