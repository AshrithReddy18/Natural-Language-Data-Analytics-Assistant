import { create } from 'zustand'
import type { StepId, StepStatus } from '@/types/api'

export const STEP_LABELS: Record<StepId, string> = {
  understand: 'Understanding your question',
  schema: 'Inspecting database schema',
  generate: 'Generating SQL',
  validate: 'Validating query',
  execute: 'Running query',
  visualize: 'Preparing visualization',
  insight: 'Writing insight',
}

export const STEP_ORDER: StepId[] = ['understand', 'schema', 'generate', 'validate', 'execute', 'visualize', 'insight']

export interface StepState {
  status: StepStatus
  detail: string | null
  /** Problems that were recovered from, e.g. a validation error fixed by a repair attempt. */
  notes: string[]
}

export interface PendingTurn {
  question: string
  conversationId: string | null
  steps: Record<StepId, StepState>
  error: { code: string; message: string } | null
}

const initialSteps = (): Record<StepId, StepState> =>
  Object.fromEntries(
    STEP_ORDER.map((s): [StepId, StepState] => [s, { status: 'pending', detail: null, notes: [] }]),
  ) as Record<StepId, StepState>

/** The in-flight question. Kept outside components so it survives the route change from
 *  "/" to "/c/:id" when a new conversation is created mid-stream. */
interface ChatState {
  pending: PendingTurn | null
  start: (question: string, conversationId: string | null) => void
  setConversation: (conversationId: string) => void
  updateStep: (step: StepId, status: StepStatus, detail: string | null) => void
  fail: (error: { code: string; message: string }) => void
  clear: () => void
}

export const useChatStore = create<ChatState>()((set) => ({
  pending: null,
  start: (question, conversationId) =>
    set({ pending: { question, conversationId, steps: initialSteps(), error: null } }),
  setConversation: (conversationId) => set((s) => (s.pending ? { pending: { ...s.pending, conversationId } } : s)),
  updateStep: (step, status, detail) =>
    set((s) => {
      if (!s.pending) return s
      const prev = s.pending.steps[step]
      const recovered = prev.status === 'error' && prev.detail && status !== 'error'
      const steps = {
        ...s.pending.steps,
        [step]: { status, detail, notes: recovered ? [...prev.notes, prev.detail as string] : prev.notes },
      }
      // A repair loop re-runs generate → validate → execute: reset the later steps, keeping
      // their errors as notes so the user can see what was corrected.
      if (status === 'running' && step === 'generate' && prev.status !== 'pending') {
        for (const later of ['validate', 'execute'] as const) {
          const p = steps[later]
          const notes = p.status === 'error' && p.detail ? [...p.notes, p.detail] : p.notes
          steps[later] = { status: 'pending', detail: null, notes }
        }
      }
      return { pending: { ...s.pending, steps } }
    }),
  fail: (error) => set((s) => (s.pending ? { pending: { ...s.pending, error } } : s)),
  clear: () => set({ pending: null }),
}))
