import { ChevronRight } from 'lucide-react'
import { useId, useState, type ReactNode } from 'react'
import { cn } from '@/lib/utils'

/** An expandable section: "▸ Generated SQL", "▸ Data table"... */
export function Disclosure({
  title,
  icon,
  meta,
  defaultOpen = false,
  children,
}: {
  title: string
  icon?: ReactNode
  meta?: ReactNode
  defaultOpen?: boolean
  children: ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen)
  const id = useId()
  return (
    <div className="rounded-xl border border-border bg-surface">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 rounded-xl px-3.5 py-2.5 text-left text-sm font-medium text-fg hover:bg-surface-2/60 cursor-pointer"
      >
        <ChevronRight className={cn('size-4 text-subtle transition-transform', open && 'rotate-90')} aria-hidden />
        <span className="text-subtle [&_svg]:size-4" aria-hidden>
          {icon}
        </span>
        {title}
        {meta && <span className="ml-auto hidden min-w-0 sm:flex items-center gap-2 text-xs font-normal text-subtle">{meta}</span>}
      </button>
      {open && (
        <div id={id} className="border-t border-border px-3.5 py-3">
          {children}
        </div>
      )}
    </div>
  )
}
