import { useState } from 'react'
import { Link, useParams, useNavigate } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { CheckCircle2, CircleDashed, XCircle } from 'lucide-react'
import { Alert, Badge, Button, PageHeader, Panel, Skeleton, Stat, pctTone } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useChartColors } from '../hooks/useChartColors'
import { useToast } from '../context/ToastContext'
import { ApiError, http } from '../services/api'
import type { Breakdown, ResultData, ReviewItem } from '../types'

function BreakdownChart({ data, title }: { data: Breakdown[]; title: string }) {
  const c = useChartColors()
  const color = (p: number) => (p >= 70 ? c.success : p >= 50 ? c.attention : c.danger)
  return (
    <Panel title={title}>
      <div role="img" aria-label={`${title}: ${data.map((d) => `${d.name} ${d.percentage}%`).join(', ')}`} style={{ height: Math.max(120, data.length * 38 + 30) }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ left: 8, right: 24 }}>
            <CartesianGrid stroke={c.line} horizontal={false} />
            <XAxis type="number" domain={[0, 100]} unit="%" stroke={c.muted} fontSize={12} />
            <YAxis type="category" dataKey="name" width={110} stroke={c.muted} fontSize={12} />
            <Tooltip formatter={(v) => [`${v}%`, 'Score']} contentStyle={{ background: c.surface, border: `1px solid ${c.line}`, color: c.ink }} />
            <Bar dataKey="percentage" radius={[0, 4, 4, 0]}>{data.map((d) => <Cell key={d.name} fill={color(d.percentage)} />)}</Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Panel>
  )
}

const label = (r: ReviewItem, id: number) => r.options?.find((o) => o.id === id)?.text ?? String(id)
function yours(r: ReviewItem) {
  if (r.your_answer === null || r.your_answer === '') return 'No answer'
  if (Array.isArray(r.your_answer)) return r.your_answer.map((i) => label(r, i)).join(', ')
  return typeof r.your_answer === 'number' ? label(r, r.your_answer) : r.your_answer
}

export function ResultPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const toast = useToast()
  const { data: r, loading, error } = useAsync<ResultData>(() => http.get<ResultData>(`/api/assessments/attempts/${id}/result`).then((x) => x.data))
  const [aiDiff, setAiDiff] = useState('intermediate')
  const [aibusy, setAibusy] = useState(false)
  if (loading) return <div className="space-y-4"><Skeleton className="h-28" /><Skeleton className="h-64" /></div>
  if (error || !r) return <Alert>{error || 'Result not found.'}</Alert>
  const tone = pctTone(r.percentage)

  const generateAiTest = async () => {
    setAibusy(true)
    try {
      const res = await http.post<{ attempt_id: number }>('/api/assessments/attempts/ai-generate', {
        assessment_id: r.assessment_id,
        difficulty: aiDiff,
        num_questions: 5
      })
      navigate(`/assessments/attempt/${res.data.attempt_id}`)
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : 'Could not generate test.')
      setAibusy(false)
    }
  }

  return (
    <>
      <PageHeader title={`${r.title} results`} subtitle={`${r.difficulty[0].toUpperCase()}${r.difficulty.slice(1)} level · ${new Date(r.submitted_at).toLocaleString()}${r.status === 'expired' ? ' · time ran out' : ''}`}
        action={<div className="flex gap-2"><Link to="/assessments"><Button variant="secondary">Take another</Button></Link><Link to="/history"><Button variant="secondary">History</Button></Link><div className="flex items-center gap-2"><select value={aiDiff} onChange={(e) => setAiDiff(e.target.value)} className="rounded-md border border-line bg-surface px-2 py-1.5 text-sm"><option value="beginner">Beginner</option><option value="intermediate">Intermediate</option><option value="advanced">Advanced</option></select><Button onClick={generateAiTest} loading={aibusy} variant="primary">New test</Button></div></div>} />
      <div className="space-y-6">
        <section className="rounded-lg border border-line bg-surface p-6">
          <div className="flex flex-wrap items-center gap-x-10 gap-y-4">
            <div><p className="text-5xl font-bold tabular-nums">{r.percentage}%</p><div className="mt-2"><Badge tone={tone}>{r.performance_category}</Badge></div></div>
            <dl className="grid flex-1 grid-cols-2 gap-5 sm:grid-cols-4">
              <Stat label="Marks" value={`${r.obtained_marks} / ${r.total_marks}`} />
              <Stat label="Accuracy" value={`${r.accuracy}%`} hint="of answered questions" />
              <Stat label="Correct" value={r.correct} hint={`${r.incorrect} wrong · ${r.unanswered} blank`} />
              <Stat label="Verified level" value={`${r.proficiency_pct}%`} hint={`score × ${r.difficulty} weighting`} />
            </dl>
          </div>
        </section>

        <div className="grid gap-6 lg:grid-cols-2">
          <BreakdownChart data={r.topics} title="By topic" />
          <BreakdownChart data={r.difficulties} title="By difficulty" />
        </div>

        <div className="grid gap-6 md:grid-cols-2">
          <Panel title="Strengths">{r.strengths.length ? <ul className="space-y-1.5 text-sm">{r.strengths.map((t) => <li key={t} className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-success" aria-hidden />{t}</li>)}</ul> : <p className="text-sm text-muted">No topic reached 75% in this attempt.</p>}</Panel>
          <Panel title="Needs work">{r.weaknesses.length ? <ul className="space-y-1.5 text-sm">{r.weaknesses.map((t) => <li key={t} className="flex items-center gap-2"><XCircle className="h-4 w-4 text-danger" aria-hidden />{t}</li>)}</ul> : <p className="text-sm text-muted">No topic fell below 50%.</p>}</Panel>
        </div>

        <Panel title="Question review">
          <ol className="space-y-5">
            {r.review.map((q, i) => (
              <li key={q.id} className="border-b border-line pb-5 last:border-0 last:pb-0">
                <div className="flex items-start gap-3">
                  {q.status === 'correct' ? <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-success" aria-label="Correct" /> : q.status === 'incorrect' ? <XCircle className="mt-0.5 h-5 w-5 shrink-0 text-danger" aria-label="Incorrect" /> : <CircleDashed className="mt-0.5 h-5 w-5 shrink-0 text-muted" aria-label="Unanswered" />}
                  <div className="min-w-0 flex-1">
                    <p className="font-medium">{i + 1}. {q.text}</p>
                    <p className="mt-1 text-xs text-muted">{q.topic} · {q.difficulty} · {q.awarded}/{q.marks} marks</p>
                    <p className="mt-2 text-sm"><span className="text-muted">Your answer: </span>{yours(q)}</p>
                    {q.status !== 'correct' && <p className="text-sm"><span className="text-muted">Correct answer: </span><strong>{q.options ? q.options.filter((o) => o.is_correct).map((o) => o.text).join(', ') : q.correct_answer}</strong></p>}
                    {q.explanation && <p className="mt-2 rounded bg-sunken p-2 text-sm text-muted">{q.explanation}</p>}
                  </div>
                </div>
              </li>
            ))}
          </ol>
        </Panel>
      </div>
    </>
  )
}
