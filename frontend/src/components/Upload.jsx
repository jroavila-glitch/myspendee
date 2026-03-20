import React, { useState, useRef } from 'react'
import { uploadPDFs } from '../api.js'
import styles from './Upload.module.css'

export default function Upload({ onSuccess }) {
  const [files, setFiles] = useState([])
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef()

  const handleFiles = (incoming) => {
    const pdfs = Array.from(incoming).filter(f => f.name.toLowerCase().endsWith('.pdf'))
    setFiles(prev => {
      const existing = new Set(prev.map(f => f.name))
      return [...prev, ...pdfs.filter(f => !existing.has(f.name))]
    })
    setResult(null)
    setError(null)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    handleFiles(e.dataTransfer.files)
  }

  const removeFile = (name) => setFiles(prev => prev.filter(f => f.name !== name))

  const handleUpload = async () => {
    if (!files.length) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await uploadPDFs(files)
      setResult(res.data)
      setFiles([])
      if (res.data.inserted > 0) {
        setTimeout(onSuccess, 1500)
      }
    } catch (e) {
      setError(e.response?.data?.detail || e.message || 'Upload failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={styles.container}>
      <h2 className={styles.title}>Upload Bank Statements</h2>
      <p className={styles.subtitle}>Upload one or more PDF bank statements. Claude will extract and classify all transactions automatically.</p>

      <div
        className={`${styles.dropzone} ${dragging ? styles.dragging : ''}`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
      >
        <div className={styles.dropIcon}>📄</div>
        <p className={styles.dropText}>Drop PDF files here or <span className={styles.browse}>browse</span></p>
        <p className={styles.dropHint}>Supports: Revolut, Millennium BCP, Nu, Rappi, Banamex, HSBC, DolarApp</p>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf"
          multiple
          hidden
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>

      {files.length > 0 && (
        <div className={styles.fileList}>
          <h3 className={styles.fileListTitle}>Selected files ({files.length})</h3>
          {files.map(f => (
            <div key={f.name} className={styles.fileItem}>
              <span className={styles.fileIcon}>📋</span>
              <span className={styles.fileName}>{f.name}</span>
              <span className={styles.fileSize}>{(f.size / 1024).toFixed(0)} KB</span>
              <button className={styles.removeBtn} onClick={() => removeFile(f.name)}>✕</button>
            </div>
          ))}
        </div>
      )}

      <button
        className={styles.uploadBtn}
        onClick={handleUpload}
        disabled={!files.length || loading}
      >
        {loading ? '⏳ Processing with Claude...' : `Upload ${files.length} file${files.length !== 1 ? 's' : ''}`}
      </button>

      {loading && (
        <div className={styles.progress}>
          <div className={styles.spinner} />
          <p>Claude is reading your bank statements and classifying transactions…</p>
        </div>
      )}

      {result && (
        <div className={styles.resultCard}>
          <h3 className={styles.resultTitle}>✅ Upload complete</h3>
          <div className={styles.resultGrid}>
            <div className={styles.resultStat}>
              <span className={styles.statNum}>{result.inserted}</span>
              <span className={styles.statLabel}>Transactions added</span>
            </div>
            <div className={styles.resultStat}>
              <span className={styles.statNum}>{result.duplicates_skipped}</span>
              <span className={styles.statLabel}>Duplicates skipped</span>
            </div>
            <div className={styles.resultStat}>
              <span className={styles.statNum}>{result.ignored}</span>
              <span className={styles.statLabel}>Ignored (internal)</span>
            </div>
          </div>
          {result.errors?.length > 0 && (
            <div className={styles.errorList}>
              <strong>Errors:</strong>
              {result.errors.map((e, i) => <p key={i} className={styles.errorLine}>{e}</p>)}
            </div>
          )}
          {result.inserted > 0 && <p className={styles.redirect}>Redirecting to dashboard…</p>}
        </div>
      )}

      {error && (
        <div className={styles.errorCard}>
          <strong>Error:</strong> {error}
        </div>
      )}
    </div>
  )
}
