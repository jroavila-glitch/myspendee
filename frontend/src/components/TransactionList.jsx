import React, { useState, useEffect, useRef, useCallback } from 'react'
import { deleteTransaction, updateTransaction, bulkUpdateTransactions, getCategories } from '../api.js'
import styles from './TransactionList.module.css'

function fmt(v) {
  return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(v)
}

function fmtOrig(amount, currency) {
  const n = Number(amount)
  const s = n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  return `${currency} ${s}`
}

function fmtDate(d) {
  return new Date(d + 'T00:00:00').toLocaleDateString('en-GB', {
    day: '2-digit', month: 'short', year: 'numeric',
  })
}

const TYPE_COLORS = { income: '#16a34a', expense: '#dc2626', ignored: '#9ca3af' }

// ── Inline notes cell ─────────────────────────────────────────────────────────
function NotesCell({ tx, onSaved }) {
  const [value, setValue] = useState(tx.notes || '')
  const [saving, setSaving] = useState(false)
  const original = useRef(tx.notes || '')

  // Sync if parent updates the tx (e.g. after bulk action)
  useEffect(() => { setValue(tx.notes || ''); original.current = tx.notes || '' }, [tx.notes, tx.id])

  const save = useCallback(async () => {
    const trimmed = value.trim()
    if (trimmed === original.current.trim()) return   // nothing changed
    setSaving(true)
    try {
      await updateTransaction(tx.id, { notes: trimmed || null })
      original.current = trimmed
      onSaved?.()
    } catch {
      setValue(original.current)   // revert on error
    } finally {
      setSaving(false)
    }
  }, [tx.id, value, onSaved])

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') { e.target.blur() }
    if (e.key === 'Escape') { setValue(original.current); e.target.blur() }
  }

  return (
    <input
      className={`${styles.notesInput} ${saving ? styles.notesSaving : ''}`}
      value={value}
      onChange={e => setValue(e.target.value)}
      onBlur={save}
      onKeyDown={handleKeyDown}
      placeholder="Add note…"
      title={value || 'Click to add a note'}
    />
  )
}

// ── Main component ────────────────────────────────────────────────────────────
export default function TransactionList({ transactions, onDelete, onEdit, onRefresh }) {
  const [menuOpen, setMenuOpen]     = useState(null)
  const [deleting, setDeleting]     = useState(null)
  const [selected, setSelected]     = useState(new Set())
  const [categories, setCategories] = useState({ income: [], expense: [] })
  const [bulkCat,  setBulkCat]      = useState('')
  const [bulkType, setBulkType]     = useState('')
  const [applying, setApplying]     = useState(false)
  const menuRef = useRef(null)

  // Load categories for the bulk-edit bar
  useEffect(() => {
    getCategories().then(r => setCategories(r.data)).catch(() => {})
  }, [])

  // Clear selection when transaction list changes (e.g. month switch)
  useEffect(() => { setSelected(new Set()) }, [transactions])

  // Close dropdown on outside click
  useEffect(() => {
    const h = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) setMenuOpen(null)
    }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [])

  // ── Selection helpers ─────────────────────────────────────────────────────
  const allIds   = transactions.map(t => t.id)
  const allChecked = allIds.length > 0 && allIds.every(id => selected.has(id))
  const someChecked = selected.size > 0

  const toggleAll = () => {
    if (allChecked) setSelected(new Set())
    else setSelected(new Set(allIds))
  }

  const toggleOne = (id) => {
    setSelected(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  // ── Delete ────────────────────────────────────────────────────────────────
  const handleDelete = async (id) => {
    if (!confirm('Delete this transaction? This cannot be undone.')) return
    setDeleting(id)
    try {
      await deleteTransaction(id)
      onDelete?.()
    } catch {
      alert('Error deleting transaction')
    } finally {
      setDeleting(null)
      setMenuOpen(null)
    }
  }

  // ── Edit (opens modal) ────────────────────────────────────────────────────
  const handleEdit = (tx) => { setMenuOpen(null); onEdit?.(tx) }

  // ── Bulk apply ────────────────────────────────────────────────────────────
  const handleBulkApply = async () => {
    if (!bulkCat && !bulkType) return
    setApplying(true)
    try {
      const fields = {}
      if (bulkCat)  fields.category = bulkCat
      if (bulkType) fields.type     = bulkType
      await bulkUpdateTransactions([...selected], fields)
      setSelected(new Set())
      setBulkCat('')
      setBulkType('')
      onRefresh?.()
    } catch {
      alert('Bulk update failed')
    } finally {
      setApplying(false)
    }
  }

  const allCategories = [...categories.income, ...categories.expense]
    .filter((v, i, a) => a.indexOf(v) === i)
    .sort()

  if (!transactions.length) {
    return <div className={styles.empty}>No transactions found</div>
  }

  return (
    <>
      <div className={styles.container}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th className={styles.checkCol}>
                <input type="checkbox" checked={allChecked}
                  onChange={toggleAll} title="Select all" />
              </th>
              <th>Date</th>
              <th>Description</th>
              <th>Bank</th>
              <th>Category</th>
              <th className={styles.right}>Amount</th>
              <th className={styles.notesCol}>Notes</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {transactions.map(tx => {
              const showOrig = tx.currency_original && tx.currency_original !== 'MXN'
              const isSelected = selected.has(tx.id)
              return (
                <tr key={tx.id}
                  className={`${styles.row} ${isSelected ? styles.rowSelected : ''}`}
                >
                  {/* Checkbox */}
                  <td className={styles.checkCol}>
                    <input type="checkbox" checked={isSelected}
                      onChange={() => toggleOne(tx.id)} />
                  </td>

                  {/* Date */}
                  <td className={styles.date}>{fmtDate(tx.date)}</td>

                  {/* Description */}
                  <td className={styles.desc}>
                    <span className={styles.descText} title={tx.description}>
                      {tx.description}
                    </span>
                    {tx.manually_added && <span className={styles.badge}>manual</span>}
                  </td>

                  {/* Bank */}
                  <td className={styles.bank}>{tx.bank_name}</td>

                  {/* Category */}
                  <td>
                    <span className={styles.category}
                      style={{ '--clr': TYPE_COLORS[tx.type] }}>
                      {tx.category}
                    </span>
                  </td>

                  {/* Amount (MXN + original currency line) */}
                  <td className={styles.right}>
                    <span className={styles.amount}
                      style={{ color: TYPE_COLORS[tx.type] }}>
                      {tx.type === 'income' ? '+' : tx.type === 'expense' ? '-' : ''}
                      {fmt(tx.amount_mxn)}
                    </span>
                    {showOrig && (
                      <div className={styles.originalAmount}>
                        {fmtOrig(tx.amount_original, tx.currency_original)}
                        {' → '}{fmt(tx.amount_mxn)}
                      </div>
                    )}
                  </td>

                  {/* Inline notes */}
                  <td className={styles.notesCol}>
                    <NotesCell tx={tx} onSaved={onRefresh} />
                  </td>

                  {/* 3-dot menu */}
                  <td className={styles.menuCell}
                    ref={menuOpen === tx.id ? menuRef : null}>
                    <div className={styles.menuWrap}>
                      <button className={styles.menuBtn}
                        onClick={() => setMenuOpen(menuOpen === tx.id ? null : tx.id)}
                        aria-label="Transaction options">⋮</button>
                      {menuOpen === tx.id && (
                        <div className={styles.dropdown}>
                          <button className={styles.editItem}
                            onClick={() => handleEdit(tx)}>
                            ✏️ Edit
                          </button>
                          <div className={styles.divider} />
                          <button className={styles.deleteItem}
                            onClick={() => handleDelete(tx.id)}
                            disabled={deleting === tx.id}>
                            {deleting === tx.id ? '⏳ Deleting…' : '🗑 Delete'}
                          </button>
                        </div>
                      )}
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Floating bulk-action bar */}
      {someChecked && (
        <div className={styles.bulkBar}>
          <span className={styles.bulkCount}>
            {selected.size} selected
          </span>

          <select className={styles.bulkSelect} value={bulkCat}
            onChange={e => setBulkCat(e.target.value)}>
            <option value="">Change category…</option>
            {allCategories.map(c => <option key={c} value={c}>{c}</option>)}
          </select>

          <select className={styles.bulkSelect} value={bulkType}
            onChange={e => setBulkType(e.target.value)}>
            <option value="">Change type…</option>
            <option value="income">Income</option>
            <option value="expense">Expense</option>
          </select>

          <button className={styles.bulkApply}
            onClick={handleBulkApply}
            disabled={applying || (!bulkCat && !bulkType)}>
            {applying ? 'Applying…' : 'Apply'}
          </button>

          <button className={styles.bulkCancel}
            onClick={() => { setSelected(new Set()); setBulkCat(''); setBulkType('') }}>
            Cancel
          </button>
        </div>
      )}
    </>
  )
}
