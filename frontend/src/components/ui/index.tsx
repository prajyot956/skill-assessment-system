import { forwardRef, useId, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type TextareaHTMLAttributes } from 'react'
import { Loader2 } from 'lucide-react'

const cx = (...c: (string | false | undefined)[]) => c.filter(Boolean).join(' ')

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  loading?: boolean
}
export function Button({ variant = 'primary', loading, disabled, className, children, ...rest }: ButtonProps) {
  const styles = {
    primary: 'bg-primary text-primary-ink hover:opacity-90',
    secondary: 'border border-line bg-surface text-ink hover:bg-sunken',
    ghost: 'text-ink hover:bg-sunken',
    danger: 'bg-danger text-white hover:opacity-90',
  }[variant]
  return (
    <button {...rest} disabled={disabled || loading}
      className={cx('inline-flex h-10 items-center justify-center gap-2 rounded-md px-4 text-sm font-semibold transition-colors',
        'disabled:cursor-not-allowed disabled:opacity-60', styles, className)}>
      {loading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
      {children}
    </button>
  )
}

interface FieldShellProps { label: string; error?: string; hint?: string; id: string; children: ReactNode }
function FieldShell({ label, error, hint, id, children }: FieldShellProps) {
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium">{label}</label>
      {children}
      {hint && !error && <p id={`${id}-hint`} className="mt-1 text-xs text-muted">{hint}</p>}
      {error && <p id={`${id}-err`} role="alert" className="mt-1 text-xs font-medium text-danger">{error}</p>}
    </div>
  )
}
const inputCls = (error?: string) => cx(
  'w-full rounded-md border bg-surface px-3 text-sm placeholder:text-muted/70 focus:border-primary',
  error ? 'border-danger' : 'border-line')

interface InputProps extends InputHTMLAttributes<HTMLInputElement> { label: string; error?: string; hint?: string }
export const Input = forwardRef<HTMLInputElement, InputProps>(function Input({ label, error, hint, className, id, ...rest }, ref) {
  const auto = useId(); const fid = id ?? auto
  return (
    <FieldShell label={label} error={error} hint={hint} id={fid}>
      <input ref={ref} id={fid} aria-invalid={!!error} aria-describedby={error ? `${fid}-err` : hint ? `${fid}-hint` : undefined}
        className={cx(inputCls(error), 'h-10', className)} {...rest} />
    </FieldShell>
  )
})

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> { label: string; error?: string; hint?: string }
export function Textarea({ label, error, hint, className, id, ...rest }: TextareaProps) {
  const auto = useId(); const fid = id ?? auto
  return (
    <FieldShell label={label} error={error} hint={hint} id={fid}>
      <textarea id={fid} aria-invalid={!!error} aria-describedby={error ? `${fid}-err` : undefined}
        className={cx(inputCls(error), 'min-h-28 py-2', className)} {...rest} />
    </FieldShell>
  )
}

export function Panel({ title, action, children, className }: { title?: string; action?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={cx('rounded-lg border border-line bg-surface', className)}>
      {(title || action) && (
        <header className="flex items-center justify-between gap-3 border-b border-line px-5 py-3">
          {title && <h2 className="text-sm font-semibold">{title}</h2>}
          {action}
        </header>
      )}
      <div className="p-5">{children}</div>
    </section>
  )
}

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cx('animate-pulse rounded-md bg-sunken', className)} />
}

export function EmptyState({ icon, title, children, action }: { icon?: ReactNode; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-start gap-2 py-2">
      {icon && <div className="text-muted">{icon}</div>}
      <p className="text-sm font-medium">{title}</p>
      {children && <p className="max-w-prose text-sm text-muted">{children}</p>}
      {action}
    </div>
  )
}

export function ProgressBar({ value, label }: { value: number; label: string }) {
  const v = Math.max(0, Math.min(100, value))
  return (
    <div role="progressbar" aria-label={label} aria-valuenow={v} aria-valuemin={0} aria-valuemax={100}
      className="h-2 w-full overflow-hidden rounded-full bg-sunken">
      <div className="h-full rounded-full bg-primary transition-[width] duration-500" style={{ width: `${v}%` }} />
    </div>
  )
}

export function PageHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
      </div>
      {action}
    </div>
  )
}

export function Alert({ kind = 'error', children }: { kind?: 'error' | 'info'; children: ReactNode }) {
  return (
    <div role={kind === 'error' ? 'alert' : 'status'}
      className={cx('rounded-md border px-3 py-2 text-sm',
        kind === 'error' ? 'border-danger/40 bg-danger/10 text-danger' : 'border-primary/40 bg-primary/10')}>
      {children}
    </div>
  )
}

export function Badge({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'neutral' | 'good' | 'warn' | 'bad' | 'info' }) {
  const t = { neutral: 'bg-sunken text-muted', good: 'bg-success/15 text-success', warn: 'bg-attention/15 text-attention', bad: 'bg-danger/15 text-danger', info: 'bg-primary/15 text-primary' }[tone]
  return <span className={cx('inline-flex items-center rounded px-2 py-0.5 text-xs font-semibold', t)}>{children}</span>
}

interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> { label: string; error?: string; options: { value: string | number; label: string }[]; placeholder?: string }
export function Select({ label, error, options, placeholder, className, id, ...rest }: SelectProps) {
  const auto = useId(); const fid = id ?? auto
  return (
    <FieldShell label={label} error={error} id={fid}>
      <select id={fid} aria-invalid={!!error} className={cx(inputCls(error), 'h-10', className)} {...rest}>
        {placeholder !== undefined && <option value="">{placeholder}</option>}
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </FieldShell>
  )
}

export function Tabs<T extends string>({ tabs, value, onChange }: { tabs: { id: T; label: string }[]; value: T; onChange: (v: T) => void }) {
  return (
    <div role="tablist" className="mb-6 flex gap-1 overflow-x-auto border-b border-line">
      {tabs.map((t) => (
        <button key={t.id} role="tab" aria-selected={value === t.id} onClick={() => onChange(t.id)}
          className={cx('-mb-px whitespace-nowrap border-b-2 px-4 py-2.5 text-sm font-medium', value === t.id ? 'border-primary text-primary' : 'border-transparent text-muted hover:text-ink')}>
          {t.label}
        </button>
      ))}
    </div>
  )
}

export function ConfirmDialog({ open, title, children, confirmLabel, onConfirm, onCancel, busy, danger }:
  { open: boolean; title: string; children: ReactNode; confirmLabel: string; onConfirm: () => void; onCancel: () => void; busy?: boolean; danger?: boolean }) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4" role="dialog" aria-modal="true" aria-label={title}
      onKeyDown={(e) => { if (e.key === 'Escape') onCancel() }}>
      <div className="w-full max-w-md rounded-lg border border-line bg-surface p-6 shadow-pop">
        <h2 className="text-lg font-bold">{title}</h2>
        <div className="mt-2 text-sm text-muted">{children}</div>
        <div className="mt-6 flex justify-end gap-2">
          <Button variant="secondary" onClick={onCancel} autoFocus>Cancel</Button>
          <Button variant={danger ? 'danger' : 'primary'} onClick={onConfirm} loading={busy}>{confirmLabel}</Button>
        </div>
      </div>
    </div>
  )
}

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return <div><dt className="text-xs text-muted">{label}</dt><dd className="mt-0.5 text-2xl font-bold tabular-nums">{value}</dd>{hint && <p className="text-xs text-muted">{hint}</p>}</div>
}

export const pctTone = (p: number | null) => (p === null ? 'neutral' : p >= 70 ? 'good' : p >= 40 ? 'warn' : 'bad') as 'neutral' | 'good' | 'warn' | 'bad'
