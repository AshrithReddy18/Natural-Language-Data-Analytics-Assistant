import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { api } from '@/services/api'
import { useUIStore } from '@/store/ui'
import type { DataSourceCreate } from '@/types/api'

export const keys = {
  health: ['health'] as const,
  datasets: ['datasets'] as const,
  schema: (id: string) => ['schema', id] as const,
  conversations: ['conversations'] as const,
  conversation: (id: string) => ['conversation', id] as const,
  history: (id?: string) => ['history', id ?? 'all'] as const,
}

export function useHealth() {
  return useQuery({ queryKey: keys.health, queryFn: api.health, refetchInterval: 60_000, retry: 1 })
}

export function useDatasets() {
  return useQuery({ queryKey: keys.datasets, queryFn: api.datasets, staleTime: 60_000 })
}

/** The data source the workspace is pointed at: the saved choice if it still exists, else the demo. */
export function useActiveDataSource() {
  const { data: sources, ...rest } = useDatasets()
  const selectedId = useUIStore((s) => s.dataSourceId)
  const setSelected = useUIStore((s) => s.setDataSourceId)
  const active = sources?.find((s) => s.id === selectedId) ?? sources?.find((s) => s.is_demo) ?? sources?.[0]

  useEffect(() => {
    if (active && active.id !== selectedId) setSelected(active.id)
  }, [active, selectedId, setSelected])

  return { source: active, sources, ...rest }
}

export function useSchema(id: string | undefined) {
  return useQuery({
    queryKey: keys.schema(id ?? ''),
    queryFn: () => api.schema(id as string),
    enabled: Boolean(id),
    staleTime: 5 * 60_000,
  })
}

export function useConversations() {
  return useQuery({ queryKey: keys.conversations, queryFn: api.conversations })
}

export function useConversation(id: string | undefined) {
  return useQuery({
    queryKey: keys.conversation(id ?? ''),
    queryFn: () => api.conversation(id as string),
    enabled: Boolean(id),
    staleTime: Infinity, // updated locally as answers stream in
  })
}

export function useHistory(dataSourceId?: string) {
  return useQuery({ queryKey: keys.history(dataSourceId), queryFn: () => api.history(dataSourceId) })
}

export function useDeleteConversation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: api.deleteConversation,
    onSuccess: (_, id) => {
      qc.removeQueries({ queryKey: keys.conversation(id) })
      void qc.invalidateQueries({ queryKey: keys.conversations })
      void qc.invalidateQueries({ queryKey: ['history'] })
    },
  })
}

export function useCreateDataset() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: DataSourceCreate) => api.createDataset(data),
    onSuccess: () => void qc.invalidateQueries({ queryKey: keys.datasets }),
  })
}

export function useUpdateDataset(id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: Partial<DataSourceCreate>) => api.updateDataset(id, data),
    onSuccess: () => void qc.invalidateQueries({ queryKey: keys.datasets }),
  })
}

export function useDeleteDataset() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: api.deleteDataset,
    onSuccess: () => void qc.invalidateQueries({ queryKey: keys.datasets }),
  })
}
