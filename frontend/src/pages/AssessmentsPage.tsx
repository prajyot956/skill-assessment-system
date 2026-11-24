import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Alert, Badge, Button, EmptyState, PageHeader, Panel, Select, Skeleton, pctTone } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useToast } from '../context/ToastContext'
import { ApiError, http } from '../services/api'
import type { CatalogCategory, CatalogItem } from '../types'

const LEVELS = [{ value: 'beginner', label: 'Beginner' }, { value: 'intermediate', label: 'Intermediate' }, { value: 'advanced', label: 'Advanced' }]
const COUNTS = [5, 10, 15, 20]

export function AssessmentsPage() {
  const { data, loading, error } = useAsync(() => http.get<CatalogCategory[]>('/api/assessments/catalog').then((r) => r.data))
  const [sel, setSel] = useState<CatalogItem | null>(null)
  const [generating, setGenerating] = useState<number | null>(null)
  const navigate = useNavigate()
  const toast = useToast()
  const available = useMemo(() => (data ?? []).reduce((n, c) => n + c.assessments.filter((a) => a.available).length, 0), [data])

  const generateForSkill = async (a: CatalogItem) => {
    setGenerating(a.id)
    try {
      const res = await http.post<{ attempt_id: number }>('/api/assessments/attempts/ai-generate', {
        assessment_id: a.id,
        difficulty: 'intermediate',
        num_questions: 5
      })
      navigate(`/assessments/attempt/${res.data.attempt_id}`)
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : 'Could not generate AI test.')
      setGenerating(null)
    }
  }

  return (
    <>
      <PageHeader title="Skill Assessments" subtitle="Timed tests that measure what you can actually do. Your score sets your verified skill level." />
      {loading && !data && <div className="space-y-4"><Skeleton className="h-40" /><Skeleton className="h-40" /></div>}
      {error && <Alert>{error}</Alert>}
      {data && (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_21rem]">
          <div className="space-y-6">
            {available === 0 && <EmptyState title="No assessments are available yet">An administrator needs to add questions first.</EmptyState>}
            {data.map((cat) => (
              <Panel key={cat.id} title={cat.name}>
                <ul className="-my-2 divide-y divide-line">
                  {cat.assessments.map((a) => (
                    <li key={a.id} className="flex flex-wrap items-center gap-x-4 gap-y-2 py-3">
                      <div className="min-w-0 flex-1">
                        <p className="font-medium">{a.title}</p>
                        <p className="text-xs text-muted">{a.available ? `${a.questions.total} questions (${a.questions.beginner} beginner · ${a.questions.intermediate} intermediate · ${a.questions.advanced} advanced)` : 'Quick questions based on resume'}</p>
                      </div>
                      {a.proficiency_pct !== null && <Badge tone={pctTone(a.proficiency_pct)}>Level {a.proficiency_pct}%</Badge>}
                      {a.in_progress_attempt_id && <Badge tone="info">In progress</Badge>}
                      <Button
                        variant={sel?.id === a.id ? 'primary' : 'secondary'}
                        loading={generating === a.id}
                        onClick={() => {
                          if (a.in_progress_attempt_id) {
                            navigate(`/assessments/attempt/${a.in_progress_attempt_id}`)
                          } else if (a.available) {
                            setSel(a)
                          } else {
                            generateForSkill(a)
                          }
                        }}
                        aria-label={`${a.in_progress_attempt_id ? 'Resume' : 'Set up'} ${a.title}`}
                      >
                        {a.in_progress_attempt_id ? 'Resume' : 'Set up'}
                      </Button>
                    </li>
                  ))}
                </ul>
              </Panel>
            ))}
          </div>
          <aside><div className="lg:sticky lg:top-20">{sel ? <Setup key={sel.id} item={sel} /> : <Panel title="Set up an assessment"><EmptyState title="Pick an assessment">Choose difficulty, length and time, then start. You can leave and come back before time runs out.</EmptyState></Panel>}</div></aside>
        </div>
      )}
    </>
  )
}

function Setup({ item }: { item: CatalogItem }) {
  const navigate = useNavigate()
  const toast = useToast()
  const [difficulty, setDifficulty] = useState('beginner')
  const max = item.questions.total
  const [n, setN] = useState(Math.min(10, max))
  const [minutes, setMinutes] = useState(Math.ceil(Math.min(10, max) * 1.5))
  const [busy, setBusy] = useState(false)
  const counts = COUNTS.filter((c) => c < max).concat(max).filter((v, i, a) => a.indexOf(v) === i)
  const exact = item.questions[difficulty as 'beginner'] ?? 0

  const start = async () => {
    setBusy(true)
    try {
      const r = await http.post<{ attempt_id: number; resumed: boolean }>('/api/assessments/attempts', { assessment_id: item.id, difficulty, num_questions: n, duration_minutes: minutes })
      if (r.data.resumed) toast.success('Resuming your unfinished attempt.')
      navigate(`/assessments/attempt/${r.data.attempt_id}`)
    } catch (e) { toast.error(e instanceof ApiError ? e.message : 'Couldn’t start. Please try again.'); setBusy(false) }
  }
  if (item.in_progress_attempt_id) return (
    <Panel title={item.title}>
      <p className="mb-4 text-sm text-muted">You have an unfinished attempt. Pick up where you left off; your answers were saved.</p>
      <Button className="w-full" onClick={() => navigate(`/assessments/attempt/${item.in_progress_attempt_id}`)}>Resume attempt</Button>
    </Panel>
  )
  return (
    <Panel title={item.title}>
      <div className="space-y-4">
        <Select label="Difficulty" value={difficulty} options={LEVELS} onChange={(e) => setDifficulty(e.target.value)} />
        <Select label="Questions" value={n} options={counts.map((c) => ({ value: c, label: `${c} questions` }))} onChange={(e) => { const v = Number(e.target.value); setN(v); setMinutes(Math.ceil(v * 1.5)) }} />
        <Select label="Time limit" value={minutes} options={[...new Set([5, 10, 15, 20, 30, 45, 60, minutes])].sort((a, b) => a - b).map((m) => ({ value: m, label: `${m} minutes` }))} onChange={(e) => setMinutes(Number(e.target.value))} />
        {exact < n && <p className="rounded-md bg-sunken p-3 text-xs text-muted">Only {exact} {difficulty} question{exact === 1 ? '' : 's'} exist for this skill, so nearby difficulty levels fill the rest.</p>}
        <p className="text-xs text-muted">Timing is enforced by the server. Answers save automatically. Your score becomes your verified level for this skill.</p>
        <Button className="w-full" onClick={start} loading={busy}>Start assessment</Button>
      </div>
    </Panel>
  )
}
