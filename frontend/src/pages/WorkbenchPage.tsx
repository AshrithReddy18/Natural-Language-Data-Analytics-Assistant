import { useMutation } from '@tanstack/react-query'
import { useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, CircleAlert, Loader2, Play, ShieldCheck, SquareTerminal } from 'lucide-react'
import { useEffect, useState, type KeyboardEvent } from 'react'
import { AnalysisView } from '@/components/chat/AnalysisView'
import { EmptyState, ErrorState } from '@/components/common/States'
import { SqlCode } from '@/components/sql/SqlCode'
import { Button } from '@/components/ui/button'
import { Badge, Card, Kbd } from '@/components/ui/primitives'
import { useActiveDataSource } from '@/hooks/queries'
import { api, ApiError } from '@/services/api'
import { useUIStore } from '@/store/ui'

type Dialect = 'sqlite' | 'postgresql'

const month = (d: Dialect, col: string) => (d === 'postgresql' ? `to_char(${col}, 'YYYY-MM')` : `strftime('%Y-%m', ${col})`)

const EXAMPLES: { label: string; sql: (d: Dialect) => string }[] = [
  {
    label: 'Monthly revenue, 2025',
    sql: (d) => `SELECT ${month(d, 'o.order_date')} AS month,
       ROUND(SUM(oi.line_total), 2) AS revenue
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
WHERE o.status IN ('delivered', 'shipped')
  AND o.order_date >= '2025-01-01'
GROUP BY 1
ORDER BY 1;`,
  },
  {
    label: 'Revenue by category',
    sql: () => `SELECT p.category,
       ROUND(SUM(oi.line_total), 2) AS revenue
FROM order_items oi
JOIN products p ON p.product_id = oi.product_id
JOIN orders o ON o.order_id = oi.order_id
WHERE o.status IN ('delivered', 'shipped')
GROUP BY p.category
ORDER BY revenue DESC;`,
  },
  {
    label: 'Payment mix',
    sql: () => `SELECT payment_method,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM payments), 1) AS share_pct
FROM payments
GROUP BY payment_method
ORDER BY share_pct DESC;`,
  },
]

export default function WorkbenchPage() {
  const { source } = useActiveDataSource()
  const handoff = useUIStore((s) => s.workbenchSql)
  const setHandoff = useUIStore((s) => s.setWorkbenchSql)
  const dialect: Dialect = source?.kind === 'postgresql' ? 'postgresql' : 'sqlite'
  const [sql, setSql] = useState(() => handoff || EXAMPLES[0].sql(dialect))
  const qc = useQueryClient()

  // The initial state above consumed any SQL handed over from history / the schema explorer.
  useEffect(() => {
    if (handoff) setHandoff('')
  }, [handoff, setHandoff])

  const validate = useMutation({ mutationFn: () => api.validateSql(source!.id, sql) })
  const run = useMutation({
    mutationFn: () => api.executeSql(source!.id, sql),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['history'] }),
  })
  const busy = validate.isPending || run.isPending

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault()
      if (source && sql.trim()) run.mutate()
    } else if (e.key === 'Tab' && !e.shiftKey) {
      e.preventDefault()
      const t = e.currentTarget
      const { selectionStart: s, selectionEnd: end } = t
      setSql(sql.slice(0, s) + '  ' + sql.slice(end))
      requestAnimationFrame(() => t.setSelectionRange(s + 2, s + 2))
    }
  }

  const mutationError = (validate.error ?? run.error) as ApiError | Error | null

  return (
    <div className="mx-auto w-full max-w-5xl space-y-5 px-4 py-6 sm:px-6">
      <div>
        <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight text-fg">
          <SquareTerminal className="size-5 text-accent" aria-hidden /> SQL workbench
        </h1>
        <p className="mt-1 text-sm text-muted">
          Write SQL by hand. It passes through the same validator, read-only executor and analytics as AI-generated queries.
        </p>
      </div>

      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-center gap-2 border-b border-border px-3 py-2">
          <span className="text-xs text-subtle">Examples:</span>
          {EXAMPLES.map((ex) => (
            <button
              key={ex.label}
              type="button"
              onClick={() => setSql(ex.sql(dialect))}
              className="rounded-md px-2 py-1 text-xs text-muted hover:bg-surface-2 hover:text-fg cursor-pointer"
            >
              {ex.label}
            </button>
          ))}
          {source?.kind === 'postgresql' && <Badge className="ml-auto">PostgreSQL dialect</Badge>}
        </div>
        <label htmlFor="sql-editor" className="sr-only">
          SQL query
        </label>
        <textarea
          id="sql-editor"
          value={sql}
          onChange={(e) => setSql(e.target.value)}
          onKeyDown={onKeyDown}
          spellCheck={false}
          rows={Math.min(18, Math.max(8, sql.split('\n').length + 1))}
          className="block w-full resize-y bg-surface px-4 py-3 font-mono text-[13px] leading-relaxed text-fg focus:outline-none focus-visible:outline-none"
        />
        <div className="flex flex-wrap items-center gap-2 border-t border-border px-3 py-2">
          <span className="hidden items-center gap-1 text-xs text-subtle sm:flex">
            <Kbd>Ctrl</Kbd> + <Kbd>Enter</Kbd> to run
          </span>
          <div className="ml-auto flex gap-2">
            <Button size="sm" variant="secondary" onClick={() => validate.mutate()} disabled={!source || !sql.trim() || busy}>
              {validate.isPending ? <Loader2 className="animate-spin" /> : <ShieldCheck />} Validate
            </Button>
            <Button size="sm" variant="primary" onClick={() => run.mutate()} disabled={!source || !sql.trim() || busy}>
              {run.isPending ? <Loader2 className="animate-spin" /> : <Play />} Run query
            </Button>
          </div>
        </div>
      </Card>

      {mutationError && <ErrorState message={mutationError.message} />}

      {validate.data && !run.data && (
        <Card className="space-y-3 px-4 py-3.5">
          <div className="flex items-center gap-2 text-sm font-medium">
            {validate.data.validation.ok ? (
              <>
                <CheckCircle2 className="size-4 text-success" aria-hidden /> Valid read-only query
              </>
            ) : (
              <>
                <CircleAlert className="size-4 text-danger" aria-hidden /> Validation failed
              </>
            )}
          </div>
          {validate.data.validation.errors.map((e) => (
            <p key={e} className="text-sm text-danger">{e}</p>
          ))}
          {validate.data.validation.warnings.map((w) => (
            <p key={w} className="text-sm text-warning">{w}</p>
          ))}
          {validate.data.validated_sql && (
            <>
              <p className="text-xs text-subtle">The SQL that would be executed:</p>
              <SqlCode sql={validate.data.validated_sql} />
            </>
          )}
        </Card>
      )}

      {run.data ? (
        <AnalysisView analysis={run.data} interactive={false} />
      ) : (
        !validate.data &&
        !mutationError && (
          <EmptyState
            icon={<Play />}
            title="Run a query to see results"
            description="Results are charted automatically, with computed KPIs and facts."
          />
        )
      )}
    </div>
  )
}
