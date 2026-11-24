import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Alert, Badge, Button, EmptyState, PageHeader, Panel, ProgressBar, Select, Skeleton } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useToast } from '../context/ToastContext'
import { ApiError, http } from '../services/api'
import type { GapSkill, Recommendation } from '../types'

interface Recs { recommendations: Recommendation[]; target: Recommendation | null; message: string | null; ai_enabled: boolean }
interface Role { id: number; name: string; skill_count: number }
const STATE: Record<GapSkill['state'], { label: string; tone: 'good' | 'warn' | 'bad' | 'neutral' | 'info' }> = {
  met: { label: 'Meets requirement', tone: 'good' }, below: { label: 'Below requirement', tone: 'warn' }, unverified: { label: 'Not verified', tone: 'info' },
  detected: { label: 'Resume only', tone: 'neutral' }, missing: { label: 'Missing', tone: 'bad' },
}

function GapTable({ roleId }: { roleId: number }) {
  const { data, loading, error } = useAsync(() => http.get<{ skills: GapSkill[] }>(`/api/careers/${roleId}/gap`).then((r) => r.data))
  if (loading) return <Skeleton className="h-32" />
  if (error) return <Alert>{error}</Alert>
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[40rem] text-left text-sm">
        <thead className="border-b border-line text-xs text-muted"><tr><th className="py-2 font-medium">Skill</th><th className="font-medium">Required</th><th className="font-medium">Your level</th><th className="font-medium">Status</th><th className="font-medium">Priority</th><th /></tr></thead>
        <tbody className="divide-y divide-line">
          {data!.skills.map((s) => (
            <tr key={s.skill_id}>
              <td className="py-2.5 font-medium">{s.skill}{s.is_core && <span className="ml-1 text-xs text-muted">core</span>}</td><td className="tabular-nums">{s.required_level}%</td>
              <td className="tabular-nums">{s.proficiency_pct !== null ? `${s.proficiency_pct}%` : <span className="text-muted">not assessed</span>}</td>
              <td><Badge tone={STATE[s.state].tone}>{STATE[s.state].label}</Badge></td>
              <td>{s.priority === 'none' ? <span className="text-muted">–</span> : <Badge tone={s.priority === 'high' ? 'bad' : s.priority === 'medium' ? 'warn' : 'neutral'}>{s.priority}</Badge>}</td>
              <td className="text-right">{s.state !== 'met' && s.assessment_available && <Link to="/assessments" className="text-xs font-medium text-primary hover:underline">Assess</Link>}{s.state !== 'met' && !s.assessment_available && <span className="text-xs text-muted">no test yet</span>}</td>
            </tr>))}
        </tbody>
      </table>
    </div>
  )
}

function Card({ r, onTarget, busy, aiOn }: { r: Recommendation; onTarget: (id: number) => void; busy: boolean; aiOn: boolean }) {
  const [open, setOpen] = useState(r.is_target)
  const [ai, setAi] = useState('')
  const toast = useToast()
  const explain = async () => {
    try { setAi((await http.post<{ explanation: string }>(`/api/careers/${r.role_id}/explain`)).data.explanation) }
    catch (e) { toast.error(e instanceof ApiError ? e.message : 'Couldn’t get an AI explanation.') }
  }
  return (
    <article className={`rounded-lg border bg-surface ${r.is_target ? 'border-primary' : 'border-line'}`}>
      <div className="flex flex-wrap items-center gap-4 p-5">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2"><h2 className="text-lg font-bold">{r.role}</h2>{r.is_target && <Badge tone="info">Your target</Badge>}</div>
          <p className="mt-0.5 text-sm text-muted">{r.description}</p>
        </div>
        <div className="w-40"><p className="text-right text-2xl font-bold tabular-nums">{r.match_pct}%</p><ProgressBar value={r.match_pct} label={`${r.role} match`} /></div>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => setOpen(!open)} aria-expanded={open}>{open ? 'Hide details' : 'Why this match?'}</Button>
          {!r.is_target && <Button onClick={() => onTarget(r.role_id)} loading={busy}>Set as target</Button>}
        </div>
      </div>
      {open && (
        <div className="space-y-6 border-t border-line p-5">
          <div><h3 className="mb-2 text-sm font-semibold">Why</h3><ul className="space-y-1.5 text-sm">{r.why.map((w) => <li key={w}>{w}</li>)}</ul>
            <p className="mt-3 text-xs text-muted">Score = {r.base_pct}% from your skills{r.adjustments.length ? ` + ${r.adjustments.map((a) => `${a.points} ${a.name.toLowerCase()}`).join(' + ')}` : ''}. Only assessments earn full credit for a skill.</p></div>
          <div className="grid gap-6 md:grid-cols-3">
            <div><h3 className="mb-2 text-sm font-semibold text-success">Matching</h3>{r.matching_skills.length ? <ul className="space-y-1 text-sm">{r.matching_skills.map((s) => <li key={s.skill_id}>{s.skill} <span className="text-muted">{s.proficiency_pct}%</span></li>)}</ul> : <p className="text-sm text-muted">None verified yet.</p>}</div>
            <div><h3 className="mb-2 text-sm font-semibold text-attention">Improve</h3>{[...r.partial_skills, ...r.unverified_skills].length ? <ul className="space-y-1 text-sm">{[...r.partial_skills, ...r.unverified_skills].map((s) => <li key={s.skill_id}>{s.skill} <span className="text-muted">{s.proficiency_pct !== null ? `${s.proficiency_pct}% of ${s.required_level}%` : 'not verified'}</span></li>)}</ul> : <p className="text-sm text-muted">Nothing to improve.</p>}</div>
            <div><h3 className="mb-2 text-sm font-semibold text-danger">Missing</h3>{r.missing_skills.length ? <ul className="space-y-1 text-sm">{r.missing_skills.map((s) => <li key={s.skill_id}>{s.skill}</li>)}</ul> : <p className="text-sm text-muted">Nothing missing.</p>}</div>
          </div>
          {r.next_steps.length > 0 && <div><h3 className="mb-2 text-sm font-semibold">Suggested next steps</h3><ol className="list-decimal space-y-1 pl-5 text-sm">{r.next_steps.map((s) => <li key={s}>{s}</li>)}</ol></div>}
          <div><h3 className="mb-2 text-sm font-semibold">Skill gap</h3><GapTable roleId={r.role_id} /></div>
          {aiOn && <div>{ai ? <p className="rounded-md bg-sunken p-3 text-sm"><Badge tone="info">AI</Badge> {ai}</p> : <Button variant="secondary" onClick={explain}>Explain in plain language (AI)</Button>}</div>}
        </div>
      )}
    </article>
  )
}

export function CareersPage() {
  const recs = useAsync(() => http.get<Recs>('/api/careers/recommendations').then((r) => r.data))
  const roles = useAsync(() => http.get<Role[]>('/api/careers/roles').then((r) => r.data))
  const toast = useToast()
  const navigate = useNavigate()
  const [busy, setBusy] = useState(false)
  const setTarget = async (id: number | null) => {
    setBusy(true)
    try { await http.put('/api/careers/target', { role_id: id }); toast.success(id ? 'Target career updated.' : 'Target cleared.'); await recs.reload() }
    catch (e) { toast.error(e instanceof ApiError ? e.message : 'Couldn’t update your target.') } finally { setBusy(false) }
  }
  const d = recs.data
  return (
    <>
      <PageHeader title="Career Recommendations" subtitle="Ranked by how well your verified and confirmed skills fit each role’s requirements." />
      {recs.loading && !d && <Skeleton className="h-64" />}
      {recs.error && <Alert>{recs.error}</Alert>}
      {d && (
        <div className="space-y-6">
          <Panel title="Your target career">
            <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
              <Select label="Choose a role to focus on" value={d.target?.role_id ?? ''} placeholder="No target selected" disabled={busy}
                options={(roles.data ?? []).map((r) => ({ value: r.id, label: r.name }))} onChange={(e) => void setTarget(e.target.value ? Number(e.target.value) : null)} />
              <Button variant="secondary" disabled={!d.target} onClick={() => navigate('/roadmap')}>View learning roadmap</Button>
            </div>
          </Panel>
          {d.message && <Panel><EmptyState title="No matches yet" action={<div className="flex gap-4"><Link to="/resume" className="text-sm font-medium text-primary hover:underline">Upload a resume</Link><Link to="/assessments" className="text-sm font-medium text-primary hover:underline">Take an assessment</Link></div>}>{d.message}</EmptyState></Panel>}
          <div className="space-y-4">{d.recommendations.map((r) => <Card key={r.role_id} r={r} onTarget={(id) => void setTarget(id)} busy={busy} aiOn={d.ai_enabled} />)}</div>
        </div>
      )}
    </>
  )
}
