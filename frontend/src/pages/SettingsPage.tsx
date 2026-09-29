import { Lock, Moon, ShieldCheck, Sparkles, Sun } from 'lucide-react'
import type { ReactNode } from 'react'
import { Button } from '@/components/ui/button'
import { Badge, Card } from '@/components/ui/primitives'
import { useHealth } from '@/hooks/queries'
import { cn } from '@/lib/utils'
import { useUIStore } from '@/store/ui'

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 py-2.5">
      <span className="text-sm text-muted">{label}</span>
      <span className="text-sm text-fg">{children}</span>
    </div>
  )
}

export default function SettingsPage() {
  const { data: health, error } = useHealth()
  const theme = useUIStore((s) => s.theme)
  const setTheme = useUIStore((s) => s.setTheme)

  return (
    <div className="mx-auto w-full max-w-3xl space-y-5 px-4 py-6 sm:px-6">
      <h1 className="text-xl font-semibold tracking-tight text-fg">Settings</h1>

      <Card className="p-4">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-fg">
          <Sparkles className="size-4 text-accent" aria-hidden /> AI provider
        </h2>
        <div className="mt-2 divide-y divide-border">
          <Row label="Status">
            {error ? <Badge tone="danger">API offline</Badge> : health?.llm_configured ? <Badge tone="success">Configured</Badge> : <Badge tone="warning">Not configured</Badge>}
          </Row>
          <Row label="Provider">{health?.llm_provider ?? '—'}</Row>
          <Row label="Model"><code className="font-mono text-xs">{health?.llm_model ?? '—'}</code></Row>
          <Row label="API version">{health?.version ?? '—'}</Row>
        </div>
        <p className="mt-3 text-xs text-subtle">
          Configured on the server via environment variables: <code className="font-mono">LLM_PROVIDER</code> is{' '}
          <code className="font-mono">ollama</code> (free, local), <code className="font-mono">gemini</code> (free tier key),{' '}
          <code className="font-mono">anthropic</code> or <code className="font-mono">openai</code>; optional{' '}
          <code className="font-mono">LLM_MODEL</code>. Keys are never sent to the browser.
        </p>
      </Card>

      <Card className="p-4">
        <h2 className="text-sm font-semibold text-fg">Appearance</h2>
        <div className="mt-3 flex gap-2" role="radiogroup" aria-label="Theme">
          {(['dark', 'light'] as const).map((t) => (
            <Button
              key={t}
              role="radio"
              aria-checked={theme === t}
              variant="outline"
              size="sm"
              onClick={() => setTheme(t)}
              className={cn('capitalize', theme === t && 'border-accent text-fg')}
            >
              {t === 'dark' ? <Moon /> : <Sun />} {t}
            </Button>
          ))}
        </div>
      </Card>

      <Card className="p-4">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-fg">
          <ShieldCheck className="size-4 text-success" aria-hidden /> How queries are kept safe
        </h2>
        <ul className="mt-3 space-y-2 text-sm text-muted">
          {[
            'Generated SQL is parsed into a syntax tree; only a single SELECT (CTEs allowed) is accepted.',
            'Writes, DDL, session commands, system catalogs and dangerous functions are rejected.',
            'Every table and column is checked against the live schema before execution.',
            'Queries run in a read-only transaction (read-only connection for SQLite) with a timeout and a row limit.',
            'Insights are computed from the results; AI-written text is rejected if it contains numbers not in the data.',
          ].map((t) => (
            <li key={t} className="flex gap-2">
              <Lock className="mt-0.5 size-3.5 shrink-0 text-subtle" aria-hidden /> {t}
            </li>
          ))}
        </ul>
      </Card>
    </div>
  )
}
