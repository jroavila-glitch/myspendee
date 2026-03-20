import React from 'react'
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import styles from './CategoryChart.module.css'

const GREEN_COLORS = [
  '#16a34a', '#22c55e', '#4ade80', '#86efac', '#15803d',
  '#166534', '#dcfce7', '#bbf7d0', '#6ee7b7', '#34d399'
]
const RED_COLORS = [
  '#dc2626', '#ef4444', '#f87171', '#fca5a5', '#b91c1c',
  '#991b1b', '#fecaca', '#fee2e2', '#f43f5e', '#fb7185'
]

function fmt(v) {
  return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 0 }).format(v)
}

export default function CategoryChart({ data, colorScheme, onCategoryClick, selectedCategory }) {
  const colors = colorScheme === 'green' ? GREEN_COLORS : RED_COLORS
  const total = data.reduce((s, d) => s + parseFloat(d.amount), 0)

  if (!data.length) {
    return <div className={styles.empty}>No data for this period</div>
  }

  const chartData = data.map(d => ({ name: d.category, value: parseFloat(d.amount), count: d.count }))

  const CustomTooltip = ({ active, payload }) => {
    if (!active || !payload?.length) return null
    const d = payload[0]
    return (
      <div className={styles.tooltip}>
        <strong>{d.name}</strong>
        <div>{fmt(d.value)}</div>
        <div style={{ color: '#888', fontSize: '0.8rem' }}>{d.payload.count} transactions</div>
      </div>
    )
  }

  return (
    <div className={styles.container}>
      <ResponsiveContainer width="100%" height={200}>
        <PieChart>
          <Pie
            data={chartData}
            cx="50%"
            cy="50%"
            outerRadius={80}
            dataKey="value"
            onClick={(d) => onCategoryClick?.(d.name)}
          >
            {chartData.map((entry, i) => (
              <Cell
                key={entry.name}
                fill={colors[i % colors.length]}
                opacity={selectedCategory && selectedCategory !== entry.name ? 0.4 : 1}
                style={{ cursor: 'pointer' }}
              />
            ))}
          </Pie>
          <Tooltip content={<CustomTooltip />} />
        </PieChart>
      </ResponsiveContainer>

      <table className={styles.table}>
        <thead>
          <tr>
            <th>Category</th>
            <th className={styles.right}>Amount</th>
            <th className={styles.right}>%</th>
          </tr>
        </thead>
        <tbody>
          {data.map((d, i) => (
            <tr
              key={d.category}
              className={`${styles.row} ${selectedCategory === d.category ? styles.selected : ''}`}
              onClick={() => onCategoryClick?.(d.category)}
            >
              <td className={styles.catCell}>
                <span className={styles.dot} style={{ background: colors[i % colors.length] }} />
                {d.category}
              </td>
              <td className={styles.right}>{fmt(d.amount)}</td>
              <td className={styles.right + ' ' + styles.pct}>
                {total > 0 ? ((d.amount / total) * 100).toFixed(1) : '0'}%
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
