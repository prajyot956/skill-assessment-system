import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { AuthLayout } from '../layouts/AuthLayout'
import { Alert, Button, Input } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { api, ApiError } from '../services/api'
import { isValidEmail, passwordMessage, type FieldErrors } from '../utils/validation'

function useForm() {
  const [errors, setErrors] = useState<FieldErrors>({})
  const [formError, setFormError] = useState('')
  const [busy, setBusy] = useState(false)
  const fail = (e: unknown) => {
    if (e instanceof ApiError) { setErrors(e.fields); setFormError(Object.keys(e.fields).length ? '' : e.message) }
    else setFormError('Something went wrong. Please try again.')
  }
  const clear = (k: string) => setErrors((p) => { const n = { ...p }; delete n[k]; return n })
  return { errors, setErrors, formError, setFormError, busy, setBusy, fail, clear }
}

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const f = useForm()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [remember, setRemember] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    const errs: FieldErrors = {}
    if (!isValidEmail(email)) errs.email = 'Enter a valid email address.'
    if (!password) errs.password = 'Enter your password.'
    f.setErrors(errs); f.setFormError('')
    if (Object.keys(errs).length) return
    f.setBusy(true)
    try { await login(email, password, remember); navigate('/', { replace: true }) }
    catch (err) { f.fail(err) } finally { f.setBusy(false) }
  }

  return (
    <AuthLayout title="Welcome back" subtitle="Sign in to continue your skill journey.">
      <form onSubmit={submit} noValidate className="space-y-4">
        {f.formError && <Alert>{f.formError}</Alert>}
        <Input label="Email" type="email" autoComplete="email" value={email} error={f.errors.email}
          onChange={(e) => { setEmail(e.target.value); f.clear('email') }} />
        <Input label="Password" type="password" autoComplete="current-password" value={password} error={f.errors.password}
          onChange={(e) => { setPassword(e.target.value); f.clear('password') }} />
        <div className="flex items-center justify-between text-sm">
          <label className="flex items-center gap-2"><input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} className="h-4 w-4 accent-[rgb(var(--c-primary))]" />Keep me signed in</label>
          <Link to="/forgot-password" className="font-medium text-primary hover:underline">Forgot password?</Link>
        </div>
        <Button type="submit" loading={f.busy} className="w-full">Sign in</Button>
      </form>
      <p className="mt-6 text-sm text-muted">New here? <Link to="/register" className="font-medium text-primary hover:underline">Create an account</Link></p>
    </AuthLayout>
  )
}

export function RegisterPage() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const f = useForm()
  const [v, setV] = useState({ full_name: '', email: '', password: '', confirm_password: '' })
  const set = (k: keyof typeof v) => (e: React.ChangeEvent<HTMLInputElement>) => { setV({ ...v, [k]: e.target.value }); f.clear(k) }

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    const errs: FieldErrors = {}
    if (!v.full_name.trim()) errs.full_name = 'Enter your full name.'
    if (!isValidEmail(v.email)) errs.email = 'Enter a valid email address.'
    const pm = passwordMessage(v.password)
    if (pm) errs.password = pm
    else if (v.password !== v.confirm_password) errs.confirm_password = 'Passwords do not match.'
    f.setErrors(errs); f.setFormError('')
    if (Object.keys(errs).length) return
    f.setBusy(true)
    try { await register(v); navigate('/', { replace: true }) }
    catch (err) { f.fail(err) } finally { f.setBusy(false) }
  }

  return (
    <AuthLayout title="Create your account" subtitle="It takes a minute. You can add your resume next.">
      <form onSubmit={submit} noValidate className="space-y-4">
        {f.formError && <Alert>{f.formError}</Alert>}
        <Input label="Full name" autoComplete="name" value={v.full_name} error={f.errors.full_name} onChange={set('full_name')} />
        <Input label="Email" type="email" autoComplete="email" value={v.email} error={f.errors.email} onChange={set('email')} />
        <Input label="Password" type="password" autoComplete="new-password" value={v.password} error={f.errors.password}
          hint="8+ characters with upper and lower case letters and a number." onChange={set('password')} />
        <Input label="Confirm password" type="password" autoComplete="new-password" value={v.confirm_password} error={f.errors.confirm_password} onChange={set('confirm_password')} />
        <Button type="submit" loading={f.busy} className="w-full">Create account</Button>
      </form>
      <p className="mt-6 text-sm text-muted">Already registered? <Link to="/login" className="font-medium text-primary hover:underline">Sign in</Link></p>
    </AuthLayout>
  )
}

export function ForgotPasswordPage() {
  const f = useForm()
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!isValidEmail(email)) { f.setErrors({ email: 'Enter a valid email address.' }); return }
    f.setBusy(true); f.setFormError('')
    try { await api.auth.forgot(email); setSent(true) } catch (err) { f.fail(err) } finally { f.setBusy(false) }
  }

  return (
    <AuthLayout title="Reset your password" subtitle="We’ll email you a link to choose a new one.">
      {sent ? (
        <div className="space-y-4">
          <Alert kind="info">If that email is registered, a reset link is on its way. It expires in 30 minutes.</Alert>
          <Link to="/login" className="text-sm font-medium text-primary hover:underline">Back to sign in</Link>
        </div>
      ) : (
        <form onSubmit={submit} noValidate className="space-y-4">
          {f.formError && <Alert>{f.formError}</Alert>}
          <Input label="Email" type="email" autoComplete="email" value={email} error={f.errors.email}
            onChange={(e) => { setEmail(e.target.value); f.clear('email') }} />
          <Button type="submit" loading={f.busy} className="w-full">Send reset link</Button>
          <Link to="/login" className="block text-sm font-medium text-primary hover:underline">Back to sign in</Link>
        </form>
      )}
    </AuthLayout>
  )
}

export function ResetPasswordPage() {
  const [params] = useSearchParams()
  const token = params.get('token') ?? ''
  const navigate = useNavigate()
  const f = useForm()
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    const errs: FieldErrors = {}
    const pm = passwordMessage(password)
    if (pm) errs.password = pm
    else if (password !== confirm) errs.confirm_password = 'Passwords do not match.'
    f.setErrors(errs); f.setFormError('')
    if (Object.keys(errs).length) return
    f.setBusy(true)
    try { await api.auth.reset({ token, password, confirm_password: confirm }); navigate('/login', { replace: true, state: { reset: true } }) }
    catch (err) { f.fail(err) } finally { f.setBusy(false) }
  }

  if (!token) return (
    <AuthLayout title="Link not valid">
      <Alert>This reset link is missing its token. Request a new one.</Alert>
      <Link to="/forgot-password" className="mt-4 inline-block text-sm font-medium text-primary hover:underline">Request a new link</Link>
    </AuthLayout>
  )
  return (
    <AuthLayout title="Choose a new password">
      <form onSubmit={submit} noValidate className="space-y-4">
        {f.formError && <Alert>{f.formError}</Alert>}
        <Input label="New password" type="password" autoComplete="new-password" value={password} error={f.errors.password}
          onChange={(e) => { setPassword(e.target.value); f.clear('password') }} />
        <Input label="Confirm new password" type="password" autoComplete="new-password" value={confirm} error={f.errors.confirm_password}
          onChange={(e) => { setConfirm(e.target.value); f.clear('confirm_password') }} />
        <Button type="submit" loading={f.busy} className="w-full">Update password</Button>
      </form>
    </AuthLayout>
  )
}
