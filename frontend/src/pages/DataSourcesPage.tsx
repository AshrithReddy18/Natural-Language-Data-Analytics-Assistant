import { Database, Loader2, Plus, Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { EmptyState, ErrorState, LoadingRows } from '@/components/common/States'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogTrigger } from '@/components/ui/overlays'
import { Badge, Card, StatusDot, inputClass } from '@/components/ui/primitives'
import { useCreateDataset, useDatasets, useDeleteDataset } from '@/hooks/queries'
import type { DataSource } from '@/types/api'

function DataSourceCard({ source }: { source: DataSource }) {
  const remove = useDeleteDataset()
  return (
    <Card className="flex flex-col p-4">
      <div className="flex items-start gap-3">
        <div className="flex size-9 shrink-0 items-center justify-center rounded-lg border border-border bg-surface-2">
          <Database className="size-4 text-accent" aria-hidden />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h2 className="truncate font-medium text-fg">{source.name}</h2>
            {source.is_demo && <Badge tone="accent">Demo</Badge>}
          </div>
          <div className="mt-0.5 flex items-center gap-1.5 text-xs text-muted">
            <StatusDot status={source.status} />
            {source.status === 'connected' ? 'Connected' : source.status === 'error' ? 'Unavailable' : 'Unknown'}
            <span className="text-subtle">·</span>
            {source.kind === 'postgresql' ? 'PostgreSQL' : 'SQLite'}
            {source.table_count !== null && (
              <>
                <span className="text-subtle">·</span> {source.table_count} tables
              </>
            )}
          </div>
        </div>
      </div>
      {source.description && <p className="mt-3 text-sm text-muted">{source.description}</p>}
      {source.status_message && <p className="mt-2 text-xs text-danger">{source.status_message}</p>}
      <code className="mt-3 truncate rounded-md bg-surface-2 px-2 py-1 font-mono text-[11px] text-subtle" title={source.display_url}>
        {source.display_url}
      </code>
      <div className="mt-4 flex items-center gap-2">
        <Button asChild size="sm" variant="secondary">
          <Link to={`/data/${source.id}`}>Explore schema</Link>
        </Button>
        {!source.is_demo && (
          <Button
            size="sm"
            variant="ghost"
            className="ml-auto text-subtle hover:text-danger"
            aria-label={`Remove ${source.name}`}
            disabled={remove.isPending}
            onClick={() => {
              if (window.confirm(`Remove "${source.name}"? Its conversations will be deleted too.`)) remove.mutate(source.id)
            }}
          >
            <Trash2 />
          </Button>
        )}
      </div>
    </Card>
  )
}

function AddDataSourceDialog() {
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({ name: '', url: '', description: '', currency: 'INR' })
  const create = useCreateDataset()

  const submit = (e: FormEvent) => {
    e.preventDefault()
    create.mutate(form, {
      onSuccess: () => {
        setOpen(false)
        setForm({ name: '', url: '', description: '', currency: 'INR' })
        create.reset()
      },
    })
  }
  const field = (key: keyof typeof form) => ({
    value: form[key],
    onChange: (e: { target: { value: string } }) => setForm((f) => ({ ...f, [key]: e.target.value })),
  })

  return (
    <Dialog open={open} onOpenChange={(o) => { setOpen(o); if (!o) create.reset() }}>
      <DialogTrigger asChild>
        <Button variant="primary" size="sm">
          <Plus /> Add data source
        </Button>
      </DialogTrigger>
      <DialogContent title="Add a data source" description="Connect a PostgreSQL database. Credentials are encrypted at rest and never shown again.">
        <form onSubmit={submit} className="space-y-3">
          <div>
            <label htmlFor="ds-name" className="mb-1 block text-xs font-medium text-muted">Name</label>
            <input id="ds-name" required maxLength={120} placeholder="Sales warehouse" className={inputClass} {...field('name')} />
          </div>
          <div>
            <label htmlFor="ds-url" className="mb-1 block text-xs font-medium text-muted">Connection URL</label>
            <input
              id="ds-url"
              required
              placeholder="postgresql://readonly_user:password@host:5432/database"
              className={`${inputClass} font-mono text-[13px]`}
              autoComplete="off"
              spellCheck={false}
              {...field('url')}
            />
            <p className="mt-1 text-xs text-subtle">Use a read-only database user. SQLite files must live in the server's data directory.</p>
          </div>
          <div className="grid grid-cols-[1fr_6rem] gap-3">
            <div>
              <label htmlFor="ds-desc" className="mb-1 block text-xs font-medium text-muted">Description (optional)</label>
              <input id="ds-desc" maxLength={1000} className={inputClass} {...field('description')} />
            </div>
            <div>
              <label htmlFor="ds-currency" className="mb-1 block text-xs font-medium text-muted">Currency</label>
              <input id="ds-currency" required minLength={3} maxLength={3} className={`${inputClass} uppercase`} {...field('currency')} />
            </div>
          </div>
          {create.error && <ErrorState title="Couldn't add the data source" message={create.error.message} />}
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
            <Button type="submit" variant="primary" disabled={create.isPending}>
              {create.isPending && <Loader2 className="animate-spin" />} Test & connect
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export default function DataSourcesPage() {
  const { data, isLoading, error, refetch } = useDatasets()
  return (
    <div className="mx-auto w-full max-w-5xl space-y-5 px-4 py-6 sm:px-6">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex-1">
          <h1 className="text-xl font-semibold tracking-tight text-fg">Data sources</h1>
          <p className="mt-1 text-sm text-muted">Databases DataPilot can query. Every query runs read-only with a timeout and row limit.</p>
        </div>
        <AddDataSourceDialog />
      </div>
      {isLoading && <LoadingRows rows={3} />}
      {error && <ErrorState message={error.message} onRetry={() => refetch()} />}
      {data && data.length === 0 && <EmptyState icon={<Database />} title="No data sources yet" description="Add a PostgreSQL database to get started." />}
      {data && data.length > 0 && (
        <div className="grid gap-4 md:grid-cols-2">
          {data.map((s) => (
            <DataSourceCard key={s.id} source={s} />
          ))}
        </div>
      )}
    </div>
  )
}
