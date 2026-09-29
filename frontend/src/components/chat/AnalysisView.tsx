import { Code2, HelpCircle, Info, SearchX, Table2 } from 'lucide-react'
import { ChartView } from '@/components/charts/ChartView'
import { Disclosure } from '@/components/common/Disclosure'
import { ErrorState } from '@/components/common/States'
import { InsightCard } from '@/components/data/InsightCard'
import { KpiCards } from '@/components/data/KpiCards'
import { ResultTable } from '@/components/data/ResultTable'
import { SqlPanel } from '@/components/sql/SqlPanel'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/primitives'
import { formatDuration } from '@/lib/format'
import type { AnalysisResult } from '@/types/api'

const ERROR_TITLES: Record<string, string> = {
  llm_not_configured: 'AI provider not configured',
  llm_unavailable: 'The AI model is unavailable',
  llm_bad_output: 'The AI response could not be used',
  sql_invalid: "I couldn't produce a valid query",
  query_failed: "The query couldn't be executed",
  query_timeout: 'The query took too long',
  datasource_unavailable: 'The database is unavailable',
}

export function AnalysisView({
  analysis,
  onAnswer,
  onRetry,
  interactive = true,
}: {
  analysis: AnalysisResult
  /** Sends a follow-up message (used by clarification options). */
  onAnswer?: (text: string) => void
  onRetry?: () => void
  interactive?: boolean
}) {
  const { status, result, chart, sql, currency } = analysis
  const showChart = status === 'success' && chart && result && !['kpi', 'table'].includes(chart.type)

  return (
    <div className="space-y-3">
      {status === 'clarification' && analysis.clarification && (
        <Card className="px-4 py-3.5">
          <div className="flex gap-3">
            <HelpCircle className="mt-0.5 size-4 shrink-0 text-accent" aria-hidden />
            <div className="min-w-0">
              <p className="text-[15px] text-fg">{analysis.clarification.question}</p>
              {analysis.clarification.options.length > 0 && interactive && onAnswer && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {analysis.clarification.options.map((o) => (
                    <Button key={o} size="sm" variant="outline" onClick={() => onAnswer(o)}>
                      {o}
                    </Button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </Card>
      )}

      {status === 'unanswerable' && (
        <Card className="flex gap-3 px-4 py-3.5">
          <Info className="mt-0.5 size-4 shrink-0 text-muted" aria-hidden />
          <div>
            <p className="text-sm font-medium text-fg">This data can't answer that question</p>
            <p className="mt-0.5 text-sm text-muted">{analysis.interpretation}</p>
          </div>
        </Card>
      )}

      {status === 'error' && analysis.error && (
        <ErrorState
          title={ERROR_TITLES[analysis.error.code] ?? 'Something went wrong'}
          message={analysis.error.message}
          onRetry={interactive ? onRetry : undefined}
        />
      )}

      {status === 'empty' && (
        <Card className="flex gap-3 px-4 py-3.5">
          <SearchX className="mt-0.5 size-4 shrink-0 text-muted" aria-hidden />
          <div>
            <p className="text-sm font-medium text-fg">No records matched the requested criteria</p>
            <p className="mt-0.5 text-sm text-muted">
              The query ran successfully but returned no rows. Try widening the date range or filters.
            </p>
          </div>
        </Card>
      )}

      {status === 'success' && <KpiCards kpis={analysis.kpis} currency={currency} />}

      {showChart && (
        <Card className="px-4 pb-3 pt-3.5">
          {analysis.title && <h3 className="mb-3 text-sm font-medium text-fg">{analysis.title}</h3>}
          <ChartView spec={chart} result={result} currency={currency} summary={analysis.insight?.headline} />
        </Card>
      )}

      {status === 'success' && analysis.insight && <InsightCard insight={analysis.insight} />}

      {sql && (
        <Disclosure
          title="Generated SQL"
          icon={<Code2 />}
          defaultOpen={status === 'empty' || status === 'error'}
          meta={
            result ? (
              <span className="truncate">
                {sql.validation.ok ? 'Validated' : 'Not validated'} · {result.row_count.toLocaleString()} rows ·{' '}
                {formatDuration(result.execution_ms)}
              </span>
            ) : (
              <span>{sql.validation.ok ? 'Validated' : 'Not validated'}</span>
            )
          }
        >
          <SqlPanel sql={sql} />
        </Disclosure>
      )}

      {result && result.row_count > 0 && (
        <Disclosure
          title="Data table"
          icon={<Table2 />}
          defaultOpen={chart?.type === 'table'}
          meta={`${result.columns.length} columns`}
        >
          <ResultTable result={result} currency={currency} filename={slug(analysis.title ?? 'result')} />
        </Disclosure>
      )}

      {(result || analysis.reasoning_summary) && (
        <Disclosure title="Query details" icon={<Info />}>
          <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-1.5 text-sm">
            {analysis.interpretation && <Detail label="Interpreted as" value={analysis.interpretation} />}
            {analysis.reasoning_summary && <Detail label="Approach" value={analysis.reasoning_summary} />}
            {result && <Detail label="Rows returned" value={`${result.row_count.toLocaleString()}${result.truncated ? ' (limit reached)' : ''}`} />}
            {result && <Detail label="Execution time" value={formatDuration(result.execution_ms)} />}
            {sql && <Detail label="Attempts" value={String(Math.max(1, sql.attempts.length))} />}
            {chart && <Detail label="Visualization" value={`${chart.type.replace('_', ' ')} — ${chart.reason}`} />}
            {analysis.query_run_id && <Detail label="Query ID" value={<code className="font-mono text-xs">{analysis.query_run_id}</code>} />}
          </dl>
        </Disclosure>
      )}
    </div>
  )
}

function Detail({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <>
      <dt className="text-subtle">{label}</dt>
      <dd className="min-w-0 break-words text-fg">{value}</dd>
    </>
  )
}

function slug(text: string): string {
  return text.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'result'
}
