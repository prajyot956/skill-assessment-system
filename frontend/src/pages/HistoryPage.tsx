import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Alert, Badge, EmptyState, PageHeader, Panel, Select, Skeleton, pctTone } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useChartColors } from '../hooks/useChartColors'
import { http } from '../services/api'
import type { HistoryRow } from '../types'

export function HistoryPage() {
  const { data, loading, error } = useAsync(() => http.get<HistoryRow[]>('/api/assessments/attempts?per_page=100').then((r) => r.data))
  const c = useChartColors()
  const [skill, setSkill] = useState('')
  const skills = useMemo(() => [...new Set((data ?? []).map((r) => r.skill))].sort(), [data])
  const active = skill || [...skills].sort((a, b) => (data ?? []).filter((r) => r.skill === b).length - (data ?? []).filter((r) => r.skill === a).length)[0] || ''
  const series = useMemo(() => (data ?? []).filter((r) => r.skill === active).slice().reverse()
    .map((r, i) => ({ n: i + 1, date: new Date(r.submitted_at).toLocaleDateString(), percentage: r.percentage })), [data, active])
  const rows = (data ?? []).filter((r) => !skill || r.skill === skill)

  return (
    <>
      <PageHeader title="Assessment History" subtitle="Every completed attempt and how you’re improving." />
      {loading && <Skeleton className="h-64" />}
      {error && <Alert>{error}</Alert>}
      {data && data.length === 0 && <Panel><EmptyState title="No assessments completed yet" action={<Link to="/assessments" className="text-sm font-medium text-primary hover:underline">Take your first assessment</Link>}>Your attempts and your improvement over time will appear here.</EmptyState></Panel>}
      {data && data.length > 0 && (
        <div className="space-y-6">
          <Panel title="Improvement trend" action={<div className="w-48"><Select label="Skill" value={active} options={skills.map((s) => ({ value: s, label: s }))} onChange={(e) => setSkill(e.target.value)} /></div>}>
            {series.length < 2 ? <p className="text-sm text-muted">Take {active} at least twice to see a trend. So far: {series.length} attempt.</p> : (
              <div style={{ height: 240 }} role="img" aria-label={`${active} scores over time: ${series.map((s) => `${s.percentage}%`).join(', ')}`}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={series} margin={{ left: 0, right: 16, top: 8 }}>
                    <CartesianGrid stroke={c.line} vertical={false} />
                    <XAxis dataKey="n" tickFormatter={(n) => `#${n}`} stroke={c.muted} fontSize={12} />
                    <YAxis domain={[0, 100]} unit="%" stroke={c.muted} fontSize={12} width={44} />
                    <Tooltip labelFormatter={(n) => `Attempt ${n}`} formatter={(v) => [`${v}%`, 'Score']} contentStyle={{ background: c.surface, border: `1px solid ${c.line}`, color: c.ink }} />
                    <Line type="monotone" dataKey="percentage" stroke={c.primary} strokeWidth={2.5} dot={{ r: 4, fill: c.primary }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </Panel>
          <Panel title={`Attempts (${rows.length})`}>
            <div className="-mx-5 -my-5 overflow-x-auto">
              <table className="w-full min-w-[34rem] text-left text-sm">
                <thead className="border-b border-line text-xs text-muted"><tr><th className="px-5 py-3 font-medium">Skill</th><th className="px-3 font-medium">Level</th><th className="px-3 font-medium">Score</th><th className="px-3 font-medium">Correct</th><th className="px-3 font-medium">Date</th><th className="px-5" /></tr></thead>
                <tbody className="divide-y divide-line">
                  {rows.map((r) => (
                    <tr key={r.attempt_id}>
                      <td className="px-5 py-3 font-medium">{r.skill}</td><td className="px-3 capitalize">{r.difficulty}</td>
                      <td className="px-3"><Badge tone={pctTone(r.percentage)}>{r.percentage}%</Badge>{r.status === 'expired' && <span className="ml-2 text-xs text-muted">timed out</span>}</td>
                      <td className="px-3 tabular-nums">{r.correct}/{r.total}</td><td className="px-3 text-muted">{new Date(r.submitted_at).toLocaleDateString()}</td>
                      <td className="px-5 text-right"><Link to={`/assessments/results/${r.attempt_id}`} className="font-medium text-primary hover:underline">Details</Link></td>
                    </tr>))}
                </tbody>
              </table>
            </div>
          </Panel>
        </div>
      )}
    </>
  )
}
