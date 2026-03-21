import React, { useState, useEffect, useCallback } from 'react'
import { getSummary, getBreakdown, getTransactions, getBanks } from '../api.js'
import CategoryChart from './CategoryChart.jsx'
import TransactionList from './TransactionList.jsx'
import AddTransactionModal from './AddTransactionModal.jsx'
import styles from './Dashboard.module.css'

const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
]

function fmt(amount) {
  return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(amount)
}

export default function Dashboard() {
  const now = new Date()
  const [month, setMonth] = useState(now.getMonth() + 1)
  const [year, setYear] = useState(now.getFullYear())

  const [summary, setSummary] = useState(null)
  const [breakdown, setBreakdown] = useState(null)
  const [transactions, setTransactions] = useState([])
  const [banks, setBanks] = useState([])
  const [loading, setLoading] = useState(true)

  // Filters
  const [filterBank, setFilterBank] = useState('')
  const [filterCategory, setFilterCategory] = useState('')
  const [filterType, setFilterType] = useState('')

  // Drilldown
  const [drillCategory, setDrillCategory] = useState(null)

  // Modals
  const [showAddModal, setShowAddModal] = useState(false)
  const [editingTx, setEditingTx] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [summRes, brkRes, txRes, bankRes] = await Promise.all([
        getSummary(month, year),
        getBreakdown(month, year),
        getTransactions({ month, year, bank: filterBank || undefined, type: filterType || undefined }),
        getBanks(),
      ])
      setSummary(summRes.data)
      setBreakdown(brkRes.data)
      setTransactions(txRes.data)
      setBanks(bankRes.data)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [month, year, filterBank, filterType])

  useEffect(() => { load() }, [load])

  const handleCategoryClick = async (cat, type) => {
    if (drillCategory?.name === cat && drillCategory?.type === type) {
      setDrillCategory(null)
      return
    }
    try {
      const res = await getTransactions({ month, year, category: cat, type })
      setDrillCategory({ name: cat, type, transactions: res.data })
    } catch (e) { console.error(e) }
  }

  const handleDelete = () => {
    load()
    if (drillCategory) {
      getTransactions({ month, year, category: drillCategory.name, type: drillCategory.type })
        .then(res => setDrillCategory(d => d ? { ...d, transactions: res.data } : null))
    }
  }

  const handleEdit = (tx) => {
    setEditingTx(tx)
  }

  const handleEditSave = () => {
    setEditingTx(null)
    load()
    if (drillCategory) {
      getTransactions({ month, year, category: drillCategory.name, type: drillCategory.type })
        .then(res => setDrillCategory(d => d ? { ...d, transactions: res.data } : null))
    }
  }

  const handleAdd = () => {
    setShowAddModal(false)
    load()
  }

  const years = Array.from({ length: 5 }, (_, i) => now.getFullYear() - 2 + i)

  // Filtered transactions for list
  const filteredTx = filterCategory
    ? transactions.filter(t => t.category?.toLowerCase() === filterCategory.toLowerCase())
    : transactions

  return (
    <div className={styles.dashboard}>
      {/* Header controls */}
      <div className={styles.controls}>
        <div className={styles.periodSelector}>
          <select className={styles.select} value={month} onChange={e => setMonth(+e.target.value)}>
            {MONTHS.map((m, i) => <option key={i} value={i + 1}>{m}</option>)}
          </select>
          <select className={styles.select} value={year} onChange={e => setYear(+e.target.value)}>
            {years.map(y => <option key={y} value={y}>{y}</option>)}
          </select>
        </div>
        <button className={styles.addBtn} onClick={() => setShowAddModal(true)}>
          + Add Transaction
        </button>
      </div>

      {loading && <div className={styles.loadingBar} />}

      {/* P&L Summary */}
      {summary && (
        <div className={styles.summaryGrid}>
          <div className={`${styles.summaryCard} ${styles.income}`}>
            <span className={styles.summaryLabel}>Total Income</span>
            <span className={styles.summaryAmount}>{fmt(summary.total_income)}</span>
          </div>
          <div className={`${styles.summaryCard} ${styles.expense}`}>
            <span className={styles.summaryLabel}>Total Expenses</span>
            <span className={styles.summaryAmount}>{fmt(summary.total_expenses)}</span>
          </div>
          <div className={`${styles.summaryCard} ${summary.net >= 0 ? styles.netPos : styles.netNeg}`}>
            <span className={styles.summaryLabel}>Net</span>
            <span className={styles.summaryAmount}>{fmt(summary.net)}</span>
          </div>
        </div>
      )}

      {/* Filter sidebar + content */}
      <div className={styles.layout}>
        <aside className={styles.sidebar}>
          <h3 className={styles.sidebarTitle}>Filters</h3>

          <label className={styles.filterLabel}>Bank</label>
          <select className={styles.filterSelect} value={filterBank} onChange={e => { setFilterBank(e.target.value); setDrillCategory(null) }}>
            <option value="">All banks</option>
            {banks.map(b => <option key={b} value={b}>{b}</option>)}
          </select>

          <label className={styles.filterLabel}>Type</label>
          <select className={styles.filterSelect} value={filterType} onChange={e => { setFilterType(e.target.value); setDrillCategory(null) }}>
            <option value="">All types</option>
            <option value="income">Income</option>
            <option value="expense">Expense</option>
          </select>

          {(filterBank || filterType || filterCategory) && (
            <button className={styles.clearBtn} onClick={() => { setFilterBank(''); setFilterType(''); setFilterCategory(''); setDrillCategory(null) }}>
              Clear filters
            </button>
          )}
        </aside>

        <div className={styles.content}>
          {/* Breakdown charts */}
          {breakdown && (
            <div className={styles.chartsRow}>
              <div className={styles.chartSection}>
                <h2 className={styles.sectionTitle}>Income by Category</h2>
                <CategoryChart
                  data={breakdown.income}
                  colorScheme="green"
                  onCategoryClick={(cat) => handleCategoryClick(cat, 'income')}
                  selectedCategory={drillCategory?.type === 'income' ? drillCategory?.name : null}
                />
              </div>
              <div className={styles.chartSection}>
                <h2 className={styles.sectionTitle}>Expenses by Category</h2>
                <CategoryChart
                  data={breakdown.expenses}
                  colorScheme="red"
                  onCategoryClick={(cat) => handleCategoryClick(cat, 'expense')}
                  selectedCategory={drillCategory?.type === 'expense' ? drillCategory?.name : null}
                />
              </div>
            </div>
          )}

          {/* Drilldown */}
          {drillCategory && (
            <div className={styles.drilldown}>
              <div className={styles.drillHeader}>
                <h3 className={styles.drillTitle}>
                  {drillCategory.type === 'income' ? '🟢' : '🔴'} {drillCategory.name}
                  <span className={styles.drillCount}> ({drillCategory.transactions.length} transactions)</span>
                </h3>
                <button className={styles.closeBtn} onClick={() => setDrillCategory(null)}>✕</button>
              </div>
              <TransactionList
                transactions={drillCategory.transactions}
                onDelete={handleDelete}
                onEdit={handleEdit}
              />
            </div>
          )}

          {/* All transactions */}
          {!drillCategory && (
            <>
              <div className={styles.txHeader}>
                <h2 className={styles.sectionTitle}>
                  Transactions
                  <span className={styles.txCount}> ({filteredTx.length})</span>
                </h2>
              </div>
              <TransactionList transactions={filteredTx} onDelete={handleDelete} onEdit={handleEdit} />
            </>
          )}
        </div>
      </div>

      {/* Add modal */}
      {showAddModal && (
        <AddTransactionModal onClose={() => setShowAddModal(false)} onSave={handleAdd} />
      )}

      {/* Edit modal */}
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
