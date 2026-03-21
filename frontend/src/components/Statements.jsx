import React, { useState, useEffect } from 'react'
import { getStatements, deleteStatement } from '../api.js'
import styles from './Statements.module.css'

const MONTHS = [
  '', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
]

function fmtDate(d) {
  return new Date(d).toLocaleDateString('en-GB', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit'
  })
}

export default function Statements({ onDeleted }) {
  const [statements, setStatements] = useState([])
  const [loading, setLoading] = useState(true)
  const [deleting, setDeleting] = useState(null)
  const [error, setError] = useState(null)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await getStatements()
      setStatements(res.data)
    } catch (e) {
      setError('Failed to load statements')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const handleDelete = async (stmt) => {
    if (!confirm(
      `Delete statement "${stmt.filename}"?\n\nThis will permanently delete all ${stmt.transactions_inserted} transaction(s) linked to this statement. This cannot be undone.`
    )) return
    setDeleting(stmt.id)
    setError(null)
    try {
      await deleteStatement(stmt.id)
      setStatements(prev => prev.filter(s => s.id !== stmt.id))
      onDeleted?.()
    } catch (e) {
      setError('Failed to delete statement')
    } finally {
      setDeleting(null)
    }
  }

  return (
    <div className={styles.container}>
      <div className={styles.pageHeader}>
        <h2 className={styles.title}>Uploaded Statements</h2>
        <p className={styles.subtitle}>
          Each row represents one uploaded PDF. Deleting a statement removes all its transactions from the dashboard.
        </p>
      </div>

      {error && <div className={styles.error}>{error}</div>}

      {loading && <div className={styles.skeleton}><div className={styles.shimmer} /></div>}

      {!loading && statements.length === 0 && (
        <div className={styles.empty}>
          <span className={styles.emptyIcon}>📂</span>
          <p>No statements uploaded yet.</p>
          <p className={styles.emptyHint}>Go to <strong>Upload Statements</strong> to get started.</p>
        </div>
      )}

      {!loading && statements.length > 0 && (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>File</th>
                <th>Bank</th>
                <th>Period</th>
                <th className={styles.center}>Transactions</th>
                <th className={styles.center}>Ignored</th>
                <th>Uploaded</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {statements.map(stmt => (
                <tr key={stmt.id} className={styles.row}>
                  <td className={styles.filename}>
                    <span className={styles.fileIcon}>📋</span>
                    <span title={stmt.filename}>{stmt.filename}</span>
                  </td>
                  <td className={styles.bank}>{stmt.bank_name || '—'}</td>
                  <td className={styles.period}>
                    {stmt.month && stmt.year
                      ? `${MONTHS[stmt.month]} ${stmt.year}`
                      : '—'}
                  </td>
                  <td className={styles.center}>
                    <span className={styles.countBadge}>{stmt.transactions_inserted}</span>
                  </td>
                  <td className={styles.center}>
                    <span className={styles.ignoredBadge}>{stmt.transactions_ignored}</span>
                  </td>
                  <td className={styles.uploaded}>{fmtDate(stmt.uploaded_at)}</td>
                  <td className={styles.actions}>
                    <button
                      className={styles.deleteBtn}
                      onClick={() => handleDelete(stmt)}
                      disabled={deleting === stmt.id}
                      title="Delete statement and all its transactions"
                    >
                      {deleting === stmt.id ? '⏳' : '🗑 Delete'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
