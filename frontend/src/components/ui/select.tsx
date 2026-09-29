import * as SelectPrimitive from '@radix-ui/react-select'
import { Check, ChevronDown } from 'lucide-react'
import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

export interface SelectOption {
  value: string
  label: ReactNode
  hint?: ReactNode
}

export function Select({
  value,
  onValueChange,
  options,
  placeholder,
  ariaLabel,
  className,
  icon,
}: {
  value: string | undefined
  onValueChange: (value: string) => void
  options: SelectOption[]
  placeholder?: string
  ariaLabel: string
  className?: string
  icon?: ReactNode
}) {
  return (
    <SelectPrimitive.Root value={value} onValueChange={onValueChange}>
      <SelectPrimitive.Trigger
        aria-label={ariaLabel}
        className={cn(
          'inline-flex h-8 min-w-0 items-center gap-2 rounded-lg border border-border bg-surface px-2.5 text-[13px] text-fg transition-colors hover:border-border-strong hover:bg-surface-2 data-[placeholder]:text-subtle cursor-pointer',
          className,
        )}
      >
        {icon}
        <span className="truncate">
          <SelectPrimitive.Value placeholder={placeholder} />
        </span>
        <SelectPrimitive.Icon className="ml-auto">
          <ChevronDown className="size-3.5 text-subtle" />
        </SelectPrimitive.Icon>
      </SelectPrimitive.Trigger>
      <SelectPrimitive.Portal>
        <SelectPrimitive.Content
          position="popper"
          sideOffset={6}
          className="z-50 min-w-[var(--radix-select-trigger-width)] overflow-hidden rounded-lg border border-border bg-surface p-1 shadow-xl"
        >
          <SelectPrimitive.Viewport>
            {options.map((o) => (
              <SelectPrimitive.Item
                key={o.value}
                value={o.value}
                className="relative flex cursor-pointer select-none items-center gap-2 rounded-md py-1.5 pl-2 pr-8 text-[13px] text-fg outline-none data-[highlighted]:bg-surface-2"
              >
                <div className="min-w-0">
                  <SelectPrimitive.ItemText>{o.label}</SelectPrimitive.ItemText>
                  {o.hint && <div className="text-[11px] text-subtle">{o.hint}</div>}
                </div>
                <SelectPrimitive.ItemIndicator className="absolute right-2">
                  <Check className="size-3.5 text-accent" />
                </SelectPrimitive.ItemIndicator>
              </SelectPrimitive.Item>
            ))}
          </SelectPrimitive.Viewport>
        </SelectPrimitive.Content>
      </SelectPrimitive.Portal>
    </SelectPrimitive.Root>
  )
}
