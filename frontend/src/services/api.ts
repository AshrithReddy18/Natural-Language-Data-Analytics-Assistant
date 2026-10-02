import type {
  AnalysisResult,
  ChatResponse,
  ConversationDetail,
  ConversationSummary,
  Credentials,
  DatabaseSchema,
  DataSource,
  DataSourceCreate,
  DataSourceUpload,
  Health,
  QueryRun,
  QueryValidateResponse,
  StreamEvent,
  User,
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
    // FormData bodies (file uploads) set their own multipart Content-Type.
    const headers = init?.body instanceof FormData ? init.headers : { 'Content-Type': 'application/json', ...init?.headers }
    res = await fetch(`${BASE}${path}`, { ...init, headers })
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

  /** The signed-in user, or null when signed out. */
  me: () =>
    request<User>('/auth/me').catch((e: unknown) => {
      if (e instanceof ApiError && e.status === 401) return null
      throw e
    }),
  login: (data: Credentials) => request<User>('/auth/login', { method: 'POST', ...json(data) }),
  signup: (data: Credentials) => request<User>('/auth/signup', { method: 'POST', ...json(data) }),
  logout: () => request<void>('/auth/logout', { method: 'POST' }),

  datasets: () => request<DataSource[]>('/datasets'),
  dataset: (id: string) => request<DataSource>(`/datasets/${id}`),
  createDataset: (data: DataSourceCreate) => request<DataSource>('/datasets', { method: 'POST', ...json(data) }),
  uploadDataset: ({ name, files, description, currency }: DataSourceUpload) => {
    const body = new FormData()
    body.set('name', name)
    if (description) body.set('description', description)
    if (currency) body.set('currency', currency)
    for (const file of files) body.append('files', file)
    return request<DataSource>('/datasets/upload', { method: 'POST', body })
  },
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
