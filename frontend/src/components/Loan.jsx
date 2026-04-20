import React, { useState, useEffect, useCallback } from 'react'
import {
  getLoans, createLoan, updateLoan, deleteLoan,
  addLoanPayment, updateLoanPayment, deleteLoanPayment,
} from '../api.js'
import styles from './Loan.module.css'

const MONTHS = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
]

function fmt(amount) {
  return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(amount)
}

function today() {
  return new Date().toISOString().split('T')[0]
}

/** Build month-by-month timeline from start_date to today */
function buildTimeline(startDate, payments) {
  const start = new Date(startDate + 'T00:00:00')
  const now = new Date()
  const months = []

  let d = new Date(start.getFullYear(), start.getMonth(), 1)
  while (d <= now) {
    const y = d.getFullYear()
    const m = d.getMonth() + 1
    const monthPayments = payments.filter(p => {
      const pd = new Date(p.date + 'T00:00:00')
      return pd.getFullYear() === y && pd.getMonth() + 1 === m
    })
    const total = monthPayments.reduce((s, p) => s + parseFloat(p.amount), 0)
    months.push({ year: y, month: m, payments: monthPayments, total })
    d = new Date(d.getFullYear(), d.getMonth() + 1, 1)
  }
  return months.reverse()
}

// ── Loan Form Modal ───────────────────────────────────────────────────────────

function LoanFormModal({ loan, onClose, onSave }) {
  const isEdit = Boolean(loan)
  const [form, setForm] = useState({
    name: loan?.name ?? '',
    principal: loan?.principal != null ? String(loan.principal) : '',
    monthly_payment: loan?.monthly_payment != null ? String(loan.monthly_payment) : '',
    start_date: loan?.start_date ?? today(),
    notes: loan?.notes ?? '',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    if (!form.name || !form.principal || !form.start_date) {
      setError('Name, principal, and start date are required')
      return
    }
    setLoading(true)
    try {
      const payload = {
        name: form.name,
        principal: parseFloat(form.principal),
        monthly_payment: form.monthly_payment ? parseFloat(form.monthly_payment) : null,
        start_date: form.start_date,
        notes: form.notes || null,
      }
      if (isEdit) {
        await updateLoan(loan.id, payload)
      } else {
        await createLoan(payload)
      }
      onSave()
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save loan')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={styles.overlay} onClick={e => e.target === e.currentTarget && onClose()}>
      <div className={styles.modal}>
        <div className={styles.modalHeader}>
          <h2 className={styles.modalTitle}>{isEdit ? 'Edit Loan' : 'New Loan'}</h2>
          <button className={styles.modalClose} onClick={onClose}>✕</button>
        </div>
        <form onSubmit={handleSubmit} className={styles.modalForm}>
          <div className={styles.field}>
            <label className={styles.label}>Loan name *</label>
            <input className={styles.input} value={form.name}
              onChange={e => set('name', e.target.value)} placeholder='e.g. "Loan from Dad"' required />
          </div>
          <div className={styles.row2}>
            <div className={styles.field}>
              <label className={styles.label}>Total borrowed (MXN) *</label>
              <input className={styles.input} type="number" min="0" step="0.01"
                value={form.principal} onChange={e => set('principal', e.target.value)}
                placeholder="0.00" required />
            </div>
            <div className={styles.field}>
              <label className={styles.label}>Expected monthly payment</label>
              <input className={styles.input} type="number" min="0" step="0.01"
                value={form.monthly_payment} onChange={e => set('monthly_payment', e.target.value)}
                placeholder="0.00 (optional)" />
            </div>
          </div>
          <div className={styles.field}>
            <label className={styles.label}>Start date *</label>
            <input className={styles.input} type="date" value={form.start_date}
              onChange={e => set('start_date', e.target.value)} required />
          </div>
          <div className={styles.field}>
            <label className={styles.label}>Notes</label>
            <textarea className={styles.textarea} value={form.notes}
              onChange={e => set('notes', e.target.value)} rows={2}
              placeholder="Optional notes about this loan…" />
          </div>
          {error && <div className={styles.error}>{error}</div>}
          <div className={styles.modalActions}>
            <button type="button" className={styles.cancelBtn} onClick={onClose}>Cancel</button>
            <button type="submit" className={styles.saveBtn} disabled={loading}>
              {loading ? 'Saving…' : isEdit ? 'Save Changes' : 'Create Loan'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── Payment Form Modal ────────────────────────────────────────────────────────

function PaymentFormModal({ loanId, payment, onClose, onSave }) {
  const isEdit = Boolean(payment)
  const [form, setForm] = useState({
    date: payment?.date ?? today(),
    amount: payment?.amount != null ? String(Math.abs(parseFloat(payment.amount))) : '',
    notes: payment?.notes ?? '',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    if (!form.amount || parseFloat(form.amount) <= 0) {
      setError('Amount must be greater than zero')
      return
    }
    setLoading(true)
    try {
      const payload = {
        date: form.date,
        amount: parseFloat(form.amount),
        notes: form.notes || null,
      }
      if (isEdit) {
        await updateLoanPayment(loanId, payment.id, payload)
      } else {
        await addLoanPayment(loanId, payload)
      }
      onSave()
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save payment')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={styles.overlay} onClick={e => e.target === e.currentTarget && onClose()}>
      <div className={styles.modal}>
        <div className={styles.modalHeader}>
          <h2 className={styles.modalTitle}>{isEdit ? 'Edit Payment' : 'Log Payment'}</h2>
          <button className={styles.modalClose} onClick={onClose}>✕</button>
        </div>
        <form onSubmit={handleSubmit} className={styles.modalForm}>
          <div className={styles.row2}>
            <div className={styles.field}>
              <label className={styles.label}>Date *</label>
              <input className={styles.input} type="date" value={form.date}
                onChange={e => set('date', e.target.value)} required />
            </div>
            <div className={styles.field}>
              <label className={styles.label}>Amount paid (MXN) *</label>
              <input className={styles.input} type="number" min="0.01" step="0.01"
                value={form.amount} onChange={e => set('amount', e.target.value)}
                placeholder="0.00" required />
            </div>
          </div>
          <div className={styles.field}>
            <label className={styles.label}>Notes</label>
            <textarea className={styles.textarea} value={form.notes}
              onChange={e => set('notes', e.target.value)} rows={2}
              placeholder="e.g. Transferred via SPEI…" />
          </div>
          {error && <div className={styles.error}>{error}</div>}
          <div className={styles.modalActions}>
            <button type="button" className={styles.cancelBtn} onClick={onClose}>Cancel</button>
            <button type="submit" className={styles.saveBtn} disabled={loading}>
              {loading ? 'Saving…' : isEdit ? 'Save Changes' : 'Log Payment'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── Main Loan component ───────────────────────────────────────────────────────

export default function Loan() {
  const [loans, setLoans] = useState([])
  const [selectedLoanId, setSelectedLoanId] = useState(null)
  const [loading, setLoading] = useState(true)

  // Modals
  const [showLoanForm, setShowLoanForm] = useState(false)
  const [editingLoan, setEditingLoan] = useState(null)
  const [showPaymentForm, setShowPaymentForm] = useState(false)
  const [editingPayment, setEditingPayment] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await getLoans()
      setLoans(res.data)
      // Auto-select first loan if none selected
      if (res.data.length > 0 && !selectedLoanId) {
        setSelectedLoanId(res.data[0].id)
      }
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [selectedLoanId])

  useEffect(() => { load() }, [load])

  const selectedLoan = loans.find(l => l.id === selectedLoanId) ?? null

  // Derived stats
  const payments = selectedLoan?.payments ?? []
  const totalPaid = payments.reduce((s, p) => s + parseFloat(p.amount), 0)
  const balance = selectedLoan ? parseFloat(selectedLoan.principal) - totalPaid : 0
  const timeline = selectedLoan ? buildTimeline(selectedLoan.start_date, payments) : []

  const handleLoanSave = async () => {
    setShowLoanForm(false)
    setEditingLoan(null)
    // Reload and select newly created loan if it's the first
    const res = await getLoans()
    setLoans(res.data)
    if (res.data.length > 0 && !selectedLoanId) {
      setSelectedLoanId(res.data[0].id)
    }
  }

  const handlePaymentSave = async () => {
    setShowPaymentForm(false)
    setEditingPayment(null)
    const res = await getLoans()
    setLoans(res.data)
  }

  const handleDeleteLoan = async (loanId) => {
    if (!window.confirm('Delete this loan and all its payment history?')) return
    try {
      await deleteLoan(loanId)
      setSelectedLoanId(null)
      load()
    } catch (e) { console.error(e) }
  }

  const handleDeletePayment = async (paymentId) => {
    if (!window.confirm('Delete this payment record?')) return
    try {
      await deleteLoanPayment(selectedLoanId, paymentId)
      const res = await getLoans()
      setLoans(res.data)
    } catch (e) { console.error(e) }
  }

  // ── Empty state ──────────────────────────────────────────────────────────────
  if (!loading && loans.length === 0) {
    return (
      <div className={styles.loan}>
        <div className={styles.topBar}>
          <div>
            <h2 className={styles.pageTitle}>💳 Loans</h2>
            <p className={styles.pageSubtitle}>Track money you owe and your payment history</p>
          </div>
        </div>
        <div className={styles.emptyState}>
          <div className={styles.emptyIcon}>💳</div>
          <h3 className={styles.emptyTitle}>No loans yet</h3>
          <p className={styles.emptyText}>Add a loan to start tracking your payments and balance.</p>
          <button className={styles.addBtn} onClick={() => setShowLoanForm(true)}>
            + Add a Loan
          </button>
        </div>
        {showLoanForm && (
          <LoanFormModal onClose={() => setShowLoanForm(false)} onSave={handleLoanSave} />
        )}
      </div>
    )
  }

  return (
    <div className={styles.loan}>
      {/* Top bar */}
      <div className={styles.topBar}>
        <div className={styles.topLeft}>
          <h2 className={styles.pageTitle}>💳 Loans</h2>
          {loans.length > 1 && (
            <select
              className={styles.loanSelect}
              value={selectedLoanId ?? ''}
              onChange={e => setSelectedLoanId(e.target.value)}
            >
              {loans.map(l => (
                <option key={l.id} value={l.id}>{l.name}</option>
              ))}
            </select>
          )}
          {loans.length === 1 && (
            <span className={styles.loanName}>{loans[0].name}</span>
          )}
        </div>
        <div className={styles.topActions}>
          <button className={styles.secondaryBtn} onClick={() => setShowLoanForm(true)}>
            + New Loan
          </button>
          {selectedLoan && (
            <>
              <button className={styles.secondaryBtn} onClick={() => setEditingLoan(selectedLoan)}>
                Edit
              </button>
              <button className={styles.dangerBtn} onClick={() => handleDeleteLoan(selectedLoan.id)}>
                Delete
              </button>
            </>
          )}
        </div>
      </div>

      {loading && <div className={styles.loadingBar} />}

      {selectedLoan && (
        <>
          {/* Loan info strip */}
          {selectedLoan.notes && (
            <div className={styles.notesStrip}>{selectedLoan.notes}</div>
          )}

          {/* Summary cards */}
          <div className={styles.summaryGrid}>
            <div className={styles.card}>
              <span className={styles.cardLabel}>Total borrowed</span>
              <span className={styles.cardValue}>{fmt(selectedLoan.principal)}</span>
              <span className={styles.cardSub}>since {selectedLoan.start_date}</span>
            </div>
            <div className={`${styles.card} ${styles.cardGreen}`}>
              <span className={styles.cardLabel}>Total paid</span>
              <span className={styles.cardValue}>{fmt(totalPaid)}</span>
              <span className={styles.cardSub}>
                {selectedLoan.principal > 0
                  ? `${Math.round((totalPaid / parseFloat(selectedLoan.principal)) * 100)}% of principal`
                  : ''}
              </span>
            </div>
            <div className={`${styles.card} ${balance <= 0 ? styles.cardGreen : styles.cardRed}`}>
              <span className={styles.cardLabel}>Balance remaining</span>
              <span className={styles.cardValue}>{fmt(Math.max(0, balance))}</span>
              <span className={styles.cardSub}>{balance <= 0 ? '🎉 Fully paid!' : 'still owed'}</span>
            </div>
            {selectedLoan.monthly_payment && (
              <div className={styles.card}>
                <span className={styles.cardLabel}>Expected monthly</span>
                <span className={styles.cardValue}>{fmt(selectedLoan.monthly_payment)}</span>
                <span className={styles.cardSub}>
                  {balance > 0
                    ? `~${Math.ceil(balance / parseFloat(selectedLoan.monthly_payment))} months left`
                    : 'done!'}
                </span>
              </div>
            )}
          </div>

          {/* Two-column layout: timeline + payment history */}
          <div className={styles.layout}>
            {/* Monthly timeline */}
            <div className={styles.timelineSection}>
              <h3 className={styles.sectionTitle}>Monthly status</h3>
              <div className={styles.timeline}>
                {timeline.map(({ year, month, payments: mp, total }) => {
                  const expected = selectedLoan.monthly_payment ? parseFloat(selectedLoan.monthly_payment) : null
                  const hasPaid = mp.length > 0
                  const isPartial = expected && hasPaid && total < expected * 0.99
                  const status = !hasPaid ? 'unpaid' : isPartial ? 'partial' : 'paid'
                  return (
                    <div key={`${year}-${month}`} className={`${styles.timelineRow} ${styles[`tl_${status}`]}`}>
                      <div className={styles.tlMonth}>{MONTHS[month - 1]} {year}</div>
                      <div className={styles.tlDot} />
                      <div className={styles.tlInfo}>
                        {hasPaid ? (
                          <>
                            <span className={styles.tlAmount}>{fmt(total)}</span>
                            {isPartial && expected && (
                              <span className={styles.tlNote}>partial ({fmt(expected - total)} short)</span>
                            )}
                          </>
                        ) : (
                          <span className={styles.tlMissed}>No payment</span>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>

            {/* Payment history */}
            <div className={styles.historySection}>
              <div className={styles.historyHeader}>
                <h3 className={styles.sectionTitle}>Payment history</h3>
                <button className={styles.addPaymentBtn} onClick={() => setShowPaymentForm(true)}>
                  + Log Payment
                </button>
              </div>

              {payments.length === 0 ? (
                <div className={styles.noPayments}>
                  <p>No payments logged yet.</p>
                  <button className={styles.addPaymentBtn} onClick={() => setShowPaymentForm(true)}>
                    Log your first payment
                  </button>
                </div>
              ) : (
                <div className={styles.tableWrap}>
                  <table className={styles.table}>
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th className={styles.right}>Amount</th>
                        <th>Notes</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {payments.map(p => (
                        <tr key={p.id} className={styles.payRow}>
                          <td className={styles.payDate}>{p.date}</td>
                          <td className={`${styles.right} ${styles.payAmount}`}>{fmt(p.amount)}</td>
                          <td className={styles.payNotes}>{p.notes || <span className={styles.dim}>—</span>}</td>
                          <td className={styles.payActions}>
                            <button
                              className={styles.editBtn}
                              onClick={() => setEditingPayment(p)}
                            >Edit</button>
                            <button
                              className={styles.deleteBtn}
                              onClick={() => handleDeletePayment(p.id)}
                            >✕</button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot>
                      <tr className={styles.totalRow}>
                        <td><strong>Total paid</strong></td>
                        <td className={styles.right}><strong>{fmt(totalPaid)}</strong></td>
                        <td colSpan={2} />
                      </tr>
                    </tfoot>
                  </table>
                </div>
              )}
            </div>
          </div>
        </>
      )}

      {/* Modals */}
      {(showLoanForm || editingLoan) && (
        <LoanFormModal
          loan={editingLoan}
          onClose={() => { setShowLoanForm(false); setEditingLoan(null) }}
          onSave={handleLoanSave}
        />
      )}
      {(showPaymentForm || editingPayment) && selectedLoan && (
        <PaymentFormModal
          loanId={selectedLoan.id}
          payment={editingPayment}
          onClose={() => { setShowPaymentForm(false); setEditingPayment(null) }}
          onSave={handlePaymentSave}
        />
      )}
    </div>
  )
}
