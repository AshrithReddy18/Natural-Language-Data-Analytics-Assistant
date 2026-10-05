import { MutationCache, QueryCache, QueryClient } from '@tanstack/react-query'
import { ApiError } from '@/services/api'

export const ME_KEY = ['me'] as const

export function createQueryClient() {
  // Any 401 means the session ended (expired or signed out elsewhere): drop back to sign-in.
  const onError = (error: unknown) => {
    if (error instanceof ApiError && error.status === 401) client.setQueryData(ME_KEY, null)
  }
  const client: QueryClient = new QueryClient({
    queryCache: new QueryCache({ onError }),
    mutationCache: new MutationCache({ onError }),
    defaultOptions: {
      queries: {
        refetchOnWindowFocus: false,
        // Don't retry client errors (404 etc.); retry transient failures once.
        retry: (count, error) => !(error instanceof ApiError && error.status >= 400 && error.status < 500) && count < 1,
      },
    },
  })
  return client
}
