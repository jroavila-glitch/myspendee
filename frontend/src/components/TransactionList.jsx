import React, { useState, useEffect, useRef, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { deleteTransaction, updateTransaction, bulkUpdateTransactions, getCategories } from '../api.js'
import styles from './TransactionList.module.css'

// ── Formatters ────────────────────────────────────────────────────────────────
function fmt(v) {
  return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(v)
}

function fmtOrig(amount, currency) {
  const n = Number(amount)
  return `${currency} ${n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function fmtDate(d) {
  return new Date(d + 'T00:00:00').toLocaleDateString('en-GB', {
    day: '2-digit', month: 'short', year: 'numeric',
  })
}

const TYPE_COLORS = { income: '#16a34a', expense: '#dc2626', ignored: '#9ca3af' }

/**
 * Returns { amount, currency } for the original foreign-currency amount, or null for MXN.
 * Falls back to amount_mxn / exchange_rate_used if amount_original is missing/zero.
 */
function getOriginalDisplay(tx) {
  const cur = tx.currency_original
  if (!cur || cur === 'MXN') return null
  const orig = Number(tx.amount_original)
  if (orig > 0) return { amount: orig, currency: cur }
  // Fallback: derive from MXN ÷ rate
  const rate = Number(tx.exchange_rate_used)
  const mxn  = Number(tx.amount_mxn)
  if (rate > 0 && mxn > 0) return { amount: mxn / rate, currency: cur }
  return null
}

// ── Inline notes cell ─────────────────────────────────────────────────────────
function NotesCell({ tx, onSaved }) {
  const [value, setValue]   = useState(tx.notes || '')
  const [saving, setSaving] = useState(false)
  const original = useRef(tx.notes || '')

  useEffect(() => {
    setValue(tx.notes || '')
    original.current = tx.notes || ''
  }, [tx.notes, tx.id])

  const save = useCallback(async () => {
    const trimmed = value.trim()
    if (trimmed === original.current.trim()) return
    setSaving(true)
    try {
      await updateTransaction(tx.id, { notes: trimmed || null })
      original.current = trimmed
      onSaved?.()
    } catch {
      setValue(original.current)
    } finally {
      setSaving(false)
    }
  }, [tx.id, value, onSaved])

  const handleKeyDown = (e) => {
    if (e.key === 'Enter')  e.target.blur()
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
  // 3-dot menu — portal based (avoids overflow:hidden clipping)
  const [menuPos,  setMenuPos]  = useState(null)   // { id, top, right }
  const [deleting, setDeleting] = useState(null)

  // Bulk-edit state
  const [selected,   setSelected]   = useState(new Set())
  const [categories, setCategories] = useState({ income: [], expense: [] })
  const [bulkCat,    setBulkCat]    = useState('')
  const [bulkType,   setBulkType]   = useState('')
  const [applying,   setApplying]   = useState(false)

  // Load categories once
  useEffect(() => {
    getCategories().then(r => setCategories(r.data)).catch(() => {})
  }, [])

  // Reset selection when transaction list changes
  useEffect(() => { setSelected(new Set()) }, [transactions])

  // Close portal-menu on outside click
  useEffect(() => {
    if (!menuPos) return
    const handler = (e) => {
      if (!e.target.closest('[data-menu-portal]')) setMenuPos(null)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [menuPos])

  // ── Menu helpers ──────────────────────────────────────────────────────────
  const openMenu = (e, txId) => {
    e.stopPropagation()
    if (menuPos?.id === txId) { setMenuPos(null); return }
    const rect = e.currentTarget.getBoundingClientRect()
    setMenuPos({
      id:    txId,
      top:   rect.bottom + 4,
      right: window.innerWidth - rect.right,
    })
  }

  // ── Delete ────────────────────────────────────────────────────────────────
  const handleDelete = async (id) => {
    if (!confirm('Delete this transaction? This cannot be undone.')) return
    setDeleting(id)
    setMenuPos(null)
    try {
      await deleteTransaction(id)
      onDelete?.()
    } catch {
      alert('Error deleting transaction')
    } finally {
      setDeleting(null)
    }
  }

  // ── Edit ──────────────────────────────────────────────────────────────────
  const handleEdit = (tx) => {
    setMenuPos(null)
    onEdit?.(tx)
  }

  // ── Checkbox helpers ──────────────────────────────────────────────────────
  const allIds     = transactions.map(t => t.id)
  const allChecked = allIds.length > 0 && allIds.every(id => selected.has(id))
  const toggleAll  = () => setSelected(allChecked ? new Set() : new Set(allIds))
  const toggleOne  = (id) => setSelected(prev => {
    const next = new Set(prev)
    next.has(id) ? next.delete(id) : next.add(id)
    return next
  })

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
    .filter((v, i, a) => a.indexOf(v) === i).sort()

  // The transaction currently shown in the portal menu
  const menuTx = menuPos ? transactions.find(t => t.id === menuPos.id) : null

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
              <th style={{ width: 36 }}></th>
            </tr>
          </thead>
          <tbody>
            {transactions.map(tx => {
              const origDisp  = getOriginalDisplay(tx)
              const isSelected = selected.has(tx.id)
              return (
                <tr key={tx.id}
                  className={`${styles.row} ${isSelected ? styles.rowSelected : ''}`}>

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

                  {/* Amount — MXN on top, original currency subtitle below */}
                  <td className={styles.right}>
                    <span className={styles.amount} style={{ color: TYPE_COLORS[tx.type] }}>
                      {tx.type === 'income' ? '+' : tx.type === 'expense' ? '-' : ''}
                      {fmt(tx.amount_mxn)}
                    </span>
                    {origDisp && (
                      <div className={styles.originalAmount}>
                        {fmtOrig(origDisp.amount, origDisp.currency)}
                      </div>
                    )}
                  </td>

                  {/* Inline notes */}
                  <td className={styles.notesCol}>
                    <NotesCell tx={tx} onSaved={onRefresh} />
                  </td>

                  {/* 3-dot menu — no dropdown here, portal renders at body */}
                  <td className={styles.menuCell}>
                    <button
                      className={`${styles.menuBtn} ${menuPos?.id === tx.id ? styles.menuBtnActive : ''}`}
                      onClick={(e) => openMenu(e, tx.id)}
                      aria-label="Transaction options"
                    >⋮</button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Portal dropdown — renders at document.body, never clipped */}
      {menuPos && menuTx && createPortal(
        <div
          data-menu-portal
          className={styles.dropdownPortal}
          style={{ top: menuPos.top, right: menuPos.right }}
        >
          <button className={styles.editItem} onClick={() => handleEdit(menuTx)}>
            ✏️ Edit
          </button>
          <div className={styles.divider} />
          <button
            className={styles.deleteItem}
            onClick={() => handleDelete(menuTx.id)}
            disabled={deleting === menuTx.id}
          >
            {deleting === menuTx.id ? '⏳ Deleting…' : '🗑 Delete'}
          </button>
        </div>,
        document.body
      )}

      {/* Floating bulk-action bar */}
      {selected.size > 0 && (
        <div className={styles.bulkBar}>
          <span className={styles.bulkCount}>{selected.size} selected</span>

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
