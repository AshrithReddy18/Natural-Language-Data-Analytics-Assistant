import { ChevronRight, Lightbulb, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { Tooltip } from '@/components/ui/overlays'
import type { Insight } from '@/types/api'

export function InsightCard({ insight }: { insight: Insight }) {
  const [showFacts, setShowFacts] = useState(false)
  const bullets = insight.bullets.filter((b) => b && b !== insight.headline)
  return (
    <section
      aria-label="Key insight"
      className="rounded-xl border border-border bg-gradient-to-br from-accent-soft/60 to-transparent px-4 py-3.5"
    >
      <div className="mb-1.5 flex items-center justify-between gap-2">
        <h3 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-accent">
          <Lightbulb className="size-3.5" aria-hidden /> Key insight
        </h3>
        <Tooltip
          content={
            insight.generated_by === 'llm'
              ? 'Written by the AI from computed facts. Every number was checked against the query results.'
              : 'Computed directly from the query results.'
          }
        >
          <span className="inline-flex items-center gap-1 text-[11px] text-subtle" tabIndex={0}>
            <ShieldCheck className="size-3" aria-hidden />
            {insight.generated_by === 'llm' ? 'Numbers verified' : 'Computed from data'}
          </span>
        </Tooltip>
      </div>
      <p className="text-[15px] leading-relaxed text-fg">{insight.headline}</p>
      {bullets.length > 0 && (
        <ul className="mt-2 space-y-1 text-sm text-muted">
          {bullets.map((b) => (
            <li key={b} className="flex gap-2">
              <span className="mt-2 size-1 shrink-0 rounded-full bg-subtle" aria-hidden />
              {b}
            </li>
          ))}
        </ul>
      )}
      {insight.facts.length > 0 && insight.generated_by === 'llm' && (
        <div className="mt-2.5">
          <button
            type="button"
            onClick={() => setShowFacts((v) => !v)}
            aria-expanded={showFacts}
            className="inline-flex items-center gap-1 text-xs text-subtle hover:text-muted cursor-pointer"
          >
            <ChevronRight className={`size-3 transition-transform ${showFacts ? 'rotate-90' : ''}`} aria-hidden />
            Facts this is based on
          </button>
          {showFacts && (
            <ul className="mt-1.5 space-y-0.5 border-l border-border pl-3 text-xs text-muted">
              {insight.facts.map((f) => (
                <li key={f}>{f}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  )
}
