import { Database, FileSpreadsheet, FileUp, Loader2, Plus, Trash2, Upload, X } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { EmptyState, ErrorState, LoadingRows } from '@/components/common/States'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogTrigger } from '@/components/ui/overlays'
import { Badge, Card, StatusDot, inputClass } from '@/components/ui/primitives'
import { useCreateDataset, useDatasets, useDeleteDataset, useUploadDataset } from '@/hooks/queries'
import { sourceKindLabel, tableCountLabel } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { DataSource } from '@/types/api'

function DataSourceCard({ source }: { source: DataSource }) {
  const remove = useDeleteDataset()
  return (
    <Card className="flex flex-col p-4">
      <div className="flex items-start gap-3">
        <div className="flex size-9 shrink-0 items-center justify-center rounded-lg border border-border bg-surface-2">
          {source.kind === 'upload' ? (
            <FileSpreadsheet className="size-4 text-accent" aria-hidden />
          ) : (
            <Database className="size-4 text-accent" aria-hidden />
          )}
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
            {sourceKindLabel(source.kind)}
            {source.table_count !== null && (
              <>
                <span className="text-subtle">·</span> {tableCountLabel(source.table_count)}
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

const MAX_UPLOAD_MB = 4
const ACCEPT = '.csv,.tsv,.txt,.xlsx,.xlsm'

function formatSize(bytes: number) {
  return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function UploadForm({ onDone, onCancel }: { onDone: () => void; onCancel: () => void }) {
  const [files, setFiles] = useState<File[]>([])
  const [name, setName] = useState('')
  const [currency, setCurrency] = useState('INR')
  const [dragging, setDragging] = useState(false)
  const upload = useUploadDataset()
  const total = files.reduce((n, f) => n + f.size, 0)
  const tooBig = total > MAX_UPLOAD_MB * 1024 * 1024

  const add = (list: FileList | null) => {
    if (!list?.length) return
    const added = Array.from(list)
    setFiles((current) => [...current, ...added.filter((f) => !current.some((c) => c.name === f.name))])
    if (!name) setName(added[0].name.replace(/\.[^.]+$/, ''))
    upload.reset()
  }
  const submit = (e: FormEvent) => {
    e.preventDefault()
    upload.mutate({ name, files, currency }, { onSuccess: onDone })
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <label
        htmlFor="ds-files"
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          add(e.dataTransfer.files)
        }}
        className={cn(
          'flex cursor-pointer flex-col items-center gap-1.5 rounded-xl border border-dashed border-border px-4 py-6 text-center transition-colors hover:border-accent/60 hover:bg-surface-2/50',
          dragging && 'border-accent bg-surface-2',
        )}
      >
        <FileUp className="size-6 text-accent" aria-hidden />
        <span className="text-sm font-medium text-fg">Drop CSV or Excel files here, or click to choose</span>
        <span className="text-xs text-subtle">
          Each file (and each Excel sheet) becomes a table. Up to {MAX_UPLOAD_MB} MB in total.
        </span>
        <input
          id="ds-files"
          type="file"
          multiple
          accept={ACCEPT}
          className="sr-only"
          onChange={(e) => {
            add(e.target.files)
            e.target.value = ''
          }}
        />
      </label>
      {files.length > 0 && (
        <ul className="space-y-1" aria-label="Chosen files">
          {files.map((f) => (
            <li key={f.name} className="flex items-center gap-2 rounded-md bg-surface-2 px-2.5 py-1.5 text-sm">
              <FileSpreadsheet className="size-4 shrink-0 text-subtle" aria-hidden />
              <span className="min-w-0 flex-1 truncate text-fg">{f.name}</span>
              <span className="text-xs text-subtle">{formatSize(f.size)}</span>
              <button
                type="button"
                onClick={() => setFiles((current) => current.filter((c) => c !== f))}
                className="rounded p-0.5 text-subtle hover:text-danger"
                aria-label={`Remove ${f.name}`}
              >
                <X className="size-3.5" />
              </button>
            </li>
          ))}
        </ul>
      )}
      {tooBig && (
        <p className="text-xs text-danger">
          These files add up to {formatSize(total)}; the limit is {MAX_UPLOAD_MB} MB. Remove some, or connect a database
          instead.
        </p>
      )}
      <div className="grid grid-cols-[1fr_6rem] gap-3">
        <div>
          <label htmlFor="ds-upload-name" className="mb-1 block text-xs font-medium text-muted">Name</label>
          <input
            id="ds-upload-name"
            required
            maxLength={120}
            placeholder="Q2 sales"
            className={inputClass}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <div>
          <label htmlFor="ds-upload-currency" className="mb-1 block text-xs font-medium text-muted">Currency</label>
          <input
            id="ds-upload-currency"
            required
            minLength={3}
            maxLength={3}
            className={`${inputClass} uppercase`}
            value={currency}
            onChange={(e) => setCurrency(e.target.value)}
          />
        </div>
      </div>
      {upload.error && <ErrorState title="Couldn't load your files" message={upload.error.message} />}
      <div className="flex justify-end gap-2 pt-1">
        <Button variant="ghost" onClick={onCancel}>Cancel</Button>
        <Button type="submit" variant="primary" disabled={upload.isPending || files.length === 0 || tooBig}>
          {upload.isPending && <Loader2 className="animate-spin" />} Upload
        </Button>
      </div>
    </form>
  )
}

function ConnectForm({ onDone, onCancel }: { onDone: () => void; onCancel: () => void }) {
  const [form, setForm] = useState({ name: '', url: '', description: '', currency: 'INR' })
  const create = useCreateDataset()

  const submit = (e: FormEvent) => {
    e.preventDefault()
    create.mutate(form, { onSuccess: onDone })
  }
  const field = (key: keyof typeof form) => ({
    value: form[key],
    onChange: (e: { target: { value: string } }) => setForm((f) => ({ ...f, [key]: e.target.value })),
  })

  return (
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
        <p className="mt-1 text-xs text-subtle">
          A PostgreSQL database reachable from the internet. Use a read-only database user; credentials are encrypted at
          rest and never shown again.
        </p>
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
        <Button variant="ghost" onClick={onCancel}>Cancel</Button>
        <Button type="submit" variant="primary" disabled={create.isPending}>
          {create.isPending && <Loader2 className="animate-spin" />} Test & connect
        </Button>
      </div>
    </form>
  )
}

const ADD_MODES = [
  { value: 'upload', label: 'Upload files', icon: Upload },
  { value: 'connect', label: 'Connect database', icon: Database },
] as const

function AddDataSourceDialog() {
  const [open, setOpen] = useState(false)
  const [mode, setMode] = useState<(typeof ADD_MODES)[number]['value']>('upload')
  const close = () => setOpen(false)

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="primary" size="sm">
          <Plus /> Add data source
        </Button>
      </DialogTrigger>
      <DialogContent title="Add a data source" description="Only you can see the data sources you add.">
        <div role="tablist" aria-label="How to add data" className="mb-4 grid grid-cols-2 gap-1 rounded-lg bg-surface-2 p-1">
          {ADD_MODES.map(({ value, label, icon: Icon }) => (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={mode === value}
              onClick={() => setMode(value)}
              className={cn(
                'flex items-center justify-center gap-1.5 rounded-md px-3 py-1.5 text-sm transition-colors',
                mode === value ? 'bg-surface text-fg shadow-sm' : 'text-muted hover:text-fg',
              )}
            >
              <Icon className="size-4" aria-hidden /> {label}
            </button>
          ))}
        </div>
        {/* The dialog unmounts its content when closed, so each visit starts with empty forms. */}
        {mode === 'upload' ? <UploadForm onDone={close} onCancel={close} /> : <ConnectForm onDone={close} onCancel={close} />}
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
          <p className="mt-1 text-sm text-muted">
            Upload spreadsheets or connect a database, then ask questions about it. Every query runs read-only with a
            timeout and row limit.
          </p>
        </div>
        <AddDataSourceDialog />
      </div>
      {isLoading && <LoadingRows rows={3} />}
      {error && <ErrorState message={error.message} onRetry={() => refetch()} />}
      {data && data.length === 0 && <EmptyState icon={<Database />} title="No data sources yet" description="Upload a CSV or Excel file, or connect a PostgreSQL database, to get started." />}
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
