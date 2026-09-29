import { CornerDownLeft, Database, History, MessageSquare, Search, Settings, Sparkles, SquareTerminal } from 'lucide-react'
import { useMemo, useState, type KeyboardEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { SUGGESTIONS } from '@/lib/suggestions'
import { Dialog, DialogContent } from '@/components/ui/overlays'
import { useConversations } from '@/hooks/queries'
import { cn } from '@/lib/utils'

interface Item {
  id: string
  label: string
  group: string
  icon: typeof Search
  run: () => void
}

export function SearchDialog({ open, onOpenChange, onAsk }: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onAsk: (question: string) => void
}) {
  const [query, setQuery] = useState('')
  const [index, setIndex] = useState(0)
  const navigate = useNavigate()
  const { data: conversations } = useConversations()

  const items = useMemo<Item[]>(() => {
    const go = (to: string) => () => navigate(to)
    const all: Item[] = [
      { id: 'p-chat', label: 'New chat', group: 'Pages', icon: MessageSquare, run: go('/') },
      { id: 'p-sql', label: 'SQL workbench', group: 'Pages', icon: SquareTerminal, run: go('/sql') },
      { id: 'p-history', label: 'Query history', group: 'Pages', icon: History, run: go('/history') },
      { id: 'p-data', label: 'Data sources', group: 'Pages', icon: Database, run: go('/data') },
      { id: 'p-settings', label: 'Settings', group: 'Pages', icon: Settings, run: go('/settings') },
      ...(conversations ?? []).map((c) => ({
        id: `c-${c.id}`,
        label: c.title,
        group: 'Conversations',
        icon: MessageSquare,
        run: go(`/c/${c.id}`),
      })),
      ...SUGGESTIONS.flatMap((s) => s.questions).map((q) => ({
        id: `q-${q}`,
        label: q,
        group: 'Ask',
        icon: Sparkles,
        run: () => onAsk(q),
      })),
    ]
    const q = query.trim().toLowerCase()
    const filtered = q ? all.filter((i) => i.label.toLowerCase().includes(q)) : all.filter((i) => i.group !== 'Conversations' || all.indexOf(i) < 11)
    if (q && !filtered.some((i) => i.group === 'Ask' && i.label.toLowerCase() === q)) {
      filtered.push({ id: 'ask-custom', label: `Ask “${query.trim()}”`, group: 'Ask', icon: Sparkles, run: () => onAsk(query.trim()) })
    }
    return filtered.slice(0, 30)
  }, [query, conversations, navigate, onAsk])

  const choose = (item: Item | undefined) => {
    if (!item) return
    item.run()
    onOpenChange(false)
    setQuery('')
  }

  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setIndex((i) => Math.min(i + 1, items.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setIndex((i) => Math.max(i - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      choose(items[index])
    }
  }

  let lastGroup = ''
  return (
    <Dialog open={open} onOpenChange={(o) => { onOpenChange(o); if (!o) setQuery('') }}>
      <DialogContent title="Search" className="max-w-xl p-3">
        <div className="flex items-center gap-2 rounded-lg border border-border px-3">
          <Search className="size-4 text-subtle" aria-hidden />
          <input
            autoFocus
            value={query}
            onChange={(e) => {
              setQuery(e.target.value)
              setIndex(0)
            }}
            onKeyDown={onKeyDown}
            placeholder="Search conversations, pages, or ask a question…"
            aria-label="Search"
            role="combobox"
            aria-expanded
            aria-controls="search-results"
            aria-activedescendant={items[index]?.id}
            className="h-10 flex-1 bg-transparent text-sm text-fg placeholder:text-subtle focus:outline-none focus-visible:outline-none"
          />
        </div>
        <ul id="search-results" role="listbox" className="mt-2 max-h-[50vh] overflow-y-auto">
          {items.map((item, i) => {
            const header = item.group !== lastGroup ? item.group : null
            lastGroup = item.group
            const Icon = item.icon
            return (
              <li key={item.id} role="presentation">
                {header && <div className="px-2 pb-1 pt-2.5 text-[11px] font-medium uppercase tracking-wider text-subtle">{header}</div>}
                <div
                  id={item.id}
                  role="option"
                  aria-selected={i === index}
                  onMouseEnter={() => setIndex(i)}
                  onClick={() => choose(item)}
                  className={cn(
                    'flex cursor-pointer items-center gap-2.5 rounded-md px-2 py-1.5 text-sm',
                    i === index ? 'bg-surface-2 text-fg' : 'text-muted',
                  )}
                >
                  <Icon className="size-4 shrink-0 text-subtle" aria-hidden />
                  <span className="truncate">{item.label}</span>
                  {i === index && <CornerDownLeft className="ml-auto size-3.5 text-subtle" aria-hidden />}
                </div>
              </li>
            )
          })}
          {items.length === 0 && <li className="px-2 py-6 text-center text-sm text-subtle">No results</li>}
        </ul>
      </DialogContent>
    </Dialog>
  )
}
