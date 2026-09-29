import { buildChartModel } from '@/components/charts/chartData'
import { formatValue } from '@/lib/format'
import { normalizeSql, tokenLines, tokenizeSql } from '@/lib/sql'
import { dateGroup } from '@/lib/time'
import { useChatStore } from '@/store/chat'
import type { QueryResultData } from '@/types/api'

describe('formatValue', () => {
  it('formats currency, percent and integers', () => {
    expect(formatValue(2412300, 'currency', 'INR', true)).toBe('₹2.41M')
    expect(formatValue(1234.5, 'currency', 'USD')).toBe('$1,234.5')
    expect(formatValue(33.44, 'percent')).toBe('33.4%')
    expect(formatValue(48293, 'integer')).toBe('48,293')
    expect(formatValue(null, 'number')).toBe('—')
    expect(formatValue('Pune', 'text')).toBe('Pune')
  })
})

describe('SQL tokenizer', () => {
  it('classifies keywords, functions, strings, numbers and comments', () => {
    const types = Object.fromEntries(
      tokenizeSql("SELECT SUM(x) FROM t WHERE s = 'it''s' AND n > 10 -- note")
        .filter((t) => t.type !== 'space')
        .map((t) => [t.text, t.type]),
    )
    expect(types.SELECT).toBe('keyword')
    expect(types.SUM).toBe('function')
    expect(types["'it''s'"]).toBe('string')
    expect(types['10']).toBe('number')
    expect(types['-- note']).toBe('comment')
    expect(types.x).toBe('identifier')
  })

  it('splits into lines for line numbers', () => {
    expect(tokenLines('SELECT 1\nFROM t\n')).toHaveLength(3)
  })

  it('normalizes for comparison', () => {
    expect(normalizeSql('SELECT  a\nFROM t;')).toBe(normalizeSql('select a from t'))
  })
})

describe('buildChartModel', () => {
  const result: QueryResultData = {
    columns: [
      { name: 'month', kind: 'temporal', format: 'integer', distinct_count: 2, null_count: 0 },
      { name: 'year', kind: 'temporal', format: 'integer', distinct_count: 2, null_count: 0 },
      { name: 'revenue', kind: 'numeric', format: 'currency', distinct_count: 4, null_count: 0 },
    ],
    rows: [
      [1, 2025, 12],
      [1, 2024, 10],
      [2, 2024, 11],
      [2, 2025, 15],
    ],
    row_count: 4,
    truncated: false,
    execution_ms: 1,
  }

  it('pivots a series column into one key per series, colored in stable order', () => {
    const model = buildChartModel({ type: 'line', x: 'month', y: ['revenue'], series: 'year', title: '', reason: '', max_points: null }, result)!
    expect(model.series.map((s) => s.label)).toEqual(['2024', '2025'])
    expect(model.series[0].color).toBe('var(--series-1)')
    expect(model.data).toEqual([
      { month: 1, 's:2025': 12, 's:2024': 10 },
      { month: 2, 's:2024': 11, 's:2025': 15 },
    ])
  })

  it('limits points when max_points is set', () => {
    const model = buildChartModel({ type: 'bar', x: 'month', y: ['revenue'], series: null, title: '', reason: '', max_points: 2 }, result)!
    expect(model.data).toHaveLength(2)
    expect(model.truncatedTo).toBe(2)
  })
})

describe('chat store', () => {
  beforeEach(() => useChatStore.getState().clear())

  it('records a recovered validation error as a note when the query is regenerated', () => {
    const s = useChatStore.getState()
    s.start('q', null)
    s.updateStep('generate', 'running', null)
    s.updateStep('generate', 'done', null)
    s.updateStep('validate', 'error', "Column 'x' could not be resolved")
    s.updateStep('generate', 'running', 'Correcting the query (attempt 2)')
    const steps = useChatStore.getState().pending!.steps
    expect(steps.validate.status).toBe('pending')
    expect(steps.validate.notes).toEqual(["Column 'x' could not be resolved"])
  })
})

describe('dateGroup', () => {
  it('groups by recency', () => {
    const now = new Date('2026-09-29T12:00:00')
    expect(dateGroup('2026-09-29T08:00:00', now)).toBe('Today')
    expect(dateGroup('2026-09-28T08:00:00', now)).toBe('Yesterday')
    expect(dateGroup('2026-09-25T08:00:00', now)).toBe('Previous 7 days')
    expect(dateGroup('2026-08-01T08:00:00', now)).toBe('Older')
  })
})
