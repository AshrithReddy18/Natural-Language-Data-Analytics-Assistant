import { QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { AppRoutes } from '@/App'
import { createQueryClient } from '@/lib/queryClient'
import { TooltipProvider } from '@/components/ui/overlays'

type Handler = (url: string, init?: RequestInit) => Response | Promise<Response>

/** Replace fetch with a router over path prefixes (longest match wins). */
export function mockApi(routes: Record<string, Handler>) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    const key = Object.keys(routes)
      .filter((k) => {
        const [method, path] = k.includes(' ') ? k.split(' ') : ['GET', k]
        return (init?.method ?? 'GET') === method && url.startsWith(`/api${path}`)
      })
      .sort((a, b) => b.length - a.length)[0]
    if (!key) return new Response(JSON.stringify({ error: { code: 'not_found', message: `No mock for ${url}` } }), { status: 404 })
    return routes[key](url, init)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

export function renderApp(path = '/') {
  const client = createQueryClient()
  return render(
    <QueryClientProvider client={client}>
      <TooltipProvider>
        <MemoryRouter initialEntries={[path]}>
          <AppRoutes />
        </MemoryRouter>
      </TooltipProvider>
    </QueryClientProvider>,
  )
}

export function renderWithProviders(ui: ReactElement) {
  const client = createQueryClient()
  return render(
    <QueryClientProvider client={client}>
      <TooltipProvider>
        <MemoryRouter>{ui}</MemoryRouter>
      </TooltipProvider>
    </QueryClientProvider>,
  )
}
