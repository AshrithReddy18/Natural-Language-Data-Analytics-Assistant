import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function humanize(name: string): string {
  const text = name.replace(/_/g, ' ').trim()
  return text.charAt(0).toUpperCase() + text.slice(1)
}
