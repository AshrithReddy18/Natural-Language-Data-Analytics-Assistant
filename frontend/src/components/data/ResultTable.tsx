import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight, Download } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Button } from '@/components/ui/button'
import { formatValue } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { Cell, QueryResultData } from '@/types/api'

const PAGE_SIZE = 25

function compare(a: Cell, b: Cell): number {
  if (a === b) return 0
  if (a === null) return 1
  if (b === null) return -1
  if (typeof a === 'number' && typeof b === 'number') return a - b
  return String(a).localeCompare(String(b), undefined, { numeric: true })
}

function toCsv(result: QueryResultData): string {
  const escape = (v: Cell) => {
    const s = v === null ? '' : String(v)
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
  }
  return [result.columns.map((c) => escape(c.name)).join(','), ...result.rows.map((r) => r.map(escape).join(','))].join(
    '\n',
  )
}

export function ResultTable({ result, currency, filename = 'datapilot-result' }: {
  result: QueryResultData
  currency: string
  filename?: string
}) {
  const [sort, setSort] = useState<{ index: number; dir: 1 | -1 } | null>(null)
  const [page, setPage] = useState(0)

  const rows = useMemo(() => {
    if (!sort) return result.rows
    return [...result.rows].sort((a, b) => compare(a[sort.index], b[sort.index]) * sort.dir)
  }, [result.rows, sort])

  const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE))
  const visible = rows.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)
  const numeric = result.columns.map((c) => c.kind === 'numeric')

  const toggleSort = (index: number) => {
    setPage(0)
    setSort((s) => (s?.index !== index ? { index, dir: numeric[index] ? -1 : 1 } : s.dir === 1 ? { index, dir: -1 } : null))
  }

  const download = () => {
    const blob = new Blob([toCsv(result)], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${filename}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div>
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full min-w-max border-collapse text-[13px]">
          <caption className="sr-only">
            Query result: {result.row_count} rows, {result.columns.length} columns
          </caption>
          <thead className="bg-surface-2">
            <tr>
              {result.columns.map((col, i) => {
                const active = sort?.index === i
                return (
                  <th
                    key={col.name}
                    scope="col"
                    aria-sort={active ? (sort.dir === 1 ? 'ascending' : 'descending') : 'none'}
                    className={cn('border-b border-border px-3 py-2 font-medium text-muted', numeric[i] ? 'text-right' : 'text-left')}
                  >
                    <button
                      type="button"
                      onClick={() => toggleSort(i)}
                      className={cn('inline-flex items-center gap-1 hover:text-fg cursor-pointer', numeric[i] && 'flex-row-reverse')}
                    >
                      {col.name}
                      {active ? (
                        sort.dir === 1 ? <ArrowUp className="size-3" aria-hidden /> : <ArrowDown className="size-3" aria-hidden />
                      ) : (
                        <span className="size-3" aria-hidden />
                      )}
                    </button>
                  </th>
                )
              })}
            </tr>
          </thead>
          <tbody>
            {visible.map((row, ri) => (
              <tr key={page * PAGE_SIZE + ri} className="border-b border-border last:border-0 hover:bg-surface-2/60">
                {row.map((cell, ci) => (
                  <td
                    key={ci}
                    className={cn(
                      'max-w-[28rem] truncate px-3 py-1.5 text-fg',
                      numeric[ci] && 'text-right tabular-nums',
                      cell === null && 'text-subtle',
                    )}
                    title={cell === null ? 'NULL' : String(cell)}
                  >
                    {cell === null ? 'NULL' : formatValue(cell, result.columns[ci].format, currency)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs text-subtle">
        <span>
          {result.row_count.toLocaleString()} {result.row_count === 1 ? 'row' : 'rows'}
          {result.truncated && ' (limit reached — more rows exist)'}
        </span>
        <div className="flex items-center gap-1">
          {pages > 1 && (
            <>
              <Button variant="ghost" size="icon-sm" onClick={() => setPage((p) => p - 1)} disabled={page === 0} aria-label="Previous page">
                <ChevronLeft />
              </Button>
              <span className="tabular-nums">
                Page {page + 1} of {pages}
              </span>
              <Button variant="ghost" size="icon-sm" onClick={() => setPage((p) => p + 1)} disabled={page >= pages - 1} aria-label="Next page">
                <ChevronRight />
              </Button>
            </>
          )}
          <Button variant="ghost" size="sm" onClick={download}>
            <Download /> CSV
          </Button>
        </div>
      </div>
    </div>
  )
}
