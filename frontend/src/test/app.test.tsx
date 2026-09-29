import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useChatStore } from '@/store/chat'
import { useUIStore } from '@/store/ui'
import type { ChatResponse } from '@/types/api'
import { health, json, message, monthlyAnalysis, ndjson, sources } from './fixtures'
import { mockApi, renderApp } from './render'

const baseRoutes = {
  '/health': () => json(health),
  '/datasets': () => json(sources),
  '/conversations': () => json([]),
}

beforeEach(() => {
  useChatStore.getState().clear()
  useUIStore.setState({ dataSourceId: null, workbenchSql: '' })
})

describe('chat workspace', () => {
  it('shows the welcome state with suggestions and the connected data source', async () => {
    mockApi(baseRoutes)
    renderApp('/')
    expect(await screen.findByRole('heading', { name: 'Ask your data anything.' })).toBeInTheDocument()
    expect(await screen.findByText('5 tables', { exact: false })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'What were our top 5 products by revenue?' })).toBeInTheDocument()
  })

  it('asks a question, streams progress, and renders the answer', async () => {
    const user = userEvent.setup()
    const response: ChatResponse = {
      conversation_id: 'c1',
      user_message: message('user', 'Show monthly revenue for 2025'),
      assistant_message: message('assistant', 'Revenue peaked', monthlyAnalysis),
    }
    let release: () => void = () => {}
    const gate = new Promise<void>((r) => (release = r))
    const fetchMock = mockApi({
      ...baseRoutes,
      '/conversations/c1': () => json({ id: 'c1', title: 't', data_source_id: 'demo', created_at: '', updated_at: '', message_count: 0, messages: [] }),
      'POST /chat/stream': async () => {
        // Emit progress first, then hold the result until the test has checked the loading state.
        const encoder = new TextEncoder()
        const stream = new ReadableStream({
          async start(controller) {
            const send = (e: object) => controller.enqueue(encoder.encode(JSON.stringify(e) + '\n'))
            send({ type: 'conversation', conversation_id: 'c1', title: 'Show monthly revenue for 2025' })
            send({ type: 'step', step: 'understand', status: 'done', detail: null })
            send({ type: 'step', step: 'schema', status: 'done', detail: '5 of 5 tables in context' })
            send({ type: 'step', step: 'generate', status: 'running', detail: null })
            await gate
            send({ type: 'result', data: response })
            controller.close()
          },
        })
        return new Response(stream, { status: 200 })
      },
    })
    renderApp('/')
    const input = await screen.findByLabelText('Ask a question')
    await waitFor(() => expect(input).toBeEnabled())
    await user.type(input, 'Show monthly revenue for 2025{Enter}')

    expect(await screen.findByText('Generating SQL', { selector: 'span' })).toHaveClass('font-medium')
    expect(screen.getByText(/5 of 5 tables in context/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Stop' })).toBeInTheDocument()

    release()
    expect(await screen.findByText('Net revenue for each month of 2025.')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /Line chart/ })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Key insight' })).toBeInTheDocument()

    const body = JSON.parse(String(fetchMock.mock.calls.find((c) => String(c[0]).includes('/chat/stream'))![1]!.body))
    expect(body).toEqual({ question: 'Show monthly revenue for 2025', data_source_id: 'demo', conversation_id: null })
  })

  it('shows a clear error when the stream reports a failure', async () => {
    const user = userEvent.setup()
    mockApi({
      ...baseRoutes,
      'POST /chat/stream': () => ndjson([{ type: 'error', code: 'datasource_unavailable', message: 'The database is unavailable.' }]),
    })
    renderApp('/')
    const input = await screen.findByLabelText('Ask a question')
    await waitFor(() => expect(input).toBeEnabled())
    await user.type(input, 'Revenue by city{Enter}')
    expect(await screen.findByRole('alert')).toHaveTextContent('The database is unavailable.')
    expect(screen.getByRole('button', { name: /Try again/ })).toBeInTheDocument()
  })

  it('reopens a saved conversation with its analysis', async () => {
    mockApi({
      ...baseRoutes,
      '/conversations/c9': () =>
        json({
          id: 'c9',
          title: 'Monthly',
          data_source_id: 'demo',
          created_at: '',
          updated_at: '',
          message_count: 2,
          messages: [message('user', 'Show monthly revenue for 2025'), message('assistant', 'x', monthlyAnalysis)],
        }),
    })
    renderApp('/c/c9')
    expect(await screen.findByText('Show monthly revenue for 2025')).toBeInTheDocument()
    expect(screen.getByText('Total revenue')).toBeInTheDocument()
  })
})

describe('data source selection', () => {
  it('lists data sources in the picker and switches the active one', async () => {
    const user = userEvent.setup()
    mockApi(baseRoutes)
    renderApp('/')
    const picker = await screen.findByRole('combobox', { name: 'Data source' })
    await waitFor(() => expect(picker).toHaveTextContent('Sales Demo'))
    await user.click(picker)
    await user.click(await screen.findByRole('option', { name: /Warehouse/ }))
    await waitFor(() => expect(useUIStore.getState().dataSourceId).toBe('warehouse'))
    expect(picker).toHaveTextContent('Warehouse')
  })
})

describe('SQL workbench', () => {
  it('runs hand-written SQL and shows the analysis', async () => {
    const user = userEvent.setup()
    mockApi({ ...baseRoutes, 'POST /query/execute': () => json(monthlyAnalysis), '/query/history': () => json([]) })
    renderApp('/sql')
    await user.click(await screen.findByRole('button', { name: /Run query/ }))
    expect(await screen.findByRole('img', { name: /Line chart/ })).toBeInTheDocument()
  })
})
