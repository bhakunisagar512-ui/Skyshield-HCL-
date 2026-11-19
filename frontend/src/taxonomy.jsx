import { createContext, useContext, useEffect, useState } from 'react'
import { api } from './api'

const TaxonomyContext = createContext(null)

export function TaxonomyProvider({ children }) {
  const [tax, setTax] = useState(null)
  useEffect(() => {
    api('/meta/taxonomy').then(setTax).catch(() => setTax({ error: true }))
  }, [])
  return <TaxonomyContext.Provider value={tax}>{children}</TaxonomyContext.Provider>
}

export function useTaxonomy() {
  const tax = useContext(TaxonomyContext)
  const categoryLabel = (code) => tax?.categories?.find((c) => c.code === code)?.label || code
  const airportLabel = (code) => {
    const a = tax?.airports?.find((x) => x.code === code)
    return a ? `${a.city} (${code})` : code
  }
  const operatorLabel = (code) => tax?.operators?.find((o) => o.code === code)?.name || code
  return { tax, categoryLabel, airportLabel, operatorLabel }
}

export const humanize = (s) => (s ? s.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase()) : '')

export function formatDate(iso, withTime = true) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleString('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric',
    ...(withTime ? { hour: '2-digit', minute: '2-digit' } : {}),
  })
}
