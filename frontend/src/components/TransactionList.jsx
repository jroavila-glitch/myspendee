import React, { useState, useEffect, useRef } from 'react'
import { deleteTransaction } from '../api.js'
import styles from './TransactionList.module.css'

function fmt(v) {
  return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(v)
}

function fmtDate(d) {
  return new Date(d + 'T00:00:00').toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}

const TYPE_COLORS = { income: '#16a34a', expense: '#dc2626', ignored: '#9ca3af' }

export default function TransactionList({ transactions, onDelete, onEdit }) {
  const [menuOpen, setMenuOpen] = useState(null)
  const [deleting, setDeleting] = useState(null)
  const menuRef = useRef(null)

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuOpen(null)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleDelete = async (id) => {
    if (!confirm('Delete this transaction? This cannot be undone.')) return
    setDeleting(id)
    try {
      await deleteTransaction(id)
      onDelete?.()
    } catch (e) {
      alert('Error deleting transaction')
    } finally {
      setDeleting(null)
      setMenuOpen(null)
    }
  }

  const handleEdit = (tx) => {
    setMenuOpen(null)
    onEdit?.(tx)
  }

  if (!transactions.length) {
    return <div className={styles.empty}>No transactions found</div>
  }

  return (
    <div className={styles.container}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Date</th>
            <th>Description</th>
            <th>Bank</th>
            <th>Category</th>
            <th className={styles.right}>Amount (MXN)</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {transactions.map(tx => (
            <tr key={tx.id} className={styles.row}>
              <td className={styles.date}>{fmtDate(tx.date)}</td>
              <td className={styles.desc}>
                <span className={styles.descText} title={tx.description}>{tx.description}</span>
                {tx.manually_added && <span className={styles.badge}>manual</span>}
                {tx.notes && !tx.notes.startsWith('Auto-ignored') && (
                  <span className={styles.notes} title={tx.notes}>ℹ</span>
                )}
              </td>
              <td className={styles.bank}>{tx.bank_name}</td>
              <td>
                <span className={styles.category} style={{ '--clr': TYPE_COLORS[tx.type] }}>
                  {tx.category}
                </span>
              </td>
              <td className={styles.right}>
                <span className={styles.amount} style={{ color: TYPE_COLORS[tx.type] }}>
                  {tx.type === 'income' ? '+' : tx.type === 'expense' ? '-' : ''}{fmt(tx.amount_mxn)}
                </span>
              </td>
              <td className={styles.menuCell} ref={menuOpen === tx.id ? menuRef : null}>
                <div className={styles.menuWrap}>
                  <button
                    className={styles.menuBtn}
                    onClick={() => setMenuOpen(menuOpen === tx.id ? null : tx.id)}
                    aria-label="Transaction options"
                  >⋮</button>
                  {menuOpen === tx.id && (
                    <div className={styles.dropdown}>
                      <button
                        className={styles.editItem}
                        onClick={() => handleEdit(tx)}
                      >
                        ✏️ Edit
                      </button>
                      <div className={styles.divider} />
                      <button
                        className={styles.deleteItem}
                        onClick={() => handleDelete(tx.id)}
                        disabled={deleting === tx.id}
                      >
                        {deleting === tx.id ? '⏳ Deleting…' : '🗑 Delete'}
                      </button>
                    </div>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
