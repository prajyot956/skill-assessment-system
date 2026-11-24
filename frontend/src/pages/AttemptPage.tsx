import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Check, ChevronLeft, ChevronRight, Clock } from 'lucide-react'
import { Alert, Button, ConfirmDialog, Input, Skeleton } from '../components/ui'
import { useToast } from '../context/ToastContext'
import { ApiError, http } from '../services/api'
import type { AnswerValue, AttemptData, AttemptQuestion } from '../types'

const fmt = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
const isAnswered = (v: AnswerValue | undefined) => v !== undefined && v !== '' && !(Array.isArray(v) && v.length === 0)

export function AttemptPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const toast = useToast()
  const [att, setAtt] = useState<AttemptData | null>(null)
  const [error, setError] = useState('')
  const [answers, setAnswers] = useState<Record<string, AnswerValue>>({})
  const [idx, setIdx] = useState(0)
  const [left, setLeft] = useState<number | null>(null)
  const [save, setSave] = useState<'saved' | 'saving' | 'error'>('saved')
  const [confirm, setConfirm] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const dirty = useRef<Set<string>>(new Set())
  const latest = useRef(answers); latest.current = answers
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const offset = useRef(0)
  const done = useRef(false)

  const finish = useCallback(() => { done.current = true; navigate(`/assessments/results/${id}`, { replace: true }) }, [id, navigate])

  useEffect(() => {
    http.get<AttemptData>(`/api/assessments/attempts/${id}`).then((r) => {
      if (r.data.finished) return finish()
      offset.current = Date.parse(r.data.server_now) - Date.now()
      setAtt(r.data); setAnswers(r.data.answers)
    }).catch((e) => setError(e instanceof ApiError ? e.message : 'Couldn’t load this assessment.'))
  }, [id, finish])

  const flush = useCallback(async () => {
    if (!dirty.current.size || done.current) return
    const keys = [...dirty.current]
    const payload: Record<string, AnswerValue | null> = {}
    for (const k of keys) payload[k] = latest.current[k] ?? null
    setSave('saving')
    try {
      await http.put(`/api/assessments/attempts/${id}/answers`, { answers: payload })
      keys.forEach((k) => { if (JSON.stringify(latest.current[k] ?? null) === JSON.stringify(payload[k])) dirty.current.delete(k) })
      setSave(dirty.current.size ? 'saving' : 'saved')
    } catch (e) {
      if (e instanceof ApiError && e.code === 'attempt_expired') { toast.error('Time is up. Your saved answers were submitted.'); return finish() }
      setSave('error')
    }
  }, [id, finish, toast])

  const submit = useCallback(async (auto = false) => {
    if (done.current) return
    setSubmitting(true)
    try {
      await http.post(`/api/assessments/attempts/${id}/submit`, { answers: latest.current })
      if (auto) toast.error('Time is up. Your answers were submitted.')
      finish()
    } catch (e) { setSubmitting(false); setConfirm(false); toast.error(e instanceof ApiError ? e.message : 'Couldn’t submit. Your answers are saved; try again.') }
  }, [id, finish, toast])

  useEffect(() => {
    if (!att) return
    const end = Date.parse(att.expires_at)
    const tick = () => {
      const s = Math.max(0, Math.ceil((end - (Date.now() + offset.current)) / 1000))
      setLeft(s)
      if (s <= 0) void submit(true)
    }
    tick(); const t = setInterval(tick, 1000)
    return () => clearInterval(t)
  }, [att, submit])

  useEffect(() => () => { if (timer.current) clearTimeout(timer.current) }, [])
  useEffect(() => { // retry failed saves periodically
    if (save !== 'error') return
    const t = setInterval(() => void flush(), 5000)
    return () => clearInterval(t)
  }, [save, flush])

  const change = (q: AttemptQuestion, v: AnswerValue) => {
    setAnswers((a) => ({ ...a, [q.id]: v }))
    dirty.current.add(String(q.id)); setSave('saving')
    if (timer.current) clearTimeout(timer.current)
    timer.current = setTimeout(() => void flush(), 700)
  }

  if (error) return <div className="mx-auto max-w-lg py-16"><Alert>{error}</Alert></div>
  if (!att) return <div className="space-y-4" aria-busy="true"><Skeleton className="h-16" /><Skeleton className="h-80" /></div>
  const q = att.questions[idx]
  const unanswered = att.questions.filter((x) => !isAnswered(answers[x.id])).length
  const low = left !== null && left <= 60

  return (
    <div>
      <div className="sticky top-14 z-10 -mx-4 mb-6 flex flex-wrap items-center gap-4 border-b border-line bg-surface/95 px-4 py-3 backdrop-blur sm:-mx-6 sm:px-6">
        <div className="min-w-0 flex-1"><h1 className="truncate text-lg font-bold">{att.title}</h1><p className="text-xs capitalize text-muted">{att.difficulty} · question {idx + 1} of {att.questions.length}</p></div>
        <span className="text-xs text-muted" aria-live="polite">{save === 'saved' ? 'All answers saved' : save === 'saving' ? 'Saving…' : <button onClick={() => void flush()} className="font-medium text-danger underline">Not saved. Retry</button>}</span>
        <div role="timer" aria-label="Time remaining" className={`flex items-center gap-2 rounded-md border px-3 py-1.5 font-mono text-lg font-bold tabular-nums ${low ? 'border-danger text-danger' : 'border-line'}`}><Clock className="h-4 w-4" aria-hidden />{left === null ? '–:––' : fmt(left)}</div>
        <Button onClick={() => setConfirm(true)}>Submit</Button>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_14rem]">
        <section className="rounded-lg border border-line bg-surface p-6" aria-label={`Question ${idx + 1}`}>
          <div className="mb-1 flex items-center gap-3 text-xs text-muted"><span>{q.topic}</span><span>·</span><span>{q.marks} mark{q.marks === 1 ? '' : 's'}</span>
            {q.type === 'multiple' && <span className="font-semibold text-attention">Select all that apply</span>}</div>
          <p className="mb-5 text-lg font-medium leading-snug">{q.text}</p>
          <Answer q={q} value={answers[q.id]} onChange={(v) => change(q, v)} />
          <div className="mt-8 flex justify-between">
            <Button variant="secondary" disabled={idx === 0} onClick={() => setIdx(idx - 1)}><ChevronLeft className="h-4 w-4" />Previous</Button>
            <Button variant="secondary" disabled={idx === att.questions.length - 1} onClick={() => setIdx(idx + 1)}>Next<ChevronRight className="h-4 w-4" /></Button>
          </div>
        </section>
        <nav aria-label="Questions" className="lg:sticky lg:top-40 lg:self-start">
          <p className="mb-2 text-xs font-medium text-muted">{att.questions.length - unanswered} of {att.questions.length} answered</p>
          <div className="grid grid-cols-6 gap-1.5 sm:grid-cols-8 lg:grid-cols-4">
            {att.questions.map((x, i) => (
              <button key={x.id} onClick={() => setIdx(i)} aria-label={`Question ${i + 1}${isAnswered(answers[x.id]) ? ', answered' : ''}`} aria-current={i === idx}
                className={`grid h-9 place-items-center rounded-md border text-sm font-medium ${i === idx ? 'border-primary bg-primary text-primary-ink' : isAnswered(answers[x.id]) ? 'border-primary/50 bg-primary/10' : 'border-line hover:bg-sunken'}`}>{isAnswered(answers[x.id]) ? <Check className="h-4 w-4" /> : i + 1}</button>
            ))}
          </div>
        </nav>
      </div>
      <ConfirmDialog open={confirm} title="Submit your answers?" confirmLabel="Submit now" busy={submitting} onConfirm={() => void submit()} onCancel={() => setConfirm(false)}>
        {unanswered > 0 ? `${unanswered} question${unanswered === 1 ? ' is' : 's are'} unanswered and will score zero.` : 'You answered every question.'} You can’t change answers after submitting.
      </ConfirmDialog>
    </div>
  )
}

function Answer({ q, value, onChange }: { q: AttemptQuestion; value: AnswerValue | undefined; onChange: (v: AnswerValue) => void }) {
  if (q.type === 'coding') return (
    <textarea
      className="w-full rounded-md border border-line bg-sunken p-3 font-mono text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
      rows={4}
      value={(value as string) ?? ''}
      maxLength={300}
      onChange={(e) => onChange(e.target.value)}
      placeholder="Type your code answer here..."
      autoComplete="off"
      spellCheck={false}
    />
  )
  if (q.type === 'short') return <Input label="Your answer" value={(value as string) ?? ''} maxLength={300} onChange={(e) => onChange(e.target.value)} autoComplete="off" />
  const multi = q.type === 'multiple'
  const chosen = multi ? ((value as number[]) ?? []) : []
  return (
    <fieldset><legend className="sr-only">Answer options</legend>
      <div className="space-y-2">
        {q.options!.map((o) => {
          const on = multi ? chosen.includes(o.id) : value === o.id
          return (
            <label key={o.id} className={`flex cursor-pointer items-start gap-3 rounded-md border p-3 text-sm ${on ? 'border-primary bg-primary/10' : 'border-line hover:bg-sunken'}`}>
              <input type={multi ? 'checkbox' : 'radio'} name={`q${q.id}`} checked={on} className="mt-0.5 h-4 w-4 accent-[rgb(var(--c-primary))]"
                onChange={() => onChange(multi ? (on ? chosen.filter((x) => x !== o.id) : [...chosen, o.id]) : o.id)} />
              <span>{o.text}</span>
            </label>
          )
        })}
      </div>
      {!multi && value !== undefined && <button type="button" onClick={() => onChange('')} className="mt-3 text-xs text-muted underline">Clear answer</button>}
    </fieldset>
  )
}
