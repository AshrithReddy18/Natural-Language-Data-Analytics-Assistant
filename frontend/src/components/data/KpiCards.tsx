import { ArrowDownRight, ArrowUpRight } from 'lucide-react'
import { formatValue } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { Kpi } from '@/types/api'

export function KpiCard({ kpi, currency }: { kpi: Kpi; currency: string }) {
  const isText = typeof kpi.value === 'string'
  const up = (kpi.delta_pct ?? 0) >= 0
  return (
    <div className="min-w-0 rounded-xl border border-border bg-surface px-4 py-3">
      <div className="truncate text-xs font-medium text-muted first-letter:uppercase">{kpi.label}</div>
      <div
        className={cn('mt-1 truncate font-semibold tracking-tight text-fg', isText ? 'text-lg' : 'text-2xl tabular-nums')}
        title={String(kpi.value)}
      >
        {isText ? kpi.value : formatValue(kpi.value, kpi.format, currency, true)}
      </div>
      {(kpi.delta_pct !== null || kpi.delta_label) && (
        <div className="mt-1 flex items-center gap-1.5 text-xs">
          {kpi.delta_pct !== null && (
            <span
              className={cn(
                'inline-flex items-center gap-0.5 rounded px-1 py-0.5 font-medium tabular-nums',
                up ? 'bg-success-soft text-success' : 'bg-danger-soft text-danger',
              )}
            >
              {up ? <ArrowUpRight className="size-3" aria-hidden /> : <ArrowDownRight className="size-3" aria-hidden />}
              <span className="sr-only">{up ? 'Up' : 'Down'}</span>
              {Math.abs(kpi.delta_pct).toFixed(1)}%
            </span>
          )}
          {kpi.delta_label && <span className="truncate text-subtle">{kpi.delta_label}</span>}
        </div>
      )}
    </div>
  )
}

export function KpiCards({ kpis, currency }: { kpis: Kpi[]; currency: string }) {
  if (!kpis.length) return null
  return (
    <div
      className={cn(
        'grid gap-3',
        kpis.length === 1 ? 'grid-cols-1 sm:max-w-xs' : kpis.length === 2 ? 'grid-cols-2' : 'grid-cols-2 lg:grid-cols-4',
        kpis.length === 3 && 'lg:grid-cols-3',
      )}
    >
      {kpis.map((kpi) => (
        <KpiCard key={kpi.label} kpi={kpi} currency={currency} />
      ))}
    </div>
  )
}
