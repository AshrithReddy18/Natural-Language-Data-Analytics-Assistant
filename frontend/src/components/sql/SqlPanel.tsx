import { CheckCircle2, CircleAlert, RotateCcw, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { Badge } from '@/components/ui/primitives'
import { normalizeSql } from '@/lib/sql'
import { cn } from '@/lib/utils'
import type { SQLInfo } from '@/types/api'
import { CopyButton, SqlCode } from './SqlCode'

/** Generated vs validated SQL, validation outcome, and any failed attempts that were repaired. */
export function SqlPanel({ sql }: { sql: SQLInfo }) {
  const differs = Boolean(sql.validated_sql) && normalizeSql(sql.validated_sql ?? '') !== normalizeSql(sql.generated_sql)
  const [view, setView] = useState<'validated' | 'generated'>(sql.validated_sql ? 'validated' : 'generated')
  const shown = view === 'validated' && sql.validated_sql ? sql.validated_sql : sql.generated_sql
  const failed = sql.attempts.filter((a) => a.stage !== 'success')

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        {sql.validation.ok ? (
          <Badge tone="success">
            <ShieldCheck /> Validated read-only
          </Badge>
        ) : (
          <Badge tone="danger">
            <CircleAlert /> Failed validation
          </Badge>
        )}
        <Badge>{sql.dialect}</Badge>
        {sql.validation.tables.length > 0 && <Badge>Tables: {sql.validation.tables.join(', ')}</Badge>}
        {sql.validation.limit_applied && <Badge tone="warning">LIMIT {sql.validation.limit_applied} enforced</Badge>}
        <div className="ml-auto flex items-center gap-1">
          {differs && (
            <div role="tablist" aria-label="SQL version" className="flex rounded-lg border border-border p-0.5 text-xs">
              {(['validated', 'generated'] as const).map((v) => (
                <button
                  key={v}
                  role="tab"
                  type="button"
                  aria-selected={view === v}
                  onClick={() => setView(v)}
                  className={cn(
                    'rounded-md px-2 py-0.5 capitalize cursor-pointer',
                    view === v ? 'bg-surface-3 text-fg' : 'text-subtle hover:text-muted',
                  )}
                >
                  {v === 'generated' ? 'As generated' : 'Validated'}
                </button>
              ))}
            </div>
          )}
          <CopyButton text={shown} />
        </div>
      </div>

      <SqlCode sql={shown} />

      {sql.validation.warnings.map((w) => (
        <p key={w} className="text-xs text-warning">
          {w}
        </p>
      ))}
      {sql.validation.errors.map((e) => (
        <p key={e} className="text-xs text-danger">
          {e}
        </p>
      ))}

      {failed.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center gap-1.5 text-xs font-medium text-muted">
            <RotateCcw className="size-3.5" aria-hidden />
            {sql.validation.ok ? `Self-corrected after ${failed.length} failed attempt${failed.length > 1 ? 's' : ''}` : 'Attempts'}
          </div>
          <ol className="space-y-2">
            {sql.attempts.map((a, i) => (
              <li key={i} className="rounded-lg border border-border px-3 py-2 text-xs">
                <div className="flex items-start gap-2">
                  {a.stage === 'success' ? (
                    <CheckCircle2 className="mt-0.5 size-3.5 shrink-0 text-success" aria-hidden />
                  ) : (
                    <CircleAlert className="mt-0.5 size-3.5 shrink-0 text-warning" aria-hidden />
                  )}
                  <div className="min-w-0">
                    <span className="font-medium text-fg">Attempt {i + 1}</span>{' '}
                    <span className="text-muted">
                      {a.stage === 'success' ? 'succeeded' : `failed during ${a.stage}`}
                      {a.error ? `: ${a.error}` : ''}
                    </span>
                  </div>
                </div>
                {a.stage !== 'success' && (
                  <details className="mt-1.5">
                    <summary className="cursor-pointer text-subtle hover:text-muted">Show SQL</summary>
                    <SqlCode sql={a.sql} className="mt-1.5" maxHeight="max-h-48" />
                  </details>
                )}
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  )
}
