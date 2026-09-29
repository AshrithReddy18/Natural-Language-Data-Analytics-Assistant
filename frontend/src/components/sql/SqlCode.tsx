import { Check, Copy } from 'lucide-react'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { tokenLines, type TokenType } from '@/lib/sql'
import { cn } from '@/lib/utils'

const TOKEN_CLASS: Record<TokenType, string> = {
  keyword: 'text-[var(--code-keyword)] font-medium',
  function: 'text-[var(--code-function)]',
  string: 'text-[var(--code-string)]',
  number: 'text-[var(--code-number)]',
  comment: 'text-[var(--code-comment)] italic',
  operator: 'text-muted',
  identifier: 'text-fg',
  space: '',
}

export function CopyButton({ text, label = 'Copy' }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      /* clipboard unavailable (insecure context) — nothing useful to do */
    }
  }
  return (
    <Button variant="ghost" size="sm" onClick={copy} aria-label={copied ? 'Copied' : `${label} to clipboard`}>
      {copied ? <Check className="text-success" /> : <Copy />}
      <span aria-live="polite">{copied ? 'Copied' : label}</span>
    </Button>
  )
}

/** Syntax-highlighted SQL with line numbers. */
export function SqlCode({ sql, className, maxHeight = 'max-h-96' }: { sql: string; className?: string; maxHeight?: string }) {
  const lines = tokenLines(sql)
  return (
    <div className={cn('overflow-auto rounded-lg border border-border bg-surface-2/60', maxHeight, className)}>
      <pre className="py-2.5 font-mono text-[12.5px] leading-[1.6]" aria-label="SQL query">
        <code>
          {lines.map((line, i) => (
            <div key={i} className="flex">
              <span className="w-10 shrink-0 select-none pr-3 text-right text-subtle/70" aria-hidden>
                {i + 1}
              </span>
              <span className="whitespace-pre pr-4">
                {line.map((t, j) => (
                  <span key={j} className={TOKEN_CLASS[t.type]}>
                    {t.text}
                  </span>
                ))}
                {line.length === 0 && ' '}
              </span>
            </div>
          ))}
        </code>
      </pre>
    </div>
  )
}
