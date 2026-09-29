import { ArrowUp, Square } from 'lucide-react'
import { forwardRef, useImperativeHandle, useRef, useState, type KeyboardEvent } from 'react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export interface ComposerHandle {
  focus: () => void
  setValue: (value: string) => void
}

export const Composer = forwardRef<
  ComposerHandle,
  {
    onSubmit: (text: string) => void
    onStop?: () => void
    busy?: boolean
    disabled?: boolean
    placeholder?: string
    size?: 'md' | 'lg'
    autoFocus?: boolean
  }
>(({ onSubmit, onStop, busy, disabled, placeholder = 'Ask a question about your data…', size = 'md', autoFocus }, ref) => {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useImperativeHandle(ref, () => ({
    focus: () => textareaRef.current?.focus(),
    setValue: (v: string) => {
      setValue(v)
      requestAnimationFrame(() => textareaRef.current?.focus())
    },
  }))

  const submit = () => {
    const text = value.trim()
    if (!text || busy || disabled) return
    onSubmit(text)
    setValue('')
  }

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      submit()
    }
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        submit()
      }}
      className={cn(
        'group relative flex items-end gap-2 rounded-2xl border border-border bg-surface shadow-sm transition-colors focus-within:border-border-strong',
        size === 'lg' ? 'p-2.5 pl-4' : 'p-2 pl-3.5',
        disabled && 'opacity-60',
      )}
    >
      <label htmlFor="composer" className="sr-only">
        Ask a question
      </label>
      <textarea
        id="composer"
        ref={textareaRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={onKeyDown}
        placeholder={placeholder}
        rows={1}
        autoFocus={autoFocus}
        disabled={disabled}
        maxLength={2000}
        className={cn(
          'field-sizing-content max-h-40 min-h-9 flex-1 resize-none bg-transparent py-1.5 text-fg placeholder:text-subtle focus:outline-none focus-visible:outline-none',
          size === 'lg' ? 'text-base' : 'text-[15px]',
        )}
      />
      {busy && onStop ? (
        <Button type="button" size="icon" variant="secondary" onClick={onStop} aria-label="Stop" className="rounded-xl">
          <Square className="size-3.5 fill-current" />
        </Button>
      ) : (
        <Button
          type="submit"
          size="icon"
          variant="primary"
          disabled={!value.trim() || busy || disabled}
          aria-label="Send question"
          className="rounded-xl"
        >
          <ArrowUp />
        </Button>
      )}
    </form>
  )
})
Composer.displayName = 'Composer'
