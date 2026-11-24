import { Link } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Alert, Badge, EmptyState, PageHeader, Panel, ProgressBar, Skeleton, pctTone } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useChartColors } from '../hooks/useChartColors'
import { http } from '../services/api'
import type { UserSkillRow } from '../types'

interface Analysis {
  skills: UserSkillRow[]; by_category: Record<string, UserSkillRow[]>; evidence_counts: Record<string, number>
  strongest: UserSkillRow[]; weakest: UserSkillRow[]; unassessed: UserSkillRow[]; unassessed_with_test: string[]
  topics: { skill: string; topic: string; percentage: number }[]; total_attempts: number
}
const LEVEL = { assessment_verified: { label: 'Verified by assessment', tone: 'good' }, user_confirmed: { label: 'Confirmed by you', tone: 'info' }, resume_detected: { label: 'Seen on resume', tone: 'neutral' } } as const

export function AnalysisPage() {
  const { data, loading, error } = useAsync(() => http.get<Analysis>('/api/analysis').then((r) => r.data))
  const c = useChartColors()
  const assessed = (data?.skills ?? []).filter((s) => s.proficiency_pct !== null).sort((a, b) => (b.proficiency_pct ?? 0) - (a.proficiency_pct ?? 0))

  return (
    <>
      <PageHeader title="Skill Analysis" subtitle="What you claim, what you’ve confirmed, and what an assessment has verified." />
      {loading && <Skeleton className="h-64" />}
      {error && <Alert>{error}</Alert>}
      {data && data.skills.length === 0 && <Panel><EmptyState title="No skills to analyse yet" action={<Link to="/resume" className="text-sm font-medium text-primary hover:underline">Upload your resume</Link>}>Confirm skills from your resume or take an assessment and your analysis appears here.</EmptyState></Panel>}
      {data && data.skills.length > 0 && (
        <div className="space-y-6">
          <section className="grid gap-px overflow-hidden rounded-lg border border-line bg-line sm:grid-cols-3">
            {(['assessment_verified', 'user_confirmed', 'resume_detected'] as const).map((k) => (
              <div key={k} className="bg-surface p-5"><p className="text-xs text-muted">{LEVEL[k].label}</p><p className="mt-1 text-3xl font-bold tabular-nums">{data.evidence_counts[k]}</p></div>
            ))}
          </section>
          <Alert kind="info">A skill is only <strong>verified</strong> once you’ve passed an assessment for it. Resume mentions and your own confirmation are shown separately and never count as proficiency.</Alert>

          {assessed.length > 0 && (
            <Panel title="Verified proficiency">
              <div style={{ height: Math.max(140, assessed.length * 36 + 30) }} role="img" aria-label={`Proficiency: ${assessed.map((s) => `${s.name} ${s.proficiency_pct}%`).join(', ')}`}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={assessed} layout="vertical" margin={{ left: 8, right: 24 }}>
                    <CartesianGrid stroke={c.line} horizontal={false} />
                    <XAxis type="number" domain={[0, 100]} unit="%" stroke={c.muted} fontSize={12} />
                    <YAxis type="category" dataKey="name" width={120} stroke={c.muted} fontSize={12} />
                    <Tooltip formatter={(v) => [`${v}%`, 'Proficiency']} contentStyle={{ background: c.surface, border: `1px solid ${c.line}`, color: c.ink }} />
                    <Bar dataKey="proficiency_pct" radius={[0, 4, 4, 0]}>{assessed.map((s) => <Cell key={s.id} fill={(s.proficiency_pct ?? 0) >= 70 ? c.success : (s.proficiency_pct ?? 0) >= 40 ? c.attention : c.danger} />)}</Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Panel>
          )}

          <div className="grid gap-6 md:grid-cols-2">
            <Panel title="Strongest">{data.strongest.length ? <ul className="space-y-2 text-sm">{data.strongest.map((s) => <li key={s.id} className="flex justify-between"><span>{s.name}</span><strong>{s.proficiency_pct}%</strong></li>)}</ul> : <p className="text-sm text-muted">Take an assessment to see your strongest skills.</p>}</Panel>
            <Panel title="Needs improvement (below 60%)">{data.weakest.length ? <ul className="space-y-2 text-sm">{data.weakest.map((s) => <li key={s.id} className="flex justify-between"><span>{s.name}</span><strong>{s.proficiency_pct}%</strong></li>)}</ul> : <p className="text-sm text-muted">{assessed.length ? 'No assessed skill is below 60%.' : 'Nothing assessed yet.'}</p>}</Panel>
          </div>

          {data.topics.length > 0 && <Panel title="Weakest topics across all attempts"><ul className="divide-y divide-line">{data.topics.slice(0, 6).map((t) => <li key={t.skill + t.topic} className="flex items-center gap-3 py-2 text-sm"><span className="flex-1">{t.topic} <span className="text-muted">· {t.skill}</span></span><Badge tone={pctTone(t.percentage)}>{t.percentage}%</Badge></li>)}</ul></Panel>}

          <Panel title="Not yet assessed" action={<Link to="/assessments" className="text-sm font-medium text-primary hover:underline">Go to assessments</Link>}>
            {data.unassessed.length === 0 ? <p className="text-sm text-muted">Every confirmed skill has been assessed.</p> : (
              <ul className="flex flex-wrap gap-2">{data.unassessed.map((s) => <li key={s.id}><Badge tone={data.unassessed_with_test.includes(s.name) ? 'warn' : 'neutral'}>{s.name}{data.unassessed_with_test.includes(s.name) ? ' · test available' : ' · no test yet'}</Badge></li>)}</ul>)}
          </Panel>

          <Panel title="All skills by category">
            <div className="space-y-6">
              {Object.entries(data.by_category).map(([cat, list]) => (
                <div key={cat}><h3 className="mb-2 text-sm font-semibold">{cat}</h3>
                  <ul className="divide-y divide-line rounded-md border border-line">{list.map((s) => (
                    <li key={s.id} className="flex flex-wrap items-center gap-3 px-3 py-2.5 text-sm">
                      <span className="w-40 font-medium">{s.name}</span><Badge tone={LEVEL[s.evidence_level].tone}>{LEVEL[s.evidence_level].label}</Badge>
                      <div className="ml-auto w-40">{s.proficiency_pct !== null ? <div className="flex items-center gap-2"><ProgressBar value={s.proficiency_pct} label={`${s.name} proficiency`} /><span className="w-10 text-right tabular-nums">{s.proficiency_pct}%</span></div> : <span className="text-xs text-muted">No level yet</span>}</div>
                    </li>))}</ul></div>
              ))}
            </div>
          </Panel>
        </div>
      )}
    </>
  )
}
