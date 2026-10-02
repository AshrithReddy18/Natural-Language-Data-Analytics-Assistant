import { QueryClientProvider } from '@tanstack/react-query'
import { lazy, Suspense } from 'react'
import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'
import { EmptyState, ErrorState, LoadingRows } from '@/components/common/States'
import { AppShell } from '@/components/layout/AppShell'
import { TooltipProvider } from '@/components/ui/overlays'
import { useMe } from '@/hooks/queries'
import { createQueryClient } from '@/lib/queryClient'

const ChatPage = lazy(() => import('@/pages/ChatPage'))
const WorkbenchPage = lazy(() => import('@/pages/WorkbenchPage'))
const HistoryPage = lazy(() => import('@/pages/HistoryPage'))
const DataSourcesPage = lazy(() => import('@/pages/DataSourcesPage'))
const SchemaPage = lazy(() => import('@/pages/SchemaPage'))
const SettingsPage = lazy(() => import('@/pages/SettingsPage'))
const AuthPage = lazy(() => import('@/pages/AuthPage'))

/** Everything in the app needs a signed-in user; until then, show the sign-in page. */
function AuthGate() {
  const { data: user, isLoading, error, refetch } = useMe()
  if (isLoading) return <LoadingRows className="mx-auto max-w-3xl p-6" />
  if (error) return <ErrorState className="m-6" message={error.message} onRetry={() => refetch()} />
  if (!user) return <AuthPage />
  return <AppShell />
}

function NotFound() {
  return (
    <EmptyState
      className="py-24"
      title="Page not found"
      description="The page you were looking for doesn't exist."
      action={<Link to="/" className="text-sm text-accent hover:underline">Back to DataPilot</Link>}
    />
  )
}

export function AppRoutes() {
  return (
    <Suspense fallback={<LoadingRows className="mx-auto max-w-3xl p-6" />}>
      <Routes>
        <Route element={<AuthGate />}>
          <Route index element={<ChatPage />} />
          <Route path="c/:conversationId" element={<ChatPage />} />
          <Route path="sql" element={<WorkbenchPage />} />
          <Route path="history" element={<HistoryPage />} />
          <Route path="data" element={<DataSourcesPage />} />
          <Route path="data/:id" element={<SchemaPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </Suspense>
  )
}

const queryClient = createQueryClient()

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </TooltipProvider>
    </QueryClientProvider>
  )
}
