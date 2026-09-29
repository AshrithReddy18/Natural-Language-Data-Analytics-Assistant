import { KeyRound } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { StatusDot } from '@/components/ui/primitives'
import { SUGGESTIONS } from '@/lib/suggestions'
import { greeting } from '@/lib/time'
import type { DataSource } from '@/types/api'
import { Composer } from './Composer'

export function Welcome({
  source,
  llmConfigured,
  onAsk,
}: {
  source: DataSource | undefined
  llmConfigured: boolean
  onAsk: (question: string) => void
}) {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col px-4 pb-10 pt-[8vh] sm:px-6">
      <p className="text-sm font-medium text-muted">{greeting()}.</p>
      <h1 className="mt-1 text-3xl font-semibold tracking-tight text-fg sm:text-4xl">Ask your data anything.</h1>
      <p className="mt-2 max-w-xl text-[15px] text-muted">
        Questions become validated SQL, run against your database, and come back as charts and insights — with every
        query visible.
      </p>

      {source && (
        <div className="mt-6 flex items-center gap-2 text-xs text-muted">
          <StatusDot status={source.status} />
          Connected to <span className="font-medium text-fg">{source.name}</span>
          {source.table_count !== null && <span className="text-subtle">· {source.table_count} tables</span>}
        </div>
      )}

      <div className="mt-3">
        <Composer
          onSubmit={onAsk}
          size="lg"
          autoFocus
          disabled={!source}
          placeholder="What were our top products this month?"
        />
      </div>

      {!llmConfigured && (
        <div className="mt-4 flex flex-col gap-3 rounded-xl border border-warning/30 bg-warning-soft/60 px-4 py-3 text-sm sm:flex-row sm:items-center">
          <KeyRound className="size-4 shrink-0 text-warning" aria-hidden />
          <p className="flex-1 text-muted">
            <span className="font-medium text-fg">AI is not configured.</span> Use a free local model with{' '}
            <code className="font-mono text-xs">LLM_PROVIDER=ollama</code>, or a free Gemini key with{' '}
            <code className="font-mono text-xs">LLM_PROVIDER=gemini</code>. The schema explorer and SQL workbench work without it.
          </p>
          <Button asChild size="sm" variant="secondary">
            <Link to="/sql">Open SQL workbench</Link>
          </Button>
        </div>
      )}

      <h2 className="mb-3 mt-10 text-xs font-medium uppercase tracking-wider text-subtle">Try asking</h2>
      <div className="grid gap-3 sm:grid-cols-2">
        {SUGGESTIONS.map(({ topic, icon: Icon, questions }) => (
          <div key={topic} className="rounded-xl border border-border bg-surface p-3">
            <div className="mb-2 flex items-center gap-2 text-sm font-medium text-fg">
              <Icon className="size-4 text-accent" aria-hidden /> {topic}
            </div>
            <ul className="space-y-0.5">
              {questions.map((q) => (
                <li key={q}>
                  <button
                    type="button"
                    onClick={() => onAsk(q)}
                    disabled={!source}
                    className="w-full rounded-md px-2 py-1.5 text-left text-sm text-muted transition-colors hover:bg-surface-2 hover:text-fg disabled:opacity-50 cursor-pointer"
                  >
                    {q}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  )
}
