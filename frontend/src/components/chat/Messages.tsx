import { Sparkles } from 'lucide-react'
import type { ReactNode } from 'react'
import { ErrorState } from '@/components/common/States'
import { Button } from '@/components/ui/button'
import type { PendingTurn } from '@/store/chat'
import type { Message } from '@/types/api'
import { AnalysisView } from './AnalysisView'
import { QueryProgress } from './QueryProgress'

export function UserMessage({ text }: { text: string }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[85%] rounded-2xl rounded-br-md bg-surface-3 px-4 py-2.5 text-[15px] text-fg whitespace-pre-wrap break-words">
        {text}
      </div>
    </div>
  )
}

function AssistantFrame({ children, heading }: { children: ReactNode; heading?: ReactNode }) {
  return (
    <div className="flex gap-3">
      <div
        className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-lg bg-accent text-accent-fg"
        aria-hidden
      >
        <Sparkles className="size-3.5" />
      </div>
      <div className="min-w-0 flex-1 space-y-3">
        {heading}
        {children}
      </div>
    </div>
  )
}

export function AssistantMessage({
  message,
  onAnswer,
  onRetry,
  interactive,
}: {
  message: Message
  onAnswer?: (text: string) => void
  onRetry?: () => void
  interactive?: boolean
}) {
  const analysis = message.analysis
  if (!analysis) {
    return (
      <AssistantFrame>
        <p className="text-[15px] text-fg">{message.content}</p>
      </AssistantFrame>
    )
  }
  const summary = analysis.status === 'success' && analysis.result && (
    <p className="text-[15px] leading-relaxed text-fg">
      {analysis.interpretation ?? analysis.title}
      <span className="text-muted">
        {' '}
        · {analysis.result.row_count.toLocaleString()} {analysis.result.row_count === 1 ? 'row' : 'rows'}
      </span>
    </p>
  )
  return (
    <AssistantFrame heading={summary || (analysis.status === 'empty' && <p className="text-[15px] text-fg">{analysis.interpretation}</p>)}>
      <AnalysisView analysis={analysis} onAnswer={onAnswer} onRetry={onRetry} interactive={interactive} />
    </AssistantFrame>
  )
}

export function PendingAssistant({
  turn,
  onRetry,
  onDismiss,
}: {
  turn: PendingTurn
  onRetry: () => void
  onDismiss: () => void
}) {
  return (
    <AssistantFrame>
      {turn.error ? (
        <ErrorState
          title="The request didn't complete"
          message={turn.error.message}
          onRetry={onRetry}
          action={
            <Button size="sm" variant="ghost" onClick={onDismiss}>
              Dismiss
            </Button>
          }
        />
      ) : (
        <QueryProgress steps={turn.steps} />
      )}
    </AssistantFrame>
  )
}
