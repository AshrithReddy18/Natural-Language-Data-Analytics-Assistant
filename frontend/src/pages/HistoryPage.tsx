import { History, MessageSquare, SquareTerminal } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { EmptyState, ErrorState, LoadingRows } from '@/components/common/States'
import { Badge, Card } from '@/components/ui/primitives'
import { useDatasets, useHistory } from '@/hooks/queries'
import { formatDuration } from '@/lib/format'
import { relativeTime } from '@/lib/time'
import { cn } from '@/lib/utils'
import { useUIStore } from '@/store/ui'
import type { QueryRun } from '@/types/api'

const FILTERS = ['all', 'success', 'failed'] as const

function StatusBadge({ status }: { status: string }) {
  if (status === 'success') return <Badge tone="success">Success</Badge>
  if (status === 'timeout') return <Badge tone="warning">Timeout</Badge>
  return <Badge tone="danger">Failed</Badge>
}

export default function HistoryPage() {
  const { data, isLoading, error, refetch } = useHistory()
  const { data: sources } = useDatasets()
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>('all')
  const navigate = useNavigate()
  const setWorkbenchSql = useUIStore((s) => s.setWorkbenchSql)
  const setSelected = useUIStore((s) => s.setDataSourceId)

  const runs = (data ?? []).filter((r) => filter === 'all' || (filter === 'success' ? r.status === 'success' : r.status !== 'success'))
  const sourceName = (id: string) => sources?.find((s) => s.id === id)?.name ?? 'Unknown source'

  const open = (run: QueryRun) => {
    if (run.conversation_id) {
      navigate(`/c/${run.conversation_id}`)
    } else {
      setSelected(run.data_source_id)
      setWorkbenchSql(run.generated_sql ?? run.validated_sql ?? '')
      navigate('/sql')
    }
  }

  return (
    <div className="mx-auto w-full max-w-5xl space-y-5 px-4 py-6 sm:px-6">
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex-1">
          <h1 className="text-xl font-semibold tracking-tight text-fg">Query history</h1>
          <p className="mt-1 text-sm text-muted">Every query DataPilot ran, from chat and the SQL workbench. Select one to reopen it.</p>
        </div>
        <div role="tablist" aria-label="Filter by status" className="flex rounded-lg border border-border p-0.5 text-sm">
          {FILTERS.map((f) => (
            <button
              key={f}
              role="tab"
              type="button"
              aria-selected={filter === f}
              onClick={() => setFilter(f)}
              className={cn('rounded-md px-3 py-1 capitalize cursor-pointer', filter === f ? 'bg-surface-3 text-fg' : 'text-muted hover:text-fg')}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {isLoading && <LoadingRows rows={6} />}
      {error && <ErrorState message={error.message} onRetry={() => refetch()} />}
      {data && runs.length === 0 && (
        <EmptyState icon={<History />} title="No queries yet" description="Ask a question or run SQL in the workbench — it will show up here." />
      )}
      {runs.length > 0 && (
        <Card className="divide-y divide-border overflow-hidden">
          {runs.map((run) => (
            <button
              key={run.id}
              type="button"
              onClick={() => open(run)}
              className="flex w-full items-start gap-3 px-4 py-3 text-left transition-colors hover:bg-surface-2/60 cursor-pointer"
            >
              <div className="mt-0.5 text-subtle" aria-hidden>
                {run.source === 'chat' ? <MessageSquare className="size-4" /> : <SquareTerminal className="size-4" />}
              </div>
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium text-fg">
                  {run.question ?? <span className="font-mono text-[13px]">{(run.generated_sql ?? '').replace(/\s+/g, ' ').slice(0, 90)}</span>}
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-subtle">
                  <StatusBadge status={run.status} />
                  <span>{sourceName(run.data_source_id)}</span>
                  {run.row_count !== null && <span>· {run.row_count.toLocaleString()} rows</span>}
                  {run.execution_ms !== null && <span>· {formatDuration(run.execution_ms)}</span>}
                  {run.attempts > 1 && <span>· {run.attempts} attempts</span>}
                </div>
                {run.error_message && <p className="mt-1 truncate text-xs text-danger">{run.error_message}</p>}
              </div>
              <time dateTime={run.created_at} className="shrink-0 text-xs text-subtle">
                {relativeTime(run.created_at)}
              </time>
            </button>
          ))}
        </Card>
      )}
    </div>
  )
}
