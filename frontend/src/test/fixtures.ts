import type { AnalysisResult, DataSource, Health, Message, StreamEvent } from '@/types/api'

export const health: Health = {
  status: 'ok',
  version: '1.0.0',
  database: true,
  llm_configured: true,
  llm_provider: 'anthropic',
  llm_model: 'claude-opus-5-5',
}

export const sources: DataSource[] = [
  {
    id: 'demo',
    name: 'Sales Demo',
    kind: 'sqlite',
    display_url: 'sqlite:///demo.db',
    description: 'Demo store',
    business_notes: null,
    currency: 'INR',
    is_demo: true,
    created_at: '2026-01-01T00:00:00Z',
    status: 'connected',
    status_message: null,
    table_count: 5,
  },
  {
    id: 'warehouse',
    name: 'Warehouse',
    kind: 'postgresql',
    display_url: 'postgresql://ro:***@db/wh',
    description: null,
    business_notes: null,
    currency: 'USD',
    is_demo: false,
    created_at: '2026-01-02T00:00:00Z',
    status: 'connected',
    status_message: null,
    table_count: 12,
  },
]

export const monthlyAnalysis: AnalysisResult = {
  status: 'success',
  question: 'Show monthly revenue for 2025',
  interpretation: 'Net revenue for each month of 2025.',
  title: 'Monthly revenue, 2025',
  reasoning_summary: 'Sums line totals of delivered orders by month.',
  sql: {
    dialect: 'SQLite',
    generated_sql: "SELECT strftime('%Y-%m', order_date) AS month, SUM(sales_amount) AS revenue FROM orders GROUP BY 1",
    validated_sql: "SELECT\n  STRFTIME('%Y-%m', order_date) AS month,\n  SUM(line_total) AS revenue\nFROM orders\nGROUP BY\n  1\nLIMIT 1000",
    validation: { ok: true, errors: [], warnings: [], limit_applied: 1000, tables: ['orders'] },
    attempts: [
      { sql: 'SELECT sales_amount FROM orders', stage: 'validation', error: "Column 'sales_amount' could not be resolved" },
      { sql: 'SELECT line_total FROM orders', stage: 'success', error: null },
    ],
  },
  result: {
    columns: [
      { name: 'month', kind: 'temporal', format: 'date', distinct_count: 3, null_count: 0 },
      { name: 'revenue', kind: 'numeric', format: 'currency', distinct_count: 3, null_count: 0 },
    ],
    rows: [
      ['2025-01', 820000],
      ['2025-02', 910000],
      ['2025-03', 1200000],
    ],
    row_count: 3,
    truncated: false,
    execution_ms: 12,
  },
  chart: { type: 'line', x: 'month', y: ['revenue'], series: null, title: 'Monthly revenue, 2025', reason: 'revenue over time.', max_points: null },
  kpis: [
    { label: 'Total revenue', value: 2930000, format: 'currency', delta_pct: null, delta_label: null },
    { label: 'Change 2025-01 → 2025-03', value: 1200000, format: 'currency', delta_pct: 46.3, delta_label: 'vs ₹820K' },
  ],
  insight: {
    headline: 'Revenue peaked in 2025-03 at ₹1.2M.',
    bullets: ['From 2025-01 to 2025-03, revenue rose 46.3%.'],
    facts: ['Revenue peaked in 2025-03 at ₹1.2M.'],
    generated_by: 'llm',
  },
  clarification: null,
  error: null,
  query_run_id: 'run-1',
  currency: 'INR',
}

export function message(role: 'user' | 'assistant', content: string, analysis: AnalysisResult | null = null): Message {
  return { id: `${role}-${content.length}-${Math.random()}`, role, content, created_at: '2026-09-29T10:00:00Z', analysis }
}

export function ndjson(events: StreamEvent[]): Response {
  const body = events.map((e) => JSON.stringify(e)).join('\n') + '\n'
  return new Response(body, { status: 200, headers: { 'Content-Type': 'application/x-ndjson' } })
}

export const json = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } })

export const testUser = { id: 'u1', email: 'analyst@example.com', created_at: '2026-10-01T00:00:00Z' }
