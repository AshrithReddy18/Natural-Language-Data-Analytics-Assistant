import { ArrowLeft, Check, Loader2, MessageSquare, RefreshCw } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ErrorState, LoadingRows } from '@/components/common/States'
import { SchemaExplorer } from '@/components/schema/SchemaExplorer'
import { Button } from '@/components/ui/button'
import { Card, StatusDot, inputClass } from '@/components/ui/primitives'
import { useDatasets, useSchema, useUpdateDataset } from '@/hooks/queries'
import { useQueryClient } from '@tanstack/react-query'
import { api } from '@/services/api'
import { keys } from '@/hooks/queries'
import { cn } from '@/lib/utils'
import { useUIStore } from '@/store/ui'

export default function SchemaPage() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { data: sources } = useDatasets()
  const source = sources?.find((s) => s.id === id)
  const schema = useSchema(id)
  const setWorkbenchSql = useUIStore((s) => s.setWorkbenchSql)
  const setSelected = useUIStore((s) => s.setDataSourceId)
  const [refreshing, setRefreshing] = useState(false)

  const refresh = async () => {
    setRefreshing(true)
    try {
      qc.setQueryData(keys.schema(id), await api.schema(id, true))
    } finally {
      setRefreshing(false)
    }
  }

  return (
    <div className="mx-auto w-full max-w-6xl space-y-5 px-4 py-6 sm:px-6">
      <Link to="/data" className="inline-flex items-center gap-1 text-sm text-muted hover:text-fg">
        <ArrowLeft className="size-4" aria-hidden /> Data sources
      </Link>
      <div className="flex flex-wrap items-start gap-3">
        <div className="min-w-0 flex-1">
          <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight text-fg">
            {source && <StatusDot status={source.status} />}
            {source?.name ?? 'Schema'}
          </h1>
          {source?.description && <p className="mt-1 text-sm text-muted">{source.description}</p>}
        </div>
        <Button size="sm" variant="secondary" onClick={refresh} disabled={refreshing}>
          <RefreshCw className={cn(refreshing && 'animate-spin')} /> Refresh schema
        </Button>
        <Button
          size="sm"
          variant="primary"
          onClick={() => {
            setSelected(id)
            navigate('/')
          }}
        >
          <MessageSquare /> Ask about this data
        </Button>
      </div>

      {schema.isLoading && <LoadingRows rows={6} />}
      {schema.error && <ErrorState title="Couldn't load the schema" message={schema.error.message} onRetry={() => schema.refetch()} />}
      {schema.data && (
        <SchemaExplorer
          schema={schema.data}
          onQueryTable={(t) => {
            setSelected(id)
            setWorkbenchSql(`SELECT *\nFROM ${t}\nLIMIT 50;`)
            navigate('/sql')
          }}
        />
      )}

      {source && (
        <BusinessNotes key={source.business_notes ?? ''} id={source.id} notes={source.business_notes ?? ''} readOnly={source.is_demo} />
      )}
    </div>
  )
}

function BusinessNotes({ id, notes, readOnly }: { id: string; notes: string; readOnly: boolean }) {
  const [value, setValue] = useState(notes)
  const update = useUpdateDataset(id)
  const dirty = value !== notes
  return (
    <Card className="p-4">
      <h2 className="text-sm font-semibold text-fg">Business definitions</h2>
      <p className="mt-1 text-sm text-muted">
        How metrics are defined for this database (e.g. what counts as revenue). These are given to the AI with every question —
        a lightweight semantic layer you can edit.
        {readOnly && ' The demo is shared by everyone, so its definitions are read-only.'}
      </p>
      <label htmlFor="business-notes" className="sr-only">Business definitions</label>
      <textarea
        id="business-notes"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        rows={7}
        maxLength={4000}
        readOnly={readOnly}
        className={cn(inputClass, 'mt-3 font-mono text-[12.5px] leading-relaxed')}
      />
      <div className={cn('mt-2 flex items-center justify-end gap-2', readOnly && 'hidden')}>
        {update.isSuccess && !dirty && (
          <span className="flex items-center gap-1 text-xs text-success"><Check className="size-3.5" /> Saved</span>
        )}
        {update.error && <span className="text-xs text-danger">{update.error.message}</span>}
        <Button size="sm" variant="primary" disabled={!dirty || update.isPending} onClick={() => update.mutate({ business_notes: value })}>
          {update.isPending && <Loader2 className="animate-spin" />} Save definitions
        </Button>
      </div>
    </Card>
  )
}
