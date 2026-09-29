import { AlertTriangle, Inbox, RefreshCw } from 'lucide-react'
import type { ReactNode } from 'react'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/primitives'
import { cn } from '@/lib/utils'

export function ErrorState({
  title = 'Something went wrong',
  message,
  onRetry,
  action,
  className,
}: {
  title?: string
  message: string
  onRetry?: () => void
  action?: ReactNode
  className?: string
}) {
  return (
    <div role="alert" className={cn('rounded-xl border border-danger/30 bg-danger-soft/50 px-4 py-3.5', className)}>
      <div className="flex gap-3">
        <AlertTriangle className="mt-0.5 size-4 shrink-0 text-danger" aria-hidden />
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium text-fg">{title}</div>
          <p className="mt-0.5 text-sm text-muted break-words">{message}</p>
          {(onRetry || action) && (
            <div className="mt-3 flex flex-wrap gap-2">
              {onRetry && (
                <Button size="sm" variant="secondary" onClick={onRetry}>
                  <RefreshCw /> Try again
                </Button>
              )}
              {action}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: {
  icon?: ReactNode
  title: string
  description?: ReactNode
  action?: ReactNode
  className?: string
}) {
  return (
    <div className={cn('flex flex-col items-center justify-center px-6 py-14 text-center', className)}>
      <div className="mb-3 flex size-10 items-center justify-center rounded-xl border border-border bg-surface-2 text-subtle [&_svg]:size-5">
        {icon ?? <Inbox />}
      </div>
      <div className="text-sm font-medium text-fg">{title}</div>
      {description && <p className="mt-1 max-w-sm text-sm text-muted">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export function LoadingRows({ rows = 3, className }: { rows?: number; className?: string }) {
  return (
    <div className={cn('space-y-2', className)} role="status" aria-label="Loading">
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className="h-9 w-full" style={{ opacity: 1 - i * 0.2 }} />
      ))}
    </div>
  )
}
