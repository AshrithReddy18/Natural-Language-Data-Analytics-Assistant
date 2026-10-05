import type { Cell, ValueFormat } from '@/types/api'

const CURRENCY_SYMBOLS: Record<string, string> = { INR: '₹', USD: '$', EUR: '€', GBP: '£', JPY: '¥' }

export function currencySymbol(code: string): string {
  return CURRENCY_SYMBOLS[code] ?? `${code} `
}

const compactFmt = new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 2 })
const intFmt = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 })
const decFmt = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 })

export function compact(value: number): string {
  return Math.abs(value) >= 1000 ? compactFmt.format(value) : decFmt.format(value)
}

/** Format a value for display. `compactNumbers` is for KPIs, axes and chart labels. */
export function formatValue(value: Cell, format: ValueFormat, currency = 'INR', compactNumbers = false): string {
  if (value === null || value === undefined) return '—'
  if (typeof value !== 'number') return String(value)
  switch (format) {
    case 'currency':
      return currencySymbol(currency) + (compactNumbers ? compact(value) : decFmt.format(value))
    case 'percent':
      return `${decFmt.format(Math.round(value * 10) / 10)}%`
    case 'integer':
      return compactNumbers && Math.abs(value) >= 100_000 ? compact(value) : intFmt.format(value)
    default:
      return compactNumbers ? compact(value) : decFmt.format(value)
  }
}

export function formatDuration(ms: number): string {
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`
}

const SOURCE_KINDS: Record<string, string> = { postgresql: 'PostgreSQL', sqlite: 'SQLite', upload: 'Uploaded files' }

export const sourceKindLabel = (kind: string) => SOURCE_KINDS[kind] ?? kind

export const tableCountLabel = (n: number) => `${n} ${n === 1 ? 'table' : 'tables'}`
