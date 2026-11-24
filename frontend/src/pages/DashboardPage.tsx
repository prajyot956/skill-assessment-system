import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Alert, EmptyState, PageHeader, Panel, ProgressBar, Skeleton } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { useAsync } from '../hooks/useAsync'
import { api } from '../services/api'
import { isEnabled } from '../nav'
import type { Dashboard } from '../types'

const RESUME_STATUS: Record<string, string> = {
  not_uploaded: 'Not uploaded', uploaded: 'Uploaded', processing: 'Processing',
  parsed: 'Ready to review', failed: 'Needs another try', confirmed: 'Confirmed',
}

/** Link only to pages that exist yet. */
function Cta({ to, children }: { to: string; children: ReactNode }) {
  return isEnabled(to) ? <Link to={to} className="text-sm font-medium text-primary hover:underline">{children}</Link> : null
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="px-5 py-4">
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="mt-1 text-2xl font-bold tabular-nums">{value}</dd>
    </div>
  )
}

function SkillList({ items }: { items: { skill: string; proficiency_pct: number }[] }) {
  return (
    <ul className="space-y-2">
      {items.map((s) => (
        <li key={s.skill} className="flex items-center justify-between text-sm">
          <span>{s.skill}</span><span className="font-semibold tabular-nums">{s.proficiency_pct}%</span>
        </li>
      ))}
    </ul>
  )
}

function DashboardSkeleton() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Loading dashboard">
      <Skeleton className="h-24" /><div className="grid gap-6 lg:grid-cols-2"><Skeleton className="h-56" /><Skeleton className="h-56" /></div>
      <div className="grid gap-6 lg:grid-cols-2"><Skeleton className="h-44" /><Skeleton className="h-44" /></div>
    </div>
  )
}

export function DashboardPage() {
  const { user } = useAuth()
  const { data, error, loading, reload } = useAsync<Dashboard>(api.dashboard.get)

  return (
    <>
      <PageHeader title={`Hello, ${user?.full_name.split(' ')[0] ?? 'there'}`} subtitle="Here’s where you stand today." />
      {loading && !data && <DashboardSkeleton />}
      {error && <div className="space-y-3"><Alert>{error}</Alert><button onClick={reload} className="text-sm font-medium text-primary hover:underline">Try again</button></div>}
      {data && <DashboardBody d={data} />}
    </>
  )
}

function DashboardBody({ d }: { d: Dashboard }) {
  const missing = d.profile.completion.items.filter((i) => !i.done)
  return (
    <div className="space-y-6">
      <section className="rounded-lg border border-line bg-surface">
        <dl className="grid grid-cols-2 divide-x divide-y divide-line sm:grid-cols-4 sm:divide-y-0">
          <Stat label="Confirmed skills" value={d.profile.confirmed_skills} />
          <Stat label="Assessments completed" value={d.assessments.completed} />
          <Stat label="In progress" value={d.assessments.pending} />
          <Stat label="Average score" value={d.assessments.average_score === null ? '—' : `${d.assessments.average_score}%`} />
        </dl>
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="Profile" action={<Cta to="/profile">Edit profile</Cta>}>
          <div className="mb-1 flex items-baseline justify-between"><span className="text-sm text-muted">Completion</span><span className="text-lg font-bold tabular-nums">{d.profile.completion.percent}%</span></div>
          <ProgressBar value={d.profile.completion.percent} label="Profile completion" />
          <p className="mt-4 text-sm"><span className="text-muted">Resume: </span><span className="font-medium">{RESUME_STATUS[d.profile.resume_status] ?? d.profile.resume_status}</span></p>
          {missing.length > 0 && (
            <div className="mt-4"><p className="mb-2 text-sm font-medium">Next steps</p>
              <ul className="space-y-1.5 text-sm text-muted">{missing.slice(0, 4).map((m) => <li key={m.key}>{m.label}</li>)}</ul></div>
          )}
        </Panel>

        <Panel title="Skills">
          {d.skills.strongest.length === 0 && d.skills.unassessed.length === 0 ? (
            <EmptyState title="No skills yet">Skills appear here after you confirm them from your resume or add them yourself. Assessed skills show a score.</EmptyState>
          ) : (
            <div className="space-y-5">
              {d.skills.strongest.length > 0 && <div><p className="mb-2 text-sm font-medium">Strongest</p><SkillList items={d.skills.strongest} /></div>}
              {d.skills.weakest.length > 0 && <div><p className="mb-2 text-sm font-medium">Needs work</p><SkillList items={d.skills.weakest} /></div>}
              {d.skills.unassessed.length > 0 && (
                <div><p className="mb-2 text-sm font-medium">Not assessed yet</p>
                  <p className="text-sm text-muted">{d.skills.unassessed.join(', ')}</p></div>
              )}
            </div>
          )}
        </Panel>

        <Panel title="Recent assessments" action={<Cta to="/history">View all</Cta>}>
          {d.assessments.recent.length === 0
            ? <EmptyState title="No assessments taken">Your results will be listed here once you finish one.</EmptyState>
            : <ul className="divide-y divide-line">{d.assessments.recent.map((r) => (
              <li key={r.attempt_id} className="flex items-center justify-between py-2.5 text-sm">
                <span>{r.skill}</span><span className="tabular-nums"><strong>{r.percentage}%</strong> <span className="text-muted">· {r.category}</span></span>
              </li>))}</ul>}
        </Panel>

        <Panel title="Career and learning">
          {d.career.top_matches.length === 0 && !d.learning
            ? <EmptyState title="No career matches yet">Matches are calculated from your confirmed skills and assessment scores. Your roadmap appears once you pick a target career.</EmptyState>
            : <div className="space-y-4">
              {d.career.top_matches.map((m) => <div key={m.role} className="flex justify-between text-sm"><span>{m.role}</span><strong>{m.match_pct}%</strong></div>)}
              {d.learning && <div><div className="mb-1 flex justify-between text-sm"><span>{d.learning.role ?? 'Roadmap'}</span>
                <span className="text-muted">{d.learning.completed}/{d.learning.total} done</span></div>
                <ProgressBar value={d.learning.progress_pct} label="Roadmap progress" /></div>}
            </div>}
        </Panel>
      </div>

      <Panel title="Recent activity">
        {d.activity.length === 0
          ? <EmptyState title="Nothing yet">Assessments, profile updates, and learning milestones will be recorded here.</EmptyState>
          : <ul className="divide-y divide-line">{d.activity.map((a) => (
            <li key={a.id} className="py-2.5 text-sm"><p className="font-medium">{a.title}</p>{a.message && <p className="text-muted">{a.message}</p>}</li>))}</ul>}
      </Panel>
    </div>
  )
}
