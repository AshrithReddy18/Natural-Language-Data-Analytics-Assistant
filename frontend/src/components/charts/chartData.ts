import type { Cell, ChartSpec, ColumnMeta, QueryResultData, ValueFormat } from '@/types/api'

/** Categorical slots in validated order. Colour follows the entity's position in a stable
 *  (sorted) order, never its rank, so filtering or re-sorting never repaints survivors. */
export const SERIES_COLORS = Array.from({ length: 8 }, (_, i) => `var(--series-${i + 1})`)
export const MAX_SERIES = 6

export interface SeriesDef {
  key: string
  label: string
  color: string
}

export interface ChartModel {
  data: Record<string, Cell>[]
  xKey: string
  series: SeriesDef[]
  xFormat: ValueFormat
  yFormat: ValueFormat
  truncatedTo: number | null
}

function column(result: QueryResultData, name: string | null): ColumnMeta | undefined {
  return result.columns.find((c) => c.name === name)
}

export function buildChartModel(spec: ChartSpec, result: QueryResultData): ChartModel | null {
  const x = column(result, spec.x)
  const measures = spec.y.map((name) => column(result, name)).filter((c): c is ColumnMeta => Boolean(c))
  if (!x || measures.length === 0) return null
  const xi = result.columns.indexOf(x)
  let rows = result.rows
  let truncatedTo: number | null = null
  if (spec.max_points && rows.length > spec.max_points) {
    rows = rows.slice(0, spec.max_points)
    truncatedTo = spec.max_points
  }

  const seriesCol = column(result, spec.series)
  if (seriesCol) {
    // Long → wide: one row per x value, one key per series value.
    const si = result.columns.indexOf(seriesCol)
    const mi = result.columns.indexOf(measures[0])
    const seriesValues = [...new Set(rows.map((r) => String(r[si])))]
      .sort((a, b) => a.localeCompare(b, undefined, { numeric: true }))
      .slice(0, MAX_SERIES)
    const byX = new Map<string, Record<string, Cell>>()
    for (const row of rows) {
      const xv = row[xi]
      const key = String(xv)
      if (!byX.has(key)) byX.set(key, { [x.name]: xv })
      const sv = String(row[si])
      if (seriesValues.includes(sv)) byX.get(key)![`s:${sv}`] = row[mi]
    }
    return {
      data: [...byX.values()],
      xKey: x.name,
      series: seriesValues.map((v, i) => ({ key: `s:${v}`, label: v, color: SERIES_COLORS[i] })),
      xFormat: x.format,
      yFormat: measures[0].format,
      truncatedTo,
    }
  }

  const indices = measures.map((m) => result.columns.indexOf(m))
  return {
    data: rows.map((row) => {
      const point: Record<string, Cell> = { [x.name]: row[xi] }
      measures.forEach((m, i) => (point[m.name] = row[indices[i]]))
      return point
    }),
    xKey: x.name,
    series: measures.map((m, i) => ({ key: m.name, label: humanizeKey(m.name), color: SERIES_COLORS[i] })),
    xFormat: x.format,
    yFormat: measures[0].format,
    truncatedTo,
  }
}

function humanizeKey(name: string): string {
  const text = name.replace(/_/g, ' ')
  return text.charAt(0).toUpperCase() + text.slice(1)
}
