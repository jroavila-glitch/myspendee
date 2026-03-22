import React, { useState, useEffect } from 'react'
import { createTransaction, updateTransaction, getCategories } from '../api.js'
import styles from './AddTransactionModal.module.css'

const PRESET_BANKS = [
  'Revolut', 'Millennium BCP', 'Nu Debit', 'Nu Credit',
  'Rappi Credit', 'Oro Banamex', 'Costco Banamex', 'HSBC 2Now',
  'DolarApp EURc', 'DolarApp USDc', 'Other'
]

/**
 * AddTransactionModal
 * Props:
 *   onClose       () => void
 *   onSave        () => void
 *   transaction   object | null — if provided, opens in edit mode
 */
export default function AddTransactionModal({ onClose, onSave, transaction }) {
  const isEdit = Boolean(transaction)
  const [categories, setCategories] = useState({ income: [], expense: [] })
  const [form, setForm] = useState({
    date: transaction?.date ?? new Date().toISOString().split('T')[0],
    description: transaction?.description ?? '',
    amount_mxn: transaction?.amount_mxn != null ? String(Math.abs(Number(transaction.amount_mxn))) : '',
    category: transaction?.category ?? '',
    type: transaction?.type === 'income' ? 'income' : 'expense',
    bank_name: transaction?.bank_name ?? '',
    notes: transaction?.notes ?? '',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    getCategories().then(res => setCategories(res.data)).catch(() => {})
  }, [])

  // Build bank list: always include the transaction's current bank even if not in preset list
  const bankOptions = isEdit && form.bank_name && !PRESET_BANKS.includes(form.bank_name)
    ? [form.bank_name, ...PRESET_BANKS]
    : PRESET_BANKS

  const availableCategories = categories[form.type] || []

  const set = (k, v) => setForm(f => ({ ...f, [k]: v, ...(k === 'type' ? { category: '' } : {}) }))

  const formatError = (err) => {
    if (!err) return null
    if (Array.isArray(err)) {
      return err.map(e => e.msg || JSON.stringify(e)).join('; ')
    }
    if (typeof err === 'object') return JSON.stringify(err)
    return String(err)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    if (!form.description || !form.amount_mxn || !form.category || !form.bank_name) {
      setError('Please fill in all required fields')
      return
    }
    setLoading(true)
    try {
      const payload = {
        date: form.date,
        description: form.description,
        amount_mxn: parseFloat(form.amount_mxn),
        category: form.category,
        type: form.type,
        bank_name: form.bank_name,
        notes: form.notes || null,   // send null instead of "" to avoid schema issues
      }
      if (isEdit) {
        await updateTransaction(transaction.id, payload)
      } else {
        await createTransaction(payload)
      }
      onSave()
    } catch (err) {
      const detail = err.response?.data?.detail
      setError(formatError(detail) || `Failed to ${isEdit ? 'update' : 'save'} transaction`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={styles.overlay} onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className={styles.modal}>
        <div className={styles.header}>
          <h2 className={styles.title}>{isEdit ? 'Edit Transaction' : 'Add Transaction'}</h2>
          <button className={styles.closeBtn} onClick={onClose}>✕</button>
        </div>

        <form onSubmit={handleSubmit} className={styles.form}>
          <div className={styles.row}>
            <div className={styles.field}>
              <label className={styles.label}>Date *</label>
              <input type="date" className={styles.input} value={form.date}
                onChange={e => set('date', e.target.value)} required />
            </div>
            <div className={styles.field}>
              <label className={styles.label}>Type *</label>
              <select className={styles.input} value={form.type} onChange={e => set('type', e.target.value)}>
                <option value="expense">Expense</option>
                <option value="income">Income</option>
              </select>
            </div>
          </div>

          <div className={styles.field}>
            <label className={styles.label}>Description *</label>
            <input type="text" className={styles.input} value={form.description}
              onChange={e => set('description', e.target.value)} placeholder="Transaction description" required />
          </div>

          <div className={styles.row}>
            <div className={styles.field}>
              <label className={styles.label}>Amount (MXN) *</label>
              <input type="number" step="0.01" min="0" className={styles.input} value={form.amount_mxn}
                onChange={e => set('amount_mxn', e.target.value)} placeholder="0.00" required />
            </div>
            <div className={styles.field}>
              <label className={styles.label}>Bank *</label>
              <select className={styles.input} value={form.bank_name} onChange={e => set('bank_name', e.target.value)} required>
                <option value="">Select bank…</option>
                {bankOptions.map(b => <option key={b} value={b}>{b}</option>)}
              </select>
            </div>
          </div>

          <div className={styles.field}>
            <label className={styles.label}>Category *</label>
            <select className={styles.input} value={form.category} onChange={e => set('category', e.target.value)} required>
              <option value="">Select category…</option>
              {availableCategories.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>

          <div className={styles.field}>
            <label className={styles.label}>Notes</label>
            <textarea className={styles.textarea} value={form.notes}
              onChange={e => set('notes', e.target.value)} placeholder="Optional notes…" rows={2} />
          </div>

          {error && <div className={styles.error}>{error}</div>}

          <div className={styles.actions}>
            <button type="button" className={styles.cancelBtn} onClick={onClose}>Cancel</button>
            <button type="submit" className={styles.saveBtn} disabled={loading}>
              {loading ? 'Saving…' : isEdit ? 'Save Changes' : 'Save Transaction'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
