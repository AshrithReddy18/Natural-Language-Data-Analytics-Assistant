import { cva, type VariantProps } from 'class-variance-authority'
import type { HTMLAttributes, ReactNode } from 'react'
import { cn } from '@/lib/utils'

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('rounded-xl border border-border bg-surface', className)} {...props} />
}

const badgeVariants = cva(
  'inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-medium leading-4 whitespace-nowrap [&_svg]:size-3',
  {
    variants: {
      tone: {
        neutral: 'bg-surface-2 text-muted border border-border',
        accent: 'bg-accent-soft text-accent',
        success: 'bg-success-soft text-success',
        warning: 'bg-warning-soft text-warning',
        danger: 'bg-danger-soft text-danger',
      },
    },
    defaultVariants: { tone: 'neutral' },
  },
)

export function Badge({
  className,
  tone,
  ...props
}: HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />
}

export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div aria-hidden className={cn('animate-pulse-soft rounded-md bg-surface-3', className)} {...props} />
}

export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="rounded border border-border bg-surface-2 px-1.5 py-0.5 font-mono text-[10px] text-subtle">
      {children}
    </kbd>
  )
}

export function StatusDot({ status, className }: { status: 'connected' | 'error' | 'unknown'; className?: string }) {
  const color = status === 'connected' ? 'bg-success' : status === 'error' ? 'bg-danger' : 'bg-subtle'
  return (
    <span className={cn('relative inline-flex size-2 shrink-0', className)} aria-hidden>
      {status === 'connected' && <span className="absolute inset-0 animate-ping rounded-full bg-success opacity-30" />}
      <span className={cn('relative inline-flex size-2 rounded-full', color)} />
    </span>
  )
}

export function SectionLabel({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn('px-2 text-[11px] font-medium uppercase tracking-wider text-subtle', className)}>{children}</div>
  )
}

export const inputClass =
  'w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-fg placeholder:text-subtle focus-visible:outline-2 focus-visible:outline-ring transition-colors hover:border-border-strong'
