import { X } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { useUIStore } from '@/store/ui'
import { cn } from '@/lib/utils'
import { SearchDialog } from './SearchDialog'
import { SidebarContent } from './Sidebar'
import { TopBar } from './TopBar'

/** Questions asked from outside the chat page (search palette) are handed over via router state. */
export interface AskState {
  ask?: string
}

export function AppShell() {
  const collapsed = useUIStore((s) => s.sidebarCollapsed)
  const mobileOpen = useUIStore((s) => s.mobileNavOpen)
  const setMobileOpen = useUIStore((s) => s.setMobileNavOpen)
  const [searchOpen, setSearchOpen] = useState(false)
  const location = useLocation()
  const navigate = useNavigate()

  useEffect(() => setMobileOpen(false), [location.pathname, setMobileOpen])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setSearchOpen((v) => !v)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const askFromSearch = useCallback((question: string) => navigate('/', { state: { ask: question } satisfies AskState }), [navigate])

  return (
    <div className="flex h-full overflow-hidden">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-lg focus:bg-accent focus:px-3 focus:py-2 focus:text-accent-fg"
      >
        Skip to content
      </a>

      <aside
        aria-label="Sidebar"
        className={cn(
          'hidden shrink-0 border-r border-border bg-surface/60 transition-[width] duration-200 lg:block',
          collapsed ? 'w-16' : 'w-[272px]',
        )}
      >
        <SidebarContent collapsed={collapsed} />
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
          <div className="absolute inset-0 bg-black/50" onClick={() => setMobileOpen(false)} aria-hidden />
          <div className="absolute inset-y-0 left-0 w-[284px] max-w-[85vw] border-r border-border bg-surface shadow-2xl">
            <SidebarContent
              collapsed={false}
              onNavigate={() => setMobileOpen(false)}
              headerExtra={
                <Button variant="ghost" size="icon-sm" onClick={() => setMobileOpen(false)} aria-label="Close navigation">
                  <X />
                </Button>
              }
            />
          </div>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar onOpenSearch={() => setSearchOpen(true)} />
        <main id="main" className="min-h-0 flex-1 overflow-y-auto" tabIndex={-1}>
          <Outlet />
        </main>
      </div>

      <SearchDialog open={searchOpen} onOpenChange={setSearchOpen} onAsk={askFromSearch} />
    </div>
  )
}
