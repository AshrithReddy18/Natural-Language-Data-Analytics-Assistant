import {
  Database,
  History,
  MessageSquare,
  MoreHorizontal,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Settings,
  SquareTerminal,
  Trash2,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, Tooltip } from '@/components/ui/overlays'
import { SectionLabel, Skeleton, StatusDot } from '@/components/ui/primitives'
import { useActiveDataSource, useConversations, useDeleteConversation } from '@/hooks/queries'
import { dateGroup, type DateGroup } from '@/lib/time'
import { cn } from '@/lib/utils'
import { useChatStore } from '@/store/chat'
import { useUIStore } from '@/store/ui'
import type { ConversationSummary } from '@/types/api'

export function Logo({ compact }: { compact?: boolean }) {
  return (
    <Link to="/" className="flex items-center gap-2.5 rounded-lg px-1 py-0.5" aria-label="DataPilot home">
      <svg viewBox="0 0 32 32" className="size-7 shrink-0" aria-hidden>
        <rect width="32" height="32" rx="8" fill="var(--accent)" />
        <path d="M9 21.5 14 15l4 3.5 5-7" fill="none" stroke="#fff" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="23" cy="11.5" r="2" fill="#fff" />
      </svg>
      {!compact && <span className="text-[15px] font-semibold tracking-tight text-fg">DataPilot</span>}
    </Link>
  )
}

const NAV = [
  { to: '/sql', label: 'SQL workbench', icon: SquareTerminal },
  { to: '/history', label: 'Query history', icon: History },
  { to: '/data', label: 'Data sources', icon: Database },
]

function NavItem({ to, label, icon: Icon, collapsed, onNavigate }: {
  to: string
  label: string
  icon: typeof History
  collapsed: boolean
  onNavigate?: () => void
}) {
  // className is computed here (not NavLink's function form) because the Tooltip trigger merges
  // className as a string, which would drop a function.
  const { pathname } = useLocation()
  const isActive = to === '/' ? pathname === '/' || pathname.startsWith('/c/') : pathname.startsWith(to)
  const link = (
    <Link
      to={to}
      onClick={onNavigate}
      aria-current={isActive ? 'page' : undefined}
      className={cn(
        'flex items-center gap-2.5 rounded-lg px-2 py-1.5 text-sm transition-colors',
        collapsed && 'justify-center px-0 py-2',
        isActive ? 'bg-surface-2 text-fg' : 'text-muted hover:bg-surface-2 hover:text-fg',
      )}
    >
      <Icon className="size-4 shrink-0" aria-hidden />
      {collapsed ? <span className="sr-only">{label}</span> : label}
    </Link>
  )
  return collapsed ? <Tooltip content={label} side="right">{link}</Tooltip> : link
}

const GROUP_ORDER: DateGroup[] = ['Today', 'Yesterday', 'Previous 7 days', 'Older']

function ConversationList({ onNavigate }: { onNavigate?: () => void }) {
  const { data, isLoading } = useConversations()
  const { conversationId } = useParams()
  const navigate = useNavigate()
  const remove = useDeleteConversation()

  if (isLoading) {
    return (
      <div className="space-y-2 px-2">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-6" />
        ))}
      </div>
    )
  }
  if (!data?.length) {
    return <p className="px-2 text-xs text-subtle">Your conversations will appear here.</p>
  }

  const groups = new Map<DateGroup, ConversationSummary[]>()
  for (const c of data) {
    const g = dateGroup(c.updated_at)
    groups.set(g, [...(groups.get(g) ?? []), c])
  }

  return (
    <div className="space-y-4">
      {GROUP_ORDER.filter((g) => groups.has(g)).map((g) => (
        <div key={g}>
          <SectionLabel className="mb-1">{g}</SectionLabel>
          <ul className="space-y-px">
            {groups.get(g)!.map((c) => (
              <li key={c.id} className="group relative">
                <Link
                  to={`/c/${c.id}`}
                  onClick={onNavigate}
                  aria-current={conversationId === c.id ? 'page' : undefined}
                  className={cn(
                    'block truncate rounded-lg py-1.5 pl-2 pr-8 text-sm transition-colors',
                    conversationId === c.id ? 'bg-surface-2 text-fg' : 'text-muted hover:bg-surface-2 hover:text-fg',
                  )}
                >
                  {c.title}
                </Link>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <button
                      type="button"
                      aria-label={`Options for ${c.title}`}
                      className="absolute right-1 top-1/2 -translate-y-1/2 rounded-md p-1 text-subtle opacity-0 hover:text-fg focus-visible:opacity-100 group-hover:opacity-100 data-[state=open]:opacity-100 cursor-pointer"
                    >
                      <MoreHorizontal className="size-4" />
                    </button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="start">
                    <DropdownMenuItem
                      destructive
                      onSelect={() =>
                        remove.mutate(c.id, {
                          onSuccess: () => conversationId === c.id && navigate('/'),
                        })
                      }
                    >
                      <Trash2 /> Delete conversation
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  )
}

function DataSourceList({ collapsed, onNavigate }: { collapsed: boolean; onNavigate?: () => void }) {
  const { sources, source: active } = useActiveDataSource()
  const setSelected = useUIStore((s) => s.setDataSourceId)
  if (!sources?.length) return null
  return (
    <div>
      {!collapsed && <SectionLabel className="mb-1">Data sources</SectionLabel>}
      <ul className="space-y-px">
        {sources.map((s) => {
          const item = (
            <Link
              to={`/data/${s.id}`}
              onClick={() => {
                setSelected(s.id)
                onNavigate?.()
              }}
              className={cn(
                'flex items-center gap-2.5 rounded-lg px-2 py-1.5 text-sm text-muted transition-colors hover:bg-surface-2 hover:text-fg',
                collapsed && 'justify-center px-0',
                active?.id === s.id && 'text-fg',
              )}
            >
              <StatusDot status={s.status} />
              {collapsed ? <span className="sr-only">{s.name}</span> : <span className="truncate">{s.name}</span>}
            </Link>
          )
          return <li key={s.id}>{collapsed ? <Tooltip content={s.name} side="right">{item}</Tooltip> : item}</li>
        })}
      </ul>
    </div>
  )
}

export function SidebarContent({ collapsed, onNavigate, headerExtra }: {
  collapsed: boolean
  onNavigate?: () => void
  headerExtra?: ReactNode
}) {
  const navigate = useNavigate()
  const clearPending = useChatStore((s) => s.clear)
  const toggle = useUIStore((s) => s.toggleSidebar)
  const newChat = () => {
    if (useChatStore.getState().pending?.error) clearPending()
    navigate('/')
    onNavigate?.()
  }

  return (
    <div className="flex h-full flex-col">
      <div className={cn('flex h-14 items-center px-3', collapsed ? 'justify-center' : 'justify-between')}>
        <Logo compact={collapsed} />
        {headerExtra}
      </div>
      <div className={cn('px-3', collapsed && 'px-2')}>
        {collapsed ? (
          <Tooltip content="New chat" side="right">
            <Button variant="outline" size="icon" onClick={newChat} className="w-full" aria-label="New chat">
              <Plus />
            </Button>
          </Tooltip>
        ) : (
          <Button variant="outline" onClick={newChat} className="w-full justify-start">
            <Plus /> New chat
          </Button>
        )}
      </div>
      <nav aria-label="Main" className={cn('mt-3 space-y-px px-3', collapsed && 'px-2')}>
        <NavItem to="/" label="Ask DataPilot" icon={MessageSquare} collapsed={collapsed} onNavigate={onNavigate} />
        {NAV.map((n) => (
          <NavItem key={n.to} {...n} collapsed={collapsed} onNavigate={onNavigate} />
        ))}
      </nav>
      <div className={cn('mt-5 min-h-0 flex-1 overflow-y-auto px-3', collapsed && 'px-2')}>
        {!collapsed && (
          <section aria-label="Conversations" className="mb-5">
            <ConversationList onNavigate={onNavigate} />
          </section>
        )}
      </div>
      <div className={cn('space-y-3 border-t border-border px-3 py-3', collapsed && 'px-2')}>
        <DataSourceList collapsed={collapsed} onNavigate={onNavigate} />
        <div className={cn('flex items-center gap-1', collapsed && 'flex-col')}>
          <div className="flex-1">
            <NavItem to="/settings" label="Settings" icon={Settings} collapsed={collapsed} onNavigate={onNavigate} />
          </div>
          <Tooltip content={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} side="right">
            <Button variant="ghost" size="icon-sm" onClick={toggle} className="hidden lg:inline-flex" aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}>
              {collapsed ? <PanelLeftOpen /> : <PanelLeftClose />}
            </Button>
          </Tooltip>
        </div>
      </div>
    </div>
  )
}
