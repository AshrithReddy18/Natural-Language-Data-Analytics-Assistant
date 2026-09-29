import { Check, Circle, CircleAlert, Loader2, Minus } from 'lucide-react'
import { STEP_LABELS, STEP_ORDER, type StepState } from '@/store/chat'
import { cn } from '@/lib/utils'
import type { StepId } from '@/types/api'

function StepIcon({ status }: { status: StepState['status'] }) {
  switch (status) {
    case 'done':
      return <Check className="size-3.5 text-success" aria-hidden />
    case 'running':
      return <Loader2 className="size-3.5 animate-spin text-accent" aria-hidden />
    case 'error':
      return <CircleAlert className="size-3.5 text-danger" aria-hidden />
    case 'skipped':
      return <Minus className="size-3.5 text-subtle" aria-hidden />
    default:
      return <Circle className="size-2.5 text-border-strong" aria-hidden />
  }
}

/** Live view of the pipeline, driven by real server events (not timers). */
export function QueryProgress({ steps }: { steps: Record<StepId, StepState> }) {
  const current = STEP_ORDER.find((s) => steps[s].status === 'running')
  return (
    <div className="rounded-xl border border-border bg-surface px-4 py-3">
      <p className="sr-only" aria-live="polite">
        {current ? STEP_LABELS[current] : ''}
      </p>
      <ol className="space-y-1.5">
        {STEP_ORDER.map((id) => {
          const step = steps[id]
          return (
            <li key={id} className="text-sm">
              <div className="flex items-center gap-2.5">
                <span className="flex size-4 items-center justify-center">
                  <StepIcon status={step.status} />
                </span>
                <span
                  className={cn(
                    step.status === 'pending' && 'text-subtle',
                    step.status === 'running' && 'text-fg font-medium',
                    step.status === 'done' && 'text-muted',
                    step.status === 'error' && 'text-danger',
                    step.status === 'skipped' && 'text-subtle line-through decoration-subtle/50',
                  )}
                >
                  {STEP_LABELS[id]}
                </span>
                {step.detail && step.status !== 'error' && (
                  <span className="truncate text-xs text-subtle">— {step.detail}</span>
                )}
              </div>
              {step.notes.map((n, i) => (
                <div key={i} className="ml-[26px] mt-0.5 text-xs text-warning">
                  Corrected: {n}
                </div>
              ))}
              {step.status === 'error' && step.detail && (
                <div className="ml-[26px] mt-0.5 text-xs text-danger break-words">{step.detail}</div>
              )}
            </li>
          )
        })}
      </ol>
    </div>
  )
}
