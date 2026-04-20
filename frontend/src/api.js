import axios from 'axios'

const BASE = import.meta.env.VITE_API_URL || '/api'

const api = axios.create({ baseURL: BASE })

export const uploadPDFs = (files) => {
  const form = new FormData()
  files.forEach(f => form.append('files', f))
  return api.post('/upload', form, { headers: { 'Content-Type': 'multipart/form-data' } })
}

export const getTransactions = (params) => api.get('/transactions', { params })

export const createTransaction = (data) => api.post('/transactions', data)

export const updateTransaction = (id, data) => api.put(`/transactions/${id}`, data)

export const deleteTransaction = (id) => api.delete(`/transactions/${id}`)

export const getSummary = (month, year) => api.get('/summary', { params: { month, year } })

export const getBreakdown = (month, year) => api.get('/breakdown', { params: { month, year } })

export const getBanks = () => api.get('/banks')

export const getCategories = () => api.get('/categories')

export const bulkUpdateTransactions = (ids, fields) =>
  api.post('/transactions/bulk-update', { ids, ...fields })

export const getStatements = () => api.get('/statements')

export const deleteStatement = (id) => api.delete(`/statements/${id}`)

// ── Loans ─────────────────────────────────────────────────────────────────────

export const getLoans = () => api.get('/loans')

export const createLoan = (data) => api.post('/loans', data)

export const updateLoan = (id, data) => api.put(`/loans/${id}`, data)

export const deleteLoan = (id) => api.delete(`/loans/${id}`)

export const getLoanPayments = (loanId) => api.get(`/loans/${loanId}/payments`)

export const addLoanPayment = (loanId, data) => api.post(`/loans/${loanId}/payments`, data)

export const updateLoanPayment = (loanId, paymentId, data) =>
  api.put(`/loans/${loanId}/payments/${paymentId}`, data)

export const deleteLoanPayment = (loanId, paymentId) =>
  api.delete(`/loans/${loanId}/payments/${paymentId}`)
