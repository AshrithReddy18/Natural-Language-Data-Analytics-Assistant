// Mirrors backend/app/schemas (analysis.py, api.py). Keep in sync when the API changes.

export type ColumnKind = 'temporal' | 'numeric' | 'categorical' | 'identifier' | 'boolean' | 'text'
export type ValueFormat = 'currency' | 'percent' | 'number' | 'integer' | 'text' | 'date'
export type ChartType = 'line' | 'bar' | 'horizontal_bar' | 'donut' | 'scatter' | 'kpi' | 'table'
export type Cell = string | number | boolean | null

export interface ColumnMeta {
  name: string
  kind: ColumnKind
  format: ValueFormat
  distinct_count: number
  null_count: number
}

export interface QueryResultData {
  columns: ColumnMeta[]
  rows: Cell[][]
  row_count: number
  truncated: boolean
  execution_ms: number
}

export interface ValidationInfo {
  ok: boolean
  errors: string[]
  warnings: string[]
  limit_applied: number | null
  tables: string[]
}

export interface SQLAttempt {
  sql: string
  stage: 'validation' | 'execution' | 'success'
  error: string | null
}

export interface SQLInfo {
  dialect: string
  generated_sql: string
  validated_sql: string | null
  validation: ValidationInfo
  attempts: SQLAttempt[]
}

export interface ChartSpec {
  type: ChartType
  x: string | null
  y: string[]
  series: string | null
  title: string
  reason: string
  max_points: number | null
}

export interface Kpi {
  label: string
  value: number | string
  format: ValueFormat
  delta_pct: number | null
  delta_label: string | null
}

export interface Insight {
  headline: string
  bullets: string[]
  facts: string[]
  generated_by: 'llm' | 'rules'
}

export type AnalysisStatus = 'success' | 'empty' | 'clarification' | 'unanswerable' | 'error'

export interface AnalysisResult {
  status: AnalysisStatus
  question: string
  interpretation: string | null
  title: string | null
  reasoning_summary: string | null
  sql: SQLInfo | null
  result: QueryResultData | null
  chart: ChartSpec | null
  kpis: Kpi[]
  insight: Insight | null
  clarification: { question: string; options: string[] } | null
  error: { code: string; message: string } | null
  query_run_id: string | null
  currency: string
}

export interface Health {
  status: 'ok' | 'degraded'
  version: string
  database: boolean
  llm_configured: boolean
  llm_provider: string
  llm_model: string | null
}

export interface DataSource {
  id: string
  name: string
  kind: 'postgresql' | 'sqlite' | string
  display_url: string
  description: string | null
  business_notes: string | null
  currency: string
  is_demo: boolean
  created_at: string
  status: 'connected' | 'error' | 'unknown'
  status_message: string | null
  table_count: number | null
}

export interface DataSourceCreate {
  name: string
  url: string
  description?: string
  business_notes?: string
  currency?: string
}

export interface SchemaColumn {
  name: string
  type: string
  nullable: boolean
  primary_key: boolean
  references: string | null
  sample_values: string[] | null
  value_range: [string, string] | null
}

export interface SchemaTable {
  name: string
  row_count: number | null
  columns: SchemaColumn[]
}

export interface Relationship {
  from_table: string
  from_column: string
  to_table: string
  to_column: string
}

export interface DatabaseSchema {
  data_source_id: string
  dialect: string
  tables: SchemaTable[]
  relationships: Relationship[]
  fetched_at: string
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
  analysis: AnalysisResult | null
}

export interface ChatResponse {
  conversation_id: string
  user_message: Message
  assistant_message: Message
}

export interface ConversationSummary {
  id: string
  title: string
  data_source_id: string
  created_at: string
  updated_at: string
  message_count: number
}

export interface ConversationDetail extends ConversationSummary {
  messages: Message[]
}

export interface QueryRun {
  id: string
  data_source_id: string
  conversation_id: string | null
  message_id: string | null
  source: 'chat' | 'workbench' | string
  question: string | null
  generated_sql: string | null
  validated_sql: string | null
  status: 'success' | 'failed' | 'timeout' | string
  error_message: string | null
  row_count: number | null
  execution_ms: number | null
  attempts: number
  created_at: string
}

export interface QueryValidateResponse {
  validated_sql: string | null
  validation: ValidationInfo
}

export type StepId = 'understand' | 'schema' | 'generate' | 'validate' | 'execute' | 'visualize' | 'insight'
export type StepStatus = 'pending' | 'running' | 'done' | 'error' | 'skipped'

export type StreamEvent =
  | { type: 'conversation'; conversation_id: string; title: string }
  | { type: 'step'; step: StepId; status: Exclude<StepStatus, 'pending'>; detail: string | null }
  | { type: 'result'; data: ChatResponse }
  | { type: 'error'; code: string; message: string }
