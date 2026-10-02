import { Database, Menu, Moon, Search, Sparkles, Sun } from 'lucide-react'
import { useLocation } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Tooltip } from '@/components/ui/overlays'
import { Badge, Kbd, StatusDot } from '@/components/ui/primitives'
import { Select } from '@/components/ui/select'
import { useActiveDataSource, useHealth } from '@/hooks/queries'
import { sourceKindLabel, tableCountLabel } from '@/lib/format'
import { useUIStore } from '@/store/ui'

function DataSourcePicker() {
  const { sources, source } = useActiveDataSource()
  const setSelected = useUIStore((s) => s.setDataSourceId)
  if (!sources) return null
  return (
    <Select
      ariaLabel="Data source"
      value={source?.id}
      onValueChange={setSelected}
      icon={source ? <StatusDot status={source.status} /> : <Database className="size-3.5 text-subtle" />}
      className="max-w-[12rem] sm:max-w-[16rem]"
      options={sources.map((s) => ({
        value: s.id,
        label: s.name,
        hint: `${sourceKindLabel(s.kind)}${s.table_count !== null ? ` · ${tableCountLabel(s.table_count)}` : ''}${s.status === 'error' ? ' · unavailable' : ''}`,
      }))}
    />
  )
}

export function TopBar({ onOpenSearch }: { onOpenSearch: () => void }) {
  const { pathname } = useLocation()
  const theme = useUIStore((s) => s.theme)
  const setTheme = useUIStore((s) => s.setTheme)
  const setMobileNavOpen = useUIStore((s) => s.setMobileNavOpen)
  const { data: health, isError } = useHealth()
  const showPicker = pathname === '/' || pathname.startsWith('/c/') || pathname === '/sql'

  return (
    <header className="sticky top-0 z-20 flex h-14 shrink-0 items-center gap-2 border-b border-border bg-bg/80 px-3 backdrop-blur sm:px-4">
      <Button variant="ghost" size="icon-sm" className="lg:hidden" onClick={() => setMobileNavOpen(true)} aria-label="Open navigation">
        <Menu />
      </Button>
      {showPicker && <DataSourcePicker />}

      <div className="ml-auto flex items-center gap-1.5">
        {isError ? (
          <Badge tone="danger">API offline</Badge>
        ) : (
          health && (
            <Tooltip
              content={
                health.llm_configured
                  ? `AI: ${health.llm_provider} · ${health.llm_model}`
                  : 'No AI provider configured — the SQL workbench and schema explorer still work.'
              }
            >
              <span tabIndex={0} className="hidden sm:inline-flex">
                <Badge tone={health.llm_configured ? 'accent' : 'warning'}>
                  <Sparkles /> {health.llm_configured ? health.llm_model : 'AI not configured'}
                </Badge>
              </span>
            </Tooltip>
          )
        )}
        <Button variant="ghost" size="sm" onClick={onOpenSearch} aria-label="Search (Ctrl+K)" className="text-subtle">
          <Search />
          <span className="hidden md:inline">Search</span>
          <span className="hidden md:inline">
            <Kbd>Ctrl K</Kbd>
          </span>
        </Button>
        <Tooltip content={theme === 'dark' ? 'Light theme' : 'Dark theme'}>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
          >
            {theme === 'dark' ? <Sun /> : <Moon />}
          </Button>
        </Tooltip>
      </div>
    </header>
  )
}
