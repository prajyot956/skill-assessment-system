import { useState } from 'react'
import { ChevronDown } from 'lucide-react'
import { Alert, Badge, Button, EmptyState, PageHeader, Panel, Select, Skeleton, Tabs, Textarea } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useToast } from '../context/ToastContext'
import { ApiError, http } from '../services/api'
import type { Interview, PracticeProject } from '../types'

const STATUS = [{ v: 'not_started', l: 'Not started' }, { v: 'in_progress', l: 'In progress' }, { v: 'completed', l: 'Completed' }]

function Projects() {
  const { data, loading, error, setData } = useAsync(() => http.get<PracticeProject[]>('/api/practice/projects').then((r) => r.data))
  const toast = useToast()
  const [open, setOpen] = useState<number | null>(null)
  const setStatus = async (p: PracticeProject, status: string) => {
    try { await http.put(`/api/practice/projects/${p.id}/status`, { status }); setData(data!.map((x) => (x.id === p.id ? { ...x, status } : x))) }
    catch (e) { toast.error(e instanceof ApiError ? e.message : 'Couldn’t update status.') }
  }
  if (loading) return <Skeleton className="h-64" />
  if (error) return <Alert>{error}</Alert>
  const done = data!.filter((p) => p.status === 'completed').length
  return (
    <div className="space-y-4">
      <p className="text-sm text-muted">Ordered by how well each project fits your target career and current skills. {done} of {data!.length} completed.</p>
      {data!.map((p) => (
        <article key={p.id} className="rounded-lg border border-line bg-surface">
          <div className="flex flex-wrap items-start gap-4 p-5">
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2"><h2 className="font-bold">{p.title}</h2><Badge tone={p.difficulty === 'beginner' ? 'good' : p.difficulty === 'intermediate' ? 'warn' : 'bad'}>{p.difficulty}</Badge></div>
              <p className="mt-1 text-sm text-muted">{p.description}</p>
              <p className="mt-2 text-xs"><span className="text-muted">Skills: </span>{p.skills.join(', ')}</p>
              {p.reasons.map((r) => <p key={r} className="mt-1 text-xs text-primary">{r}</p>)}
            </div>
            <div className="flex items-end gap-2">
              <div className="w-36"><Select label="Status" value={p.status} options={STATUS.map((s) => ({ value: s.v, label: s.l }))} onChange={(e) => void setStatus(p, e.target.value)} /></div>
              <Button variant="secondary" aria-expanded={open === p.id} onClick={() => setOpen(open === p.id ? null : p.id)}>Plan<ChevronDown className={`h-4 w-4 ${open === p.id ? 'rotate-180' : ''}`} /></Button>
            </div>
          </div>
          {open === p.id && (
            <div className="grid gap-6 border-t border-line p-5 md:grid-cols-3">
              <div><h3 className="mb-2 text-sm font-semibold">Learning objectives</h3><ul className="list-disc space-y-1 pl-5 text-sm">{p.objectives.map((o) => <li key={o}>{o}</li>)}</ul></div>
              <div><h3 className="mb-2 text-sm font-semibold">Steps</h3><ol className="list-decimal space-y-1 pl-5 text-sm">{p.steps.map((s) => <li key={s}>{s}</li>)}</ol></div>
              <div><h3 className="mb-2 text-sm font-semibold">Expected outcome</h3><p className="text-sm">{p.expected_outcome}</p></div>
            </div>)}
        </article>
      ))}
    </div>
  )
}

function Interviews() {
  const roles = useAsync(() => http.get<{ id: number; name: string }[]>('/api/careers/roles').then((r) => r.data))
  const hist = useAsync(() => http.get<{ interviews: Interview[]; ai_enabled: boolean }>('/api/interviews').then((r) => r.data))
  const toast = useToast()
  const [role, setRole] = useState('')
  const [level, setLevel] = useState('beginner')
  const [n, setN] = useState('5')
  const [active, setActive] = useState<Interview | null>(null)
  const [busy, setBusy] = useState(false)
  const [draft, setDraft] = useState<Record<number, string>>({})
  const [cur, setCur] = useState(0)

  const open = async (id: number) => { const r = await http.get<Interview>(`/api/interviews/${id}`); setActive(r.data); setCur(0); setDraft(Object.fromEntries((r.data.questions ?? []).map((q) => [q.index, q.answer]))) }
  const start = async () => {
    setBusy(true)
    try { const r = await http.post<Interview>('/api/interviews', { role_id: role ? Number(role) : null, difficulty: level, num_questions: Number(n) }); setActive(r.data); setCur(0); setDraft({}); void hist.reload() }
    catch (e) { toast.error(e instanceof ApiError ? e.message : 'Couldn’t start the interview.') } finally { setBusy(false) }
  }
  const saveAnswer = async (i: number) => {
    if (active?.status !== 'in_progress' || draft[i] === undefined) return
    try { await http.put(`/api/interviews/${active.id}/answers/${i}`, { answer: draft[i] }) } catch { toast.error('Couldn’t save that answer. Try again.') }
  }
  const complete = async () => {
    setBusy(true)
    try { await saveAnswer(cur); const r = await http.post<Interview>(`/api/interviews/${active!.id}/complete`); setActive(r.data); void hist.reload() }
    catch (e) { toast.error(e instanceof ApiError ? e.message : 'Couldn’t finish.') } finally { setBusy(false) }
  }

  if (active) {
    const qs = active.questions ?? []
    const q = qs[cur]
    const finished = active.status === 'completed'
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between"><p className="text-sm text-muted">{active.role} · {active.difficulty} · {finished ? 'completed' : `question ${cur + 1} of ${qs.length}`}</p><Button variant="secondary" onClick={() => { setActive(null); void hist.reload() }}>Back to interviews</Button></div>
        {!finished && q && (
          <Panel title={`Question ${cur + 1}`}>
            <p className="mb-1 text-xs text-muted">{q.skill}</p><p className="mb-4 text-lg font-medium">{q.text}</p>
            <Textarea label="Your answer" value={draft[cur] ?? ''} maxLength={4000} onChange={(e) => setDraft({ ...draft, [cur]: e.target.value })} onBlur={() => void saveAnswer(cur)} className="min-h-40" hint="Answer as you would out loud. Skipping is fine." />
            <div className="mt-4 flex justify-between"><Button variant="secondary" disabled={cur === 0} onClick={() => { void saveAnswer(cur); setCur(cur - 1) }}>Previous</Button>
              {cur < qs.length - 1 ? <Button onClick={() => { void saveAnswer(cur); setCur(cur + 1) }}>Next</Button> : <Button onClick={complete} loading={busy}>Finish and get feedback</Button>}</div>
            {cur < qs.length - 1 && <div className="mt-3 text-right"><button className="text-xs text-muted underline" onClick={complete}>Finish now</button></div>}
          </Panel>)}
        {finished && (
          <>
            {active.feedback?.overall && <Panel title="Feedback"><p className="text-sm">{active.feedback.overall}</p>
              {!!active.feedback.knowledge_gaps?.length && <><h3 className="mb-1 mt-4 text-sm font-semibold">Possible knowledge gaps</h3><ul className="list-disc space-y-1 pl-5 text-sm">{active.feedback.knowledge_gaps.map((g) => <li key={g}>{g}</li>)}</ul></>}
              <p className="mt-3 text-xs text-muted">AI-written feedback. It gives no score, because a number would imply precision it doesn’t have.</p></Panel>}
            {active.feedback?.note && <Alert kind="info">{active.feedback.note}</Alert>}
            {qs.filter((x) => x.answer).map((x) => { const fb = active.feedback?.per_question?.find((p) => p.index === x.index); return (
              <Panel key={x.index} title={`Q${x.index + 1}. ${x.text}`}>
                <p className="mb-3 whitespace-pre-wrap rounded-md bg-sunken p-3 text-sm">{x.answer}</p>
                {fb && <div className="mb-3 grid gap-4 text-sm md:grid-cols-2"><div><strong className="text-success">Strengths</strong><ul className="list-disc pl-5">{fb.strengths.map((s) => <li key={s}>{s}</li>)}</ul></div><div><strong className="text-attention">To improve</strong><ul className="list-disc pl-5">{fb.improvements.map((s) => <li key={s}>{s}</li>)}</ul></div></div>}
                {x.keyword_check && <p className="text-xs text-muted"><strong>Key-point check</strong> (a rough guide, not a grade): you mentioned {x.keyword_check.mentioned.length ? x.keyword_check.mentioned.join(', ') : 'none of the expected terms'}.{x.keyword_check.not_mentioned.length > 0 && <> Consider covering: {x.keyword_check.not_mentioned.join(', ')}.</>}</p>}
              </Panel>) })}
          </>)}
      </div>
    )
  }
  return (
    <div className="grid gap-6 lg:grid-cols-[22rem_minmax(0,1fr)]">
      <Panel title="Start a mock interview">
        <div className="space-y-4">
          <Select label="Role" value={role} placeholder="General (based on my skills)" options={(roles.data ?? []).map((r) => ({ value: r.id, label: r.name }))} onChange={(e) => setRole(e.target.value)} />
          <Select label="Difficulty" value={level} options={['beginner', 'intermediate', 'advanced'].map((v) => ({ value: v, label: v[0].toUpperCase() + v.slice(1) }))} onChange={(e) => setLevel(e.target.value)} />
          <Select label="Questions" value={n} options={['3', '5', '8', '10'].map((v) => ({ value: v, label: `${v} questions` }))} onChange={(e) => setN(e.target.value)} />
          <p className="text-xs text-muted">{hist.data?.ai_enabled ? 'AI feedback is on. Your answers are sent to the AI provider only when you finish.' : 'AI is off. You’ll get a key-point check instead of written feedback. No scores are given either way.'}</p>
          <Button className="w-full" onClick={start} loading={busy}>Start interview</Button>
        </div>
      </Panel>
      <Panel title="Past interviews">
        {hist.loading ? <Skeleton className="h-24" /> : !hist.data?.interviews.length ? <EmptyState title="No interviews yet">Your practice sessions are saved here.</EmptyState> : (
          <ul className="-my-2 divide-y divide-line">{hist.data.interviews.map((i) => (
            <li key={i.id} className="flex flex-wrap items-center gap-3 py-3 text-sm"><div className="flex-1"><p className="font-medium">{i.role}</p><p className="text-xs capitalize text-muted">{i.difficulty} · {i.answered}/{i.question_count} answered · {new Date(i.created_at).toLocaleDateString()}</p></div>
              <Badge tone={i.status === 'completed' ? 'good' : 'info'}>{i.status === 'completed' ? 'Completed' : 'In progress'}</Badge><Button variant="secondary" onClick={() => void open(i.id)}>{i.status === 'completed' ? 'View' : 'Continue'}</Button></li>))}</ul>)}
      </Panel>
    </div>
  )
}

export function PracticePage() {
  const [tab, setTab] = useState<'projects' | 'interview'>('projects')
  return (
    <>
      <PageHeader title="Projects & Practice" subtitle="Build real things and rehearse real interviews." />
      <Tabs tabs={[{ id: 'projects', label: 'Practice projects' }, { id: 'interview', label: 'Mock interview' }]} value={tab} onChange={setTab} />
      {tab === 'projects' ? <Projects /> : <Interviews />}
    </>
  )
}
