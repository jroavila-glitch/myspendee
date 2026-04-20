import React, { useState, useEffect, useCallback } from 'react'
import { getTransactions } from '../api.js'
import AddTransactionModal from './AddTransactionModal.jsx'
import styles from './Rent.module.css'

const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
]

const RENT_CATEGORY = 'Rent'

function fmt(amount) {
  return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(amount)
}

/** Build a list of {year, month} entries from 18 months ago to now */
function buildMonthRange() {
  const now = new Date()
  const result = []
  for (let i = 17; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1)
    result.push({ year: d.getFullYear(), month: d.getMonth() + 1 })
  }
  return result
}

export default function Rent() {
  const [transactions, setTransactions] = useState([])
  const [loading, setLoading] = useState(true)
  const [expandedMonth, setExpandedMonth] = useState(null)
  const [showAddModal, setShowAddModal] = useState(false)
  const [editingTx, setEditingTx] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await getTransactions({ category: RENT_CATEGORY, limit: 500 })
      setTransactions(res.data)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const monthRange = buildMonthRange()

  // Group transactions by year-month key
  const byMonth = {}
  transactions.forEach(tx => {
    const key = `${tx.year}-${String(tx.month).padStart(2, '0')}`
    if (!byMonth[key]) byMonth[key] = []
    byMonth[key].push(tx)
  })

  // Summary stats for the current calendar year
  const currentYear = new Date().getFullYear()
  const thisYearTxs = transactions.filter(t => t.year === currentYear)
  const totalThisYear = thisYearTxs.reduce((s, t) => s + parseFloat(t.amount_mxn), 0)
  const monthsPaidThisYear = new Set(thisYearTxs.map(t => t.month)).size
  const monthlyAvg = monthsPaidThisYear > 0 ? totalThisYear / monthsPaidThisYear : 0

  const currentMonth = new Date().getMonth() + 1
  const currentMonthKey = `${currentYear}-${String(currentMonth).padStart(2, '0')}`
  const currentMonthStatus = byMonth[currentMonthKey]?.length > 0 ? 'paid' : 'unpaid'

  const toggleMonth = (key) => setExpandedMonth(prev => prev === key ? null : key)

  const handleAdd = () => {
    setShowAddModal(false)
    load()
  }

  const handleEditSave = () => {
    setEditingTx(null)
    load()
  }

  return (
    <div className={styles.rent}>
      <div className={styles.topBar}>
        <div>
          <h2 className={styles.pageTitle}>🏠 Rent</h2>
          <p className={styles.pageSubtitle}>Monthly rent payments overview</p>
        </div>
        <button className={styles.addBtn} onClick={() => setShowAddModal(true)}>
          + Log Rent Payment
        </button>
      </div>

      {loading && <div className={styles.loadingBar} />}

      {/* Summary cards */}
      <div className={styles.summaryGrid}>
        <div className={styles.card}>
          <span className={styles.cardLabel}>Paid in {currentYear}</span>
          <span className={styles.cardValue}>{fmt(totalThisYear)}</span>
        </div>
        <div className={styles.card}>
          <span className={styles.cardLabel}>Monthly avg ({currentYear})</span>
          <span className={styles.cardValue}>{fmt(monthlyAvg)}</span>
        </div>
        <div className={styles.card}>
          <span className={styles.cardLabel}>Months paid ({currentYear})</span>
          <span className={styles.cardValue}>{monthsPaidThisYear} / {currentMonth}</span>
        </div>
        <div className={`${styles.card} ${currentMonthStatus === 'paid' ? styles.cardGreen : styles.cardRed}`}>
          <span className={styles.cardLabel}>This month</span>
          <span className={styles.cardValue}>{currentMonthStatus === 'paid' ? '✅ Paid' : '⚠️ Not logged'}</span>
        </div>
      </div>

      {/* Monthly table */}
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Month</th>
              <th>Status</th>
              <th className={styles.right}>Amount Paid</th>
              <th className={styles.right}># Payments</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {[...monthRange].reverse().map(({ year, month }) => {
              const key = `${year}-${String(month).padStart(2, '0')}`
              const txs = byMonth[key] || []
              const total = txs.reduce((s, t) => s + parseFloat(t.amount_mxn), 0)
              const paid = txs.length > 0
              const isExpanded = expandedMonth === key
              const isFuture = year > currentYear || (year === currentYear && month > currentMonth)

              return (
                <React.Fragment key={key}>
                  <tr
                    className={`${styles.row} ${paid ? styles.rowPaid : isFuture ? styles.rowFuture : styles.rowUnpaid}`}
                    onClick={() => paid && toggleMonth(key)}
                    style={{ cursor: paid ? 'pointer' : 'default' }}
                  >
                    <td className={styles.monthCell}>
                      <span className={styles.monthName}>{MONTHS[month - 1]}</span>
                      <span className={styles.yearTag}>{year}</span>
                    </td>
                    <td>
                      {isFuture ? (
                        <span className={styles.badgeFuture}>—</span>
                      ) : paid ? (
                        <span className={styles.badgePaid}>Paid</span>
                      ) : (
                        <span className={styles.badgeUnpaid}>Unpaid</span>
                      )}
                    </td>
                    <td className={styles.right}>
                      {paid ? <strong>{fmt(total)}</strong> : <span className={styles.dim}>—</span>}
                    </td>
                    <td className={styles.right}>
                      {paid ? txs.length : <span className={styles.dim}>—</span>}
                    </td>
                    <td className={styles.chevronCell}>
                      {paid && <span className={styles.chevron}>{isExpanded ? '▲' : '▼'}</span>}
                    </td>
                  </tr>

                  {isExpanded && txs.map(tx => (
                    <tr key={tx.id} className={styles.detailRow}>
                      <td colSpan={5}>
                        <div className={styles.detailCard}>
                          <div className={styles.detailLeft}>
                            <span className={styles.detailDate}>{tx.date}</span>
                            <span className={styles.detailDesc}>{tx.description}</span>
                            {tx.notes && <span className={styles.detailNotes}>{tx.notes}</span>}
                          </div>
                          <div className={styles.detailRight}>
                            <span className={styles.detailAmount}>{fmt(tx.amount_mxn)}</span>
                            <span className={styles.detailBank}>{tx.bank_name}</span>
                            <button
                              className={styles.editBtn}
                              onClick={(e) => { e.stopPropagation(); setEditingTx(tx) }}
                            >
                              Edit
                            </button>
                          </div>
                        </div>
                      </td>
                    </tr>
                  ))}
                </React.Fragment>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Add payment modal — pre-fill category as Rent */}
      {showAddModal && (
        <AddTransactionModal
          onClose={() => setShowAddModal(false)}
          onSave={handleAdd}
          defaultCategory={RENT_CATEGORY}
          defaultType="expense"
        />
      )}

      {editingTx && (
        <AddTransactionModal
          transaction={editingTx}
          onClose={() => setEditingTx(null)}
          onSave={handleEditSave}
        />
      )}
    </div>
  )
}
