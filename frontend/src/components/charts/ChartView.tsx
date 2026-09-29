import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell as PieCell,
  LabelList,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { formatValue } from '@/lib/format'
import { humanize } from '@/lib/utils'
import type { Cell, ChartSpec, QueryResultData, ValueFormat } from '@/types/api'
import { buildChartModel, SERIES_COLORS, type ChartModel, type SeriesDef } from './chartData'

const AXIS_TICK = { fill: 'var(--text-subtle)', fontSize: 11 }
const MARGIN = { top: 8, right: 16, bottom: 4, left: 4 }

interface TooltipEntry {
  dataKey?: string | number
  name?: string | number
  value?: Cell
  color?: string
  payload?: Record<string, Cell>
}

function ChartTooltip({
  active,
  payload,
  label,
  series,
  format,
  xFormat,
  currency,
}: {
  active?: boolean
  payload?: TooltipEntry[]
  label?: Cell
  series: SeriesDef[]
  format: ValueFormat
  xFormat: ValueFormat
  currency: string
}) {
  if (!active || !payload?.length) return null
  return (
    <div className="min-w-36 rounded-lg border border-border bg-surface px-3 py-2 text-xs shadow-xl">
      {label !== undefined && label !== null && (
        <div className="mb-1.5 font-medium text-fg">{formatValue(label, xFormat, currency)}</div>
      )}
      <div className="space-y-1">
        {payload.map((entry) => {
          const def = series.find((s) => s.key === entry.dataKey)
          return (
            <div key={String(entry.dataKey)} className="flex items-center justify-between gap-4">
              <span className="flex items-center gap-1.5 text-muted">
                <span className="size-2 rounded-full" style={{ background: def?.color ?? entry.color }} />
                {def?.label ?? entry.name}
              </span>
              <span className="font-medium tabular-nums text-fg">
                {formatValue(entry.value ?? null, format, currency)}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export function ChartLegend({ series }: { series: SeriesDef[] }) {
  if (series.length < 2) return null
  return (
    <ul className="mb-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted" aria-label="Legend">
      {series.map((s) => (
        <li key={s.key} className="flex items-center gap-1.5">
          <span className="h-0.5 w-3 rounded-full" style={{ background: s.color, height: 3 }} aria-hidden />
          {s.label}
        </li>
      ))}
    </ul>
  )
}

function truncate(label: string, max = 22): string {
  return label.length > max ? `${label.slice(0, max - 1)}…` : label
}

export function ChartView({
  spec,
  result,
  currency,
  summary,
}: {
  spec: ChartSpec
  result: QueryResultData
  currency: string
  /** Text alternative announced to screen readers. */
  summary?: string
}) {
  const model = buildChartModel(spec, result)
  if (!model) return null
  const label = `${humanize(spec.type.replace('_', ' '))} chart${spec.title ? `: ${spec.title}` : ''}. ${summary ?? ''}`

  return (
    <figure role="img" aria-label={label} className="w-full">
      <ChartLegend series={model.series} />
      <ChartBody spec={spec} model={model} currency={currency} />
      {model.truncatedTo && (
        <figcaption className="mt-2 text-xs text-subtle">
          Showing the first {model.truncatedTo} of {result.row_count} rows — see the data table for all.
        </figcaption>
      )}
    </figure>
  )
}

function ChartBody({ spec, model, currency }: { spec: ChartSpec; model: ChartModel; currency: string }) {
  const { data, xKey, series, xFormat, yFormat } = model
  const yTick = (v: number) => formatValue(v, yFormat, currency, true)
  const xTick = (v: Cell) => truncate(formatValue(v, xFormat, currency, true), 14)
  const tooltip = (
    <Tooltip
      cursor={{ fill: 'var(--surface-2)', stroke: 'var(--border-strong)' }}
      content={(props) => (
        <ChartTooltip
          {...(props as unknown as { active?: boolean; payload?: TooltipEntry[]; label?: Cell })}
          series={series}
          format={yFormat}
          xFormat={xFormat}
          currency={currency}
        />
      )}
    />
  )
  const grid = <CartesianGrid stroke="var(--grid)" vertical={false} />

  if (spec.type === 'line') {
    if (series.length === 1) {
      const s = series[0]
      return (
        <ResponsiveContainer width="100%" height={280}>
          <AreaChart data={data} margin={MARGIN}>
            <defs>
              <linearGradient id="area-wash" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={s.color} stopOpacity={0.18} />
                <stop offset="100%" stopColor={s.color} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            {grid}
            <XAxis dataKey={xKey} tick={AXIS_TICK} tickLine={false} axisLine={{ stroke: 'var(--border)' }} tickFormatter={xTick} minTickGap={16} />
            <YAxis tick={AXIS_TICK} tickLine={false} axisLine={false} tickFormatter={yTick} width={64} />
            {tooltip}
            <Area
              type="monotone"
              dataKey={s.key}
              name={s.label}
              stroke={s.color}
              strokeWidth={2}
              fill="url(#area-wash)"
              dot={data.length <= 16 ? { r: 3, fill: s.color, stroke: 'var(--surface)', strokeWidth: 2 } : false}
              activeDot={{ r: 5, fill: s.color, stroke: 'var(--surface)', strokeWidth: 2 }}
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      )
    }
    return (
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={data} margin={MARGIN}>
          {grid}
          <XAxis dataKey={xKey} tick={AXIS_TICK} tickLine={false} axisLine={{ stroke: 'var(--border)' }} tickFormatter={xTick} minTickGap={16} />
          <YAxis tick={AXIS_TICK} tickLine={false} axisLine={false} tickFormatter={yTick} width={64} />
          {tooltip}
          {series.map((s) => (
            <Line
              key={s.key}
              type="monotone"
              dataKey={s.key}
              name={s.label}
              stroke={s.color}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 5, fill: s.color, stroke: 'var(--surface)', strokeWidth: 2 }}
              connectNulls
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    )
  }

  if (spec.type === 'horizontal_bar') {
    const longest = Math.max(...data.map((d) => truncate(String(d[xKey])).length))
    const labelWidth = Math.min(180, Math.max(64, longest * 7 + 16))
    const showValues = data.length <= 15 && series.length === 1
    return (
      <ResponsiveContainer width="100%" height={Math.max(160, data.length * (series.length > 1 ? 44 : 32) + 32)}>
        <BarChart data={data} layout="vertical" margin={{ ...MARGIN, right: showValues ? 56 : 16 }} barCategoryGap="22%">
          <CartesianGrid stroke="var(--grid)" horizontal={false} />
          <XAxis type="number" tick={AXIS_TICK} tickLine={false} axisLine={false} tickFormatter={yTick} />
          <YAxis
            type="category"
            dataKey={xKey}
            tick={{ ...AXIS_TICK, fill: 'var(--text-muted)' }}
            tickLine={false}
            axisLine={{ stroke: 'var(--border)' }}
            width={labelWidth}
            tickFormatter={(v: Cell) => truncate(String(v))}
            interval={0}
          />
          {tooltip}
          {series.map((s) => (
            <Bar key={s.key} dataKey={s.key} name={s.label} fill={s.color} radius={[0, 4, 4, 0]} maxBarSize={24} isAnimationActive={false}>
              {showValues && (
                <LabelList
                  dataKey={s.key}
                  position="right"
                  formatter={(v: unknown) => formatValue(v as Cell, yFormat, currency, true)}
                  style={{ fill: 'var(--text-muted)', fontSize: 11 }}
                />
              )}
            </Bar>
          ))}
        </BarChart>
      </ResponsiveContainer>
    )
  }

  if (spec.type === 'bar') {
    return (
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={data} margin={MARGIN} barCategoryGap="24%" barGap={2}>
          {grid}
          <XAxis dataKey={xKey} tick={AXIS_TICK} tickLine={false} axisLine={{ stroke: 'var(--border)' }} tickFormatter={xTick} interval={data.length > 12 ? 'preserveStartEnd' : 0} />
          <YAxis tick={AXIS_TICK} tickLine={false} axisLine={false} tickFormatter={yTick} width={64} />
          {tooltip}
          {series.map((s) => (
            <Bar key={s.key} dataKey={s.key} name={s.label} fill={s.color} radius={[4, 4, 0, 0]} maxBarSize={24} isAnimationActive={false} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    )
  }

  if (spec.type === 'donut') {
    const s = series[0]
    const total = data.reduce((sum, d) => sum + (typeof d[s.key] === 'number' ? (d[s.key] as number) : 0), 0)
    return (
      <div className="flex flex-col items-center gap-4 sm:flex-row sm:gap-8">
        <div className="h-52 w-52 shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                dataKey={s.key}
                nameKey={xKey}
                innerRadius="62%"
                outerRadius="92%"
                stroke="var(--surface)"
                strokeWidth={2}
                isAnimationActive={false}
              >
                {data.map((_, i) => (
                  <PieCell key={i} fill={SERIES_COLORS[i % SERIES_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                content={(props) => {
                  const p = props as unknown as { active?: boolean; payload?: TooltipEntry[] }
                  const entry = p.payload?.[0]
                  if (!p.active || !entry) return null
                  return (
                    <div className="rounded-lg border border-border bg-surface px-3 py-2 text-xs shadow-xl">
                      <div className="font-medium text-fg">{String(entry.name)}</div>
                      <div className="tabular-nums text-muted">{formatValue(entry.value ?? null, yFormat, currency)}</div>
                    </div>
                  )
                }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <ul className="w-full max-w-xs space-y-1.5 text-sm" aria-label="Legend">
          {data.map((d, i) => {
            const value = typeof d[s.key] === 'number' ? (d[s.key] as number) : 0
            return (
              <li key={String(d[xKey])} className="flex items-center gap-2">
                <span className="size-2.5 shrink-0 rounded-sm" style={{ background: SERIES_COLORS[i % SERIES_COLORS.length] }} aria-hidden />
                <span className="min-w-0 flex-1 truncate text-muted">{String(d[xKey])}</span>
                <span className="tabular-nums text-fg">{formatValue(value, yFormat, currency, true)}</span>
                {yFormat !== 'percent' && total > 0 && (
                  <span className="w-12 text-right text-xs tabular-nums text-subtle">{((value / total) * 100).toFixed(1)}%</span>
                )}
              </li>
            )
          })}
        </ul>
      </div>
    )
  }

  if (spec.type === 'scatter') {
    const s = series[0]
    return (
      <ResponsiveContainer width="100%" height={300}>
        <ScatterChart margin={{ ...MARGIN, bottom: 16 }}>
          <CartesianGrid stroke="var(--grid)" />
          <XAxis
            type="number"
            dataKey={xKey}
            name={humanize(xKey)}
            tick={AXIS_TICK}
            tickLine={false}
            axisLine={{ stroke: 'var(--border)' }}
            tickFormatter={(v: number) => formatValue(v, xFormat, currency, true)}
            label={{ value: humanize(xKey), position: 'insideBottom', offset: -10, fill: 'var(--text-subtle)', fontSize: 11 }}
          />
          <YAxis type="number" dataKey={s.key} name={s.label} tick={AXIS_TICK} tickLine={false} axisLine={false} tickFormatter={yTick} width={64} />
          <Tooltip
            cursor={{ stroke: 'var(--border-strong)' }}
            content={(props) => {
              const p = props as unknown as { active?: boolean; payload?: TooltipEntry[] }
              const point = p.payload?.[0]?.payload
              if (!p.active || !point) return null
              return (
                <div className="rounded-lg border border-border bg-surface px-3 py-2 text-xs shadow-xl tabular-nums">
                  <div className="text-muted">{humanize(xKey)}: <span className="text-fg">{formatValue(point[xKey], xFormat, currency)}</span></div>
                  <div className="text-muted">{s.label}: <span className="text-fg">{formatValue(point[s.key], yFormat, currency)}</span></div>
                </div>
              )
            }}
          />
          <Scatter data={data} fill={s.color} stroke="var(--surface)" strokeWidth={2} isAnimationActive={false} />
        </ScatterChart>
      </ResponsiveContainer>
    )
  }

  return null
}
