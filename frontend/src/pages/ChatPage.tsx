import { useCallback, useEffect, useLayoutEffect, useRef } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { Composer, type ComposerHandle } from '@/components/chat/Composer'
import { AssistantMessage, PendingAssistant, UserMessage } from '@/components/chat/Messages'
import { Welcome } from '@/components/chat/Welcome'
import type { AskState } from '@/components/layout/AppShell'
import { ErrorState, LoadingRows } from '@/components/common/States'
import { useActiveDataSource, useConversation, useHealth } from '@/hooks/queries'
import { useAsk } from '@/hooks/useAsk'
import { useChatStore } from '@/store/chat'
import { useUIStore } from '@/store/ui'

export default function ChatPage() {
  const { conversationId } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const { source } = useActiveDataSource()
  const setSelected = useUIStore((s) => s.setDataSourceId)
  const { data: health } = useHealth()
  const conversation = useConversation(conversationId)
  const pending = useChatStore((s) => s.pending)
  const clearPending = useChatStore((s) => s.clear)
  const { ask, cancel } = useAsk()
  const composerRef = useRef<ComposerHandle>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const syncedFor = useRef<string | null>(null)

  const conversationSourceId = conversation.data?.data_source_id
  const activeSourceId = conversationSourceId ?? source?.id
  const showPending = pending && pending.conversationId === (conversationId ?? null)
  const busy = Boolean(pending && !pending.error)

  // Keep the header's data-source picker in sync with the open conversation; picking a different
  // source while a conversation is open starts a new chat against that source.
  useEffect(() => {
    if (!conversationId || !conversationSourceId) return
    if (syncedFor.current !== conversationId) {
      syncedFor.current = conversationId
      setSelected(conversationSourceId)
    } else if (source && source.id !== conversationSourceId && !busy) {
      navigate('/')
    }
  }, [conversationId, conversationSourceId, source, setSelected, navigate, busy])

  const send = useCallback(
    (text: string) => {
      if (!activeSourceId) return
      void ask(text, activeSourceId, conversationId ?? null)
    },
    [ask, activeSourceId, conversationId],
  )

  // A question handed over from the search palette.
  useEffect(() => {
    const question = (location.state as AskState | null)?.ask
    if (question && activeSourceId) {
      navigate(location.pathname, { replace: true, state: null })
      send(question)
    }
  }, [location.state, location.pathname, activeSourceId, navigate, send])

  const messages = conversation.data?.messages ?? []
  useLayoutEffect(() => {
    bottomRef.current?.scrollIntoView({ block: 'end' })
  }, [messages.length, showPending, conversationId])
  useEffect(() => {
    if (showPending && !pending?.error) bottomRef.current?.scrollIntoView({ block: 'end', behavior: 'smooth' })
  }, [showPending, pending])

  if (!conversationId && !showPending) {
    return <Welcome source={source} llmConfigured={health?.llm_configured ?? true} onAsk={send} />
  }

  const lastAssistantIndex = messages.map((m) => m.role).lastIndexOf('assistant')

  return (
    <div className="flex min-h-full flex-col">
      <div className="mx-auto w-full max-w-3xl flex-1 space-y-6 px-4 pb-6 pt-6 sm:px-6">
        {conversation.isLoading && <LoadingRows rows={4} />}
        {conversation.isError && (
          <ErrorState
            title="Conversation not found"
            message="It may have been deleted."
            action={<button className="text-sm text-accent hover:underline cursor-pointer" onClick={() => navigate('/')}>Start a new chat</button>}
          />
        )}
        {messages.map((m, i) =>
          m.role === 'user' ? (
            <UserMessage key={m.id} text={m.content} />
          ) : (
            <AssistantMessage
              key={m.id}
              message={m}
              interactive={i === lastAssistantIndex && !busy}
              onAnswer={send}
              onRetry={() => {
                const question = messages[i - 1]?.role === 'user' ? messages[i - 1].content : m.analysis?.question
                if (question) send(question)
              }}
            />
          ),
        )}
        {showPending && pending && (
          <>
            <UserMessage text={pending.question} />
            <PendingAssistant
              turn={pending}
              onRetry={() => activeSourceId && void ask(pending.question, activeSourceId, pending.conversationId)}
              onDismiss={clearPending}
            />
          </>
        )}
        <div ref={bottomRef} />
      </div>
      <div className="sticky bottom-0 bg-gradient-to-t from-bg via-bg to-transparent pb-4 pt-6">
        <div className="mx-auto w-full max-w-3xl px-4 sm:px-6">
          <Composer
            ref={composerRef}
            onSubmit={send}
            onStop={cancel}
            busy={busy}
            disabled={!activeSourceId}
            placeholder="Ask a follow-up question…"
          />
          <p className="mt-2 text-center text-[11px] text-subtle">
            Answers come from SQL run on your data. Review the generated SQL for anything important.
          </p>
        </div>
      </div>
    </div>
  )
}
