import { useState, type FormEvent } from 'react'
import { Button, Input, PageHeader, Panel } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { useTheme, type ThemeMode } from '../context/ThemeContext'
import { useToast } from '../context/ToastContext'
import { api, ApiError } from '../services/api'
import { passwordMessage, type FieldErrors } from '../utils/validation'

const MODES: [ThemeMode, string][] = [['light', 'Light'], ['dark', 'Dark'], ['system', 'Match my device']]

export function SettingsPage() {
  const { user } = useAuth()
  const { mode, setMode } = useTheme()
  const toast = useToast()
  const [v, setV] = useState({ current_password: '', new_password: '', confirm_password: '' })
  const [errors, setErrors] = useState<FieldErrors>({})
  const [busy, setBusy] = useState(false)
  const set = (k: keyof typeof v) => (e: React.ChangeEvent<HTMLInputElement>) => { setV({ ...v, [k]: e.target.value }); setErrors((p) => ({ ...p, [k]: '' })) }

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    const errs: FieldErrors = {}
    if (!v.current_password) errs.current_password = 'Enter your current password.'
    const pm = passwordMessage(v.new_password)
    if (pm) errs.new_password = pm
    else if (v.new_password !== v.confirm_password) errs.confirm_password = 'Passwords do not match.'
    setErrors(errs)
    if (Object.keys(errs).length) return
    setBusy(true)
    try {
      await api.auth.changePassword(v)
      setV({ current_password: '', new_password: '', confirm_password: '' }); toast.success('Password changed.')
    } catch (err) {
      if (err instanceof ApiError && Object.keys(err.fields).length) setErrors(err.fields)
      else toast.error(err instanceof ApiError ? err.message : 'Couldn’t change your password. Please try again.')
    } finally { setBusy(false) }
  }

  return (
    <>
      <PageHeader title="Settings" />
      <div className="max-w-2xl space-y-6">
        <Panel title="Appearance">
          <fieldset><legend className="sr-only">Theme</legend>
            <div className="flex flex-wrap gap-x-6 gap-y-2">
              {MODES.map(([m, label]) => (
                <label key={m} className="flex items-center gap-2 text-sm">
                  <input type="radio" name="theme" checked={mode === m} onChange={() => setMode(m)} className="h-4 w-4 accent-[rgb(var(--c-primary))]" />{label}
                </label>))}
            </div>
          </fieldset>
        </Panel>
        <Panel title="Account">
          <dl className="grid gap-3 text-sm sm:grid-cols-2">
            <div><dt className="text-muted">Name</dt><dd className="font-medium">{user?.full_name}</dd></div>
            <div><dt className="text-muted">Email</dt><dd className="font-medium">{user?.email}</dd></div>
          </dl>
        </Panel>
        <Panel title="Change password">
          <form onSubmit={submit} noValidate className="space-y-4">
            <Input label="Current password" type="password" autoComplete="current-password" value={v.current_password} error={errors.current_password} onChange={set('current_password')} />
            <Input label="New password" type="password" autoComplete="new-password" value={v.new_password} error={errors.new_password} onChange={set('new_password')} />
            <Input label="Confirm new password" type="password" autoComplete="new-password" value={v.confirm_password} error={errors.confirm_password} onChange={set('confirm_password')} />
            <Button type="submit" loading={busy}>Change password</Button>
          </form>
        </Panel>
      </div>
    </>
  )
}
