import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { keys } from '@/hooks/queries'
import { ApiError, streamChat } from '@/services/api'
import { useChatStore } from '@/store/chat'
import type { ConversationDetail } from '@/types/api'

/** Sends a question, streams pipeline progress into the chat store, and merges the final
 *  answer into the cached conversation so no refetch is needed. */
export function useAsk() {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const abortRef = useRef<AbortController | null>(null)
  const { start, setConversation, updateStep, fail, clear } = useChatStore.getState()

  const ask = useCallback(
    async (question: string, dataSourceId: string, conversationId: string | null) => {
      if (useChatStore.getState().pending && !useChatStore.getState().pending?.error) return
      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller
      start(question, conversationId)

      try {
        await streamChat(
          { question, data_source_id: dataSourceId, conversation_id: conversationId },
          (event) => {
            switch (event.type) {
              case 'conversation':
                setConversation(event.conversation_id)
                if (!conversationId) {
                  const now = new Date().toISOString()
                  qc.setQueryData<ConversationDetail>(keys.conversation(event.conversation_id), {
                    id: event.conversation_id,
                    title: event.title,
                    data_source_id: dataSourceId,
                    created_at: now,
                    updated_at: now,
                    message_count: 0,
                    messages: [],
                  })
                  navigate(`/c/${event.conversation_id}`, { replace: false })
                }
                void qc.invalidateQueries({ queryKey: keys.conversations })
                break
              case 'step':
                updateStep(event.step, event.status, event.detail)
                break
              case 'result': {
                const { conversation_id, user_message, assistant_message } = event.data
                qc.setQueryData<ConversationDetail>(keys.conversation(conversation_id), (prev) =>
                  prev
                    ? {
                        ...prev,
                        message_count: prev.message_count + 2,
                        messages: [...prev.messages, user_message, assistant_message],
                      }
                    : prev,
                )
                clear()
                void qc.invalidateQueries({ queryKey: keys.conversations })
                void qc.invalidateQueries({ queryKey: ['history'] })
                break
              }
              case 'error':
                fail({ code: event.code, message: event.message })
                break
            }
          },
          controller.signal,
        )
      } catch (e) {
        if (controller.signal.aborted) {
          clear()
          return
        }
        const err = e instanceof ApiError ? e : new ApiError(0, 'unknown', 'Something went wrong.')
        fail({ code: err.code, message: err.message })
      }
    },
    [qc, navigate, start, setConversation, updateStep, fail, clear],
  )

  const cancel = useCallback(() => {
    abortRef.current?.abort()
    clear()
  }, [clear])

  return { ask, cancel }
}
