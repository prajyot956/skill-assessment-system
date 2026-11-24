import { useState } from 'react'
import { Link } from 'react-router-dom'
import { BookOpen, Dumbbell, FolderKanban, ClipboardCheck, ExternalLink } from 'lucide-react'
import { Alert, Badge, Button, EmptyState, PageHeader, Panel, ProgressBar, Select, Skeleton, Stat } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useToast } from '../context/ToastContext'
import { ApiError, http } from '../services/api'
import type { Roadmap, RoadmapItem } from '../types'

interface RoadmapResp { roadmap: Roadmap | null; target_role_id: number | null; ai_enabled: boolean }
const ICON = { learn: BookOpen, exercise: Dumbbell, mini_project: FolderKanban, assess: ClipboardCheck }
const TYPE = { learn: 'Learn', exercise: 'Practice', mini_project: 'Mini-project', assess: 'Assess' }
const NEXT: Record<RoadmapItem['status'], { label: string; to: RoadmapItem['status'] }> = { pending: { label: 'Start', to: 'in_progress' }, in_progress: { label: 'Mark complete', to: 'completed' }, completed: { label: 'Undo', to: 'pending' } }

export function RoadmapPage() {
  const { data, loading, error, setData, reload } = useAsync(() => http.get<RoadmapResp>('/api/roadmap').then((r) => r.data))
  const roles = useAsync(() => http.get<{ id: number; name: string }[]>('/api/careers/roles').then((r) => r.data))
  const toast = useToast()
  const [busy, setBusy] = useState(false)
  const [pick, setPick] = useState('')
  const [filter, setFilter] = useState<'all' | 'pending' | 'completed'>('all')
  const [ai, setAi] = useState<Record<string, { title: string; why: string }[]>>({})

  const generate = async (roleId?: number) => {
    setBusy(true)
    try { await http.post('/api/roadmap/generate', roleId ? { role_id: roleId } : {}); toast.success('Roadmap updated. Your progress on matching items was kept.'); await reload() }
    catch (e) { toast.error(e instanceof ApiError ? e.message : 'Couldn’t build the roadmap.') } finally { setBusy(false) }
  }
  const mark = async (it: RoadmapItem, status: RoadmapItem['status']) => {
    try { const r = await http.patch<Roadmap>(`/api/roadmap/items/${it.id}`, { status }); setData({ ...data!, roadmap: r.data }) }
    catch (e) { toast.error(e instanceof ApiError ? e.message : 'Couldn’t update that item.') }
  }
  const suggest = async (skill: string) => {
    try { setAi({ ...ai, [skill]: (await http.post<{ suggestions: { title: string; why: string }[] }>('/api/roadmap/suggest-resources', { skill })).data.suggestions }) }
    catch (e) { toast.error(e instanceof ApiError ? e.message : 'No suggestions available.') }
  }
  const rm = data?.roadmap
  const groups = rm ? rm.items.filter((i) => filter === 'all' || (filter === 'completed' ? i.status === 'completed' : i.status !== 'completed')).reduce<Record<string, RoadmapItem[]>>((a, i) => { (a[i.skill ?? 'General'] ??= []).push(i); return a }, {}) : {}

  return (
    <>
      <PageHeader title="Learning Roadmap" subtitle={rm ? `Your plan for becoming a ${rm.role}.` : 'A personal plan built from your skill gaps.'}
        action={rm && <Button variant="secondary" onClick={() => void generate()} loading={busy}>Rebuild from latest results</Button>} />
      {loading && !data && <Skeleton className="h-64" />}
      {error && <Alert>{error}</Alert>}
      {data && !rm && (
        <Panel title="Create your roadmap">
          <EmptyState title="Choose a target career">Your roadmap lists what to learn, practise and build to close the gaps between your verified skills and the role. You tick items off yourself; nothing is marked done automatically.</EmptyState>
          <div className="mt-4 grid max-w-md gap-3 sm:grid-cols-[1fr_auto] sm:items-end">
            <Select label="Target career" value={pick || data.target_role_id || ''} placeholder="Choose a role…" options={(roles.data ?? []).map((r) => ({ value: r.id, label: r.name }))} onChange={(e) => setPick(e.target.value)} />
            <Button loading={busy} disabled={!(pick || data.target_role_id)} onClick={() => void generate(Number(pick || data.target_role_id))}>Build roadmap</Button>
          </div>
        </Panel>
      )}
      {rm && (
        <div className="space-y-6">
          {rm.is_stale && <Alert kind="info"><div className="flex flex-wrap items-center gap-3"><span>Your skills or target changed since this roadmap was made.</span><Button variant="secondary" onClick={() => void generate()} loading={busy}>Update roadmap</Button></div></Alert>}
          <section className="rounded-lg border border-line bg-surface p-5">
            <div className="grid gap-5 sm:grid-cols-[1fr_auto] sm:items-center">
              <div><div className="mb-1 flex items-baseline justify-between"><span className="text-sm text-muted">Overall progress</span><span className="text-xl font-bold tabular-nums">{rm.progress_pct}%</span></div><ProgressBar value={rm.progress_pct} label="Roadmap progress" /></div>
              <dl className="grid grid-cols-3 gap-6"><Stat label="Done" value={rm.completed} /><Stat label="In progress" value={rm.in_progress} /><Stat label="Pending" value={rm.pending} /></dl>
            </div>
          </section>
          {rm.items.length === 0 && <Panel><EmptyState title="You already meet every requirement for this role">Nothing to learn right now. Try a stretch role on the Careers page, or reassess to confirm your levels.</EmptyState></Panel>}
          {rm.items.length > 0 && <div className="flex gap-2" role="group" aria-label="Filter items">{(['all', 'pending', 'completed'] as const).map((f) => <Button key={f} variant={filter === f ? 'primary' : 'secondary'} onClick={() => setFilter(f)} className="capitalize">{f === 'pending' ? 'To do' : f}</Button>)}</div>}
          {Object.entries(groups).map(([skill, items]) => (
            <Panel key={skill} title={skill} action={<div className="flex items-center gap-3"><Badge tone={items[0].priority === 'high' ? 'bad' : items[0].priority === 'medium' ? 'warn' : 'neutral'}>{items[0].priority} priority</Badge>
              {data.ai_enabled && skill !== 'General' && <button className="text-xs font-medium text-primary hover:underline" onClick={() => void suggest(skill)}>More ideas (AI)</button>}</div>}>
              <ul className="-my-2 divide-y divide-line">
                {items.map((it) => { const Icon = ICON[it.type]; const n = NEXT[it.status]; return (
                  <li key={it.id} className="flex flex-wrap items-start gap-3 py-3">
                    <Icon className={`mt-0.5 h-5 w-5 shrink-0 ${it.status === 'completed' ? 'text-success' : 'text-muted'}`} aria-hidden />
                    <div className="min-w-0 flex-1">
                      <p className={`font-medium ${it.status === 'completed' ? 'text-muted line-through' : ''}`}>{it.title}</p>
                      <p className="text-xs text-muted">{TYPE[it.type]}{it.status === 'in_progress' && ' · in progress'}</p>
                      {it.description && <p className="mt-1 text-sm text-muted">{it.description}</p>}
                      <div className="mt-1 flex gap-4 text-sm">
                        {it.resource_url && <a href={it.resource_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 font-medium text-primary hover:underline">Open resource<ExternalLink className="h-3.5 w-3.5" aria-hidden /></a>}
                        {it.type === 'assess' && <Link to="/assessments" className="font-medium text-primary hover:underline">Go to assessments</Link>}
                      </div>
                    </div>
                    <Button variant={it.status === 'in_progress' ? 'primary' : 'secondary'} onClick={() => void mark(it, n.to)} aria-label={`${n.label}: ${it.title}`}>{n.label}</Button>
                  </li>) })}
              </ul>
              {ai[skill] && <div className="mt-4 rounded-md bg-sunken p-3 text-sm"><p className="mb-1 text-xs font-semibold text-muted">AI suggestions (search for these; links are not provided)</p><ul className="space-y-1">{ai[skill].map((s) => <li key={s.title}><strong>{s.title}</strong> <span className="text-muted">{s.why}</span></li>)}</ul></div>}
            </Panel>
          ))}
        </div>
      )}
    </>
  )
}
