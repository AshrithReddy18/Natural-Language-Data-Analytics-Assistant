import type {
  AnalysisResult,
  ChatResponse,
  ConversationDetail,
  ConversationSummary,
  DatabaseSchema,
  DataSource,
  DataSourceCreate,
  Health,
  QueryRun,
  QueryValidateResponse,
  StreamEvent,
} from '@/types/api'

const BASE = import.meta.env.VITE_API_URL ?? '/api'

export class ApiError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    })
  } catch {
    throw new ApiError(0, 'network_error', 'Cannot reach the DataPilot server. Is the backend running?')
  }
  if (res.status === 204) return undefined as T
  const body: unknown = await res.json().catch(() => null)
  if (!res.ok) {
    const err = (body as { error?: { code?: string; message?: string } } | null)?.error
    throw new ApiError(res.status, err?.code ?? 'http_error', err?.message ?? `Request failed (${res.status})`)
  }
  return body as T
}

const json = (data: unknown): RequestInit => ({ body: JSON.stringify(data) })

export const api = {
  health: () => request<Health>('/health'),

  datasets: () => request<DataSource[]>('/datasets'),
  dataset: (id: string) => request<DataSource>(`/datasets/${id}`),
  createDataset: (data: DataSourceCreate) => request<DataSource>('/datasets', { method: 'POST', ...json(data) }),
  updateDataset: (id: string, data: Partial<DataSourceCreate>) =>
    request<DataSource>(`/datasets/${id}`, { method: 'PATCH', ...json(data) }),
  deleteDataset: (id: string) => request<void>(`/datasets/${id}`, { method: 'DELETE' }),
  schema: (id: string, refresh = false) =>
    request<DatabaseSchema>(`/datasets/${id}/schema${refresh ? '?refresh=true' : ''}`),

  conversations: () => request<ConversationSummary[]>('/conversations'),
  conversation: (id: string) => request<ConversationDetail>(`/conversations/${id}`),
  deleteConversation: (id: string) => request<void>(`/conversations/${id}`, { method: 'DELETE' }),

  validateSql: (dataSourceId: string, sql: string) =>
    request<QueryValidateResponse>('/query/validate', { method: 'POST', ...json({ data_source_id: dataSourceId, sql }) }),
  executeSql: (dataSourceId: string, sql: string) =>
    request<AnalysisResult>('/query/execute', { method: 'POST', ...json({ data_source_id: dataSourceId, sql }) }),
  history: (dataSourceId?: string, limit = 100) => {
    const params = new URLSearchParams({ limit: String(limit) })
    if (dataSourceId) params.set('data_source_id', dataSourceId)
    return request<QueryRun[]>(`/query/history?${params}`)
  },

  chat: (body: { question: string; data_source_id: string; conversation_id?: string | null }) =>
    request<ChatResponse>('/chat', { method: 'POST', ...json(body) }),
}

/** Ask a question and receive pipeline progress as newline-delimited JSON events. */
export async function streamChat(
  body: { question: string; data_source_id: string; conversation_id?: string | null },
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  let res: Response
  try {
    res = await fetch(`${BASE}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal,
    })
  } catch (e) {
    if (signal?.aborted) throw e
    throw new ApiError(0, 'network_error', 'Cannot reach the DataPilot server. Is the backend running?')
  }
  if (!res.ok || !res.body) {
    const err = ((await res.json().catch(() => null)) as { error?: { code: string; message: string } } | null)?.error
    throw new ApiError(res.status, err?.code ?? 'http_error', err?.message ?? `Request failed (${res.status})`)
  }
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let newline: number
    while ((newline = buffer.indexOf('\n')) >= 0) {
      const line = buffer.slice(0, newline).trim()
      buffer = buffer.slice(newline + 1)
      if (line) onEvent(JSON.parse(line) as StreamEvent)
    }
  }
  if (buffer.trim()) onEvent(JSON.parse(buffer) as StreamEvent)
}
