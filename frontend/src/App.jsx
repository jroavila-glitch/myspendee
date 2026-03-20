import React, { useState } from 'react'
import Dashboard from './components/Dashboard.jsx'
import Upload from './components/Upload.jsx'
import styles from './App.module.css'

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard')
  const [refreshKey, setRefreshKey] = useState(0)

  const handleUploadSuccess = () => {
    setRefreshKey(k => k + 1)
    setActiveTab('dashboard')
  }

  return (
    <div className={styles.app}>
      <header className={styles.header}>
        <div className={styles.headerInner}>
          <h1 className={styles.logo}>💸 MySpendee</h1>
          <nav className={styles.nav}>
            <button
              className={`${styles.navBtn} ${activeTab === 'dashboard' ? styles.active : ''}`}
              onClick={() => setActiveTab('dashboard')}
            >
              Dashboard
            </button>
            <button
              className={`${styles.navBtn} ${activeTab === 'upload' ? styles.active : ''}`}
              onClick={() => setActiveTab('upload')}
            >
              Upload Statements
            </button>
          </nav>
        </div>
      </header>
      <main className={styles.main}>
        {activeTab === 'dashboard' && <Dashboard key={refreshKey} />}
        {activeTab === 'upload' && <Upload onSuccess={handleUploadSuccess} />}
      </main>
    </div>
  )
}
