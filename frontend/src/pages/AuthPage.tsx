import { Loader2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Logo } from '@/components/layout/Sidebar'
import { Button } from '@/components/ui/button'
import { Card, inputClass } from '@/components/ui/primitives'
import { useAuth } from '@/hooks/queries'

export default function AuthPage() {
  const [mode, setMode] = useState<'login' | 'signup'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const auth = useAuth(mode)
  const signup = mode === 'signup'

  const submit = (e: FormEvent) => {
    e.preventDefault()
    auth.mutate({ email, password })
  }
  const switchMode = () => {
    setMode(signup ? 'login' : 'signup')
    auth.reset()
  }

  return (
    <main className="flex min-h-full items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex justify-center">
          <Logo />
        </div>
        <Card className="p-6">
          <h1 className="text-lg font-semibold tracking-tight text-fg">{signup ? 'Create your account' : 'Sign in'}</h1>
          <p className="mt-1 text-sm text-muted">
            {signup
              ? 'Your data sources, chats and query history stay private to your account.'
              : 'Ask questions about your data in plain English.'}
          </p>
          <form onSubmit={submit} className="mt-5 space-y-3">
            <div>
              <label htmlFor="auth-email" className="mb-1 block text-xs font-medium text-muted">Email</label>
              <input
                id="auth-email"
                type="email"
                required
                autoComplete="email"
                maxLength={254}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className={inputClass}
              />
            </div>
            <div>
              <label htmlFor="auth-password" className="mb-1 block text-xs font-medium text-muted">Password</label>
              <input
                id="auth-password"
                type="password"
                required
                minLength={signup ? 8 : undefined}
                maxLength={200}
                autoComplete={signup ? 'new-password' : 'current-password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={inputClass}
              />
              {signup && <p className="mt-1 text-xs text-subtle">At least 8 characters.</p>}
            </div>
            {auth.error && (
              <p role="alert" className="text-sm text-danger">
                {auth.error.message}
              </p>
            )}
            <Button type="submit" variant="primary" className="w-full" disabled={auth.isPending}>
              {auth.isPending && <Loader2 className="animate-spin" />} {signup ? 'Create account' : 'Sign in'}
            </Button>
          </form>
        </Card>
        <p className="mt-4 text-center text-sm text-muted">
          {signup ? 'Already have an account?' : 'New to DataPilot?'}{' '}
          <button type="button" onClick={switchMode} className="font-medium text-accent hover:underline">
            {signup ? 'Sign in' : 'Create an account'}
          </button>
        </p>
      </div>
    </main>
  )
}
