import { ArrowRight, KeyRound, Link2, Search, Table2 } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Badge, Card, inputClass } from '@/components/ui/primitives'
import { cn } from '@/lib/utils'
import type { DatabaseSchema, SchemaTable } from '@/types/api'

export function SchemaExplorer({ schema, onQueryTable }: {
  schema: DatabaseSchema
  onQueryTable?: (table: string) => void
}) {
  const [selected, setSelected] = useState(schema.tables[0]?.name)
  const [filter, setFilter] = useState('')
  const tables = useMemo(() => {
    const q = filter.trim().toLowerCase()
    return q
      ? schema.tables.filter((t) => t.name.toLowerCase().includes(q) || t.columns.some((c) => c.name.toLowerCase().includes(q)))
      : schema.tables
  }, [schema.tables, filter])
  const table = schema.tables.find((t) => t.name === selected) ?? schema.tables[0]

  return (
    <div className="grid gap-4 lg:grid-cols-[240px_1fr]">
      <Card className="h-fit p-2">
        <div className="relative mb-2">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-subtle" aria-hidden />
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter tables & columns"
            aria-label="Filter tables and columns"
            className={cn(inputClass, 'h-8 pl-8 text-[13px]')}
          />
        </div>
        <ul role="listbox" aria-label="Tables" className="space-y-px">
          {tables.map((t) => (
            <li key={t.name}>
              <button
                type="button"
                role="option"
                aria-selected={t.name === table?.name}
                onClick={() => setSelected(t.name)}
                className={cn(
                  'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm cursor-pointer',
                  t.name === table?.name ? 'bg-surface-2 text-fg' : 'text-muted hover:bg-surface-2 hover:text-fg',
                )}
              >
                <Table2 className="size-3.5 shrink-0 text-subtle" aria-hidden />
                <span className="truncate font-mono text-[13px]">{t.name}</span>
                {t.row_count !== null && (
                  <span className="ml-auto text-[11px] tabular-nums text-subtle">{compactCount(t.row_count)}</span>
                )}
              </button>
            </li>
          ))}
          {tables.length === 0 && <li className="px-2 py-3 text-xs text-subtle">No matches</li>}
        </ul>
      </Card>

      {table && <TableDetail table={table} schema={schema} onQuery={onQueryTable} />}
    </div>
  )
}

function TableDetail({ table, schema, onQuery }: { table: SchemaTable; schema: DatabaseSchema; onQuery?: (t: string) => void }) {
  const incoming = schema.relationships.filter((r) => r.to_table === table.name)
  return (
    <Card className="min-w-0 overflow-hidden">
      <div className="flex flex-wrap items-center gap-3 border-b border-border px-4 py-3">
        <h2 className="font-mono text-base font-semibold text-fg">{table.name}</h2>
        <span className="text-xs text-subtle">
          {table.columns.length} columns{table.row_count !== null && ` · ${table.row_count.toLocaleString()} rows`}
        </span>
        {onQuery && (
          <Button size="sm" variant="ghost" className="ml-auto" onClick={() => onQuery(table.name)}>
            Query in workbench <ArrowRight />
          </Button>
        )}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[36rem] text-[13px]">
          <thead>
            <tr className="border-b border-border text-left text-xs text-subtle">
              <th scope="col" className="px-4 py-2 font-medium">Column</th>
              <th scope="col" className="px-4 py-2 font-medium">Type</th>
              <th scope="col" className="px-4 py-2 font-medium">Details</th>
            </tr>
          </thead>
          <tbody>
            {table.columns.map((c) => (
              <tr key={c.name} className="border-b border-border last:border-0 align-top">
                <td className="whitespace-nowrap px-4 py-2 font-mono text-fg">
                  <span className="inline-flex items-center gap-1.5">
                    {c.primary_key && <KeyRound className="size-3 text-warning" aria-label="Primary key" />}
                    {c.references && <Link2 className="size-3 text-accent" aria-label="Foreign key" />}
                    {c.name}
                  </span>
                </td>
                <td className="whitespace-nowrap px-4 py-2 font-mono text-xs text-muted">
                  {c.type}
                  {!c.nullable && <span className="ml-1.5 text-subtle">not null</span>}
                </td>
                <td className="px-4 py-2 text-xs text-muted">
                  <div className="flex flex-wrap items-center gap-1">
                    {c.primary_key && <Badge tone="warning">Primary key</Badge>}
                    {c.references && <Badge tone="accent">→ {c.references}</Badge>}
                    {c.value_range && (
                      <span>
                        {c.value_range[0]} → {c.value_range[1]}
                      </span>
                    )}
                    {c.sample_values?.map((v) => (
                      <Badge key={v} className="font-mono">{v}</Badge>
                    ))}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {incoming.length > 0 && (
        <div className="border-t border-border px-4 py-3 text-xs text-muted">
          <span className="text-subtle">Referenced by: </span>
          {incoming.map((r, i) => (
            <span key={`${r.from_table}.${r.from_column}`} className="font-mono">
              {i > 0 && ', '}
              {r.from_table}.{r.from_column}
            </span>
          ))}
        </div>
      )}
    </Card>
  )
}

function compactCount(n: number): string {
  return n >= 1000 ? `${(n / 1000).toFixed(n >= 10_000 ? 0 : 1)}k` : String(n)
}
