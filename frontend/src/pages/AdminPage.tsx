import { useEffect, useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import { Alert, Badge, Button, ConfirmDialog, Input, PageHeader, Panel, Select, Skeleton, Stat, Tabs, Textarea } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useToast } from '../context/ToastContext'
import { ApiError, http } from '../services/api'

interface Catalog {
  categories: { id: number; name: string; description: string | null; is_active: boolean }[]
  skills: { id: number; name: string; slug: string; category: string; is_active: boolean }[]
  assessments: { id: number; title: string; skill_id: number; skill: string; category_id: number; is_active: boolean; questions: number }[]
  skill_categories: string[]; difficulties: string[]
}
const useCatalog = () => useAsync(() => http.get<Catalog>('/api/admin/catalog').then((r) => r.data))
const msg = (e: unknown) => (e instanceof ApiError ? (Object.values(e.fields)[0] ?? e.message) : 'Something went wrong.')

function Overview() {
  const { data, loading, error } = useAsync(() => http.get<Record<string, number | { skill: string; count: number }[]>>('/api/admin/stats').then((r) => r.data))
  if (loading) return <Skeleton className="h-40" />
  if (error || !data) return <Alert>{error}</Alert>
  const items: [string, string][] = [['users', 'Users'], ['active_users', 'Active'], ['admins', 'Admins'], ['resumes', 'Resumes'], ['attempts', 'Attempts'], ['completed_attempts', 'Completed'], ['questions', 'Active questions'], ['skills', 'Skills'], ['roles', 'Roles'], ['projects', 'Practice projects'], ['interview_questions', 'Interview questions']]
  return (
    <div className="space-y-6">
      <section className="rounded-lg border border-line bg-surface p-5"><dl className="grid grid-cols-2 gap-5 sm:grid-cols-3 lg:grid-cols-5">{items.map(([k, l]) => <Stat key={k} label={l} value={data[k] as number} />)}</dl></section>
      <Panel title="Questions per skill"><ul className="grid gap-x-8 gap-y-1.5 text-sm sm:grid-cols-2">{(data.questions_by_skill as { skill: string; count: number }[]).map((q) => <li key={q.skill} className="flex justify-between"><span>{q.skill}</span><strong className="tabular-nums">{q.count}</strong></li>)}</ul></Panel>
    </div>
  )
}

interface AdminUser { id: number; full_name: string; email: string; is_admin: boolean; is_active: boolean; last_login_at: string | null; skills: number; attempts: number }
function Users() {
  const [q, setQ] = useState('')
  const [page, setPage] = useState(1)
  const { data, reload } = useAsync(() => http.get<AdminUser[]>('/api/admin/users?per_page=100').then((r) => r.data))
  const toast = useToast()
  const [ask, setAsk] = useState<{ u: AdminUser; active: boolean } | null>(null)
  const rows = (data ?? []).filter((u) => `${u.full_name} ${u.email}`.toLowerCase().includes(q.toLowerCase()))
  const per = 15
  const toggle = async () => {
    try { await http.patch(`/api/admin/users/${ask!.u.id}`, { is_active: ask!.active }); setAsk(null); toast.success('User updated.'); await reload() } catch (e) { toast.error(msg(e)); setAsk(null) }
  }
  return (
    <Panel title="Registered users">
      <div className="mb-4 max-w-xs"><Input label="Search" value={q} onChange={(e) => { setQ(e.target.value); setPage(1) }} placeholder="Name or email" /></div>
      <div className="overflow-x-auto"><table className="w-full min-w-[36rem] text-left text-sm"><thead className="border-b border-line text-xs text-muted"><tr><th className="py-2 font-medium">User</th><th className="font-medium">Skills</th><th className="font-medium">Attempts</th><th className="font-medium">Last login</th><th className="font-medium">Status</th><th /></tr></thead>
        <tbody className="divide-y divide-line">{rows.slice((page - 1) * per, page * per).map((u) => (
          <tr key={u.id}><td className="py-2.5"><p className="font-medium">{u.full_name}{u.is_admin && <span className="ml-2"><Badge tone="info">admin</Badge></span>}</p><p className="text-xs text-muted">{u.email}</p></td>
            <td className="tabular-nums">{u.skills}</td><td className="tabular-nums">{u.attempts}</td><td className="text-muted">{u.last_login_at ? new Date(u.last_login_at).toLocaleDateString() : 'never'}</td>
            <td><Badge tone={u.is_active ? 'good' : 'bad'}>{u.is_active ? 'Active' : 'Deactivated'}</Badge></td>
            <td className="text-right"><Button variant="secondary" onClick={() => setAsk({ u, active: !u.is_active })}>{u.is_active ? 'Deactivate' : 'Reactivate'}</Button></td></tr>))}</tbody></table></div>
      {rows.length === 0 && <p className="py-4 text-sm text-muted">No users match.</p>}
      {rows.length > per && <div className="mt-4 flex items-center justify-between text-sm"><span className="text-muted">{rows.length} users</span><div className="flex gap-2"><Button variant="secondary" disabled={page === 1} onClick={() => setPage(page - 1)}>Previous</Button><Button variant="secondary" disabled={page * per >= rows.length} onClick={() => setPage(page + 1)}>Next</Button></div></div>}
      <ConfirmDialog open={!!ask} title={ask?.active ? 'Reactivate this user?' : 'Deactivate this user?'} confirmLabel={ask?.active ? 'Reactivate' : 'Deactivate'} danger={!ask?.active} onConfirm={toggle} onCancel={() => setAsk(null)}>
        {ask?.active ? `${ask.u.email} will be able to sign in again.` : `${ask?.u.email} is signed out immediately and can’t sign in. Their data is kept.`}</ConfirmDialog>
    </Panel>
  )
}

interface AdminQ { id: number; skill_id: number; skill: string; topic: string; difficulty: string; type: string; text: string; explanation: string | null; marks: number; is_active: boolean; accepted_answers: string[] | null; options: { text: string; is_correct: boolean }[] }
const blank = (skill_id: number): Record<string, unknown> => ({ skill_id, topic: '', difficulty: 'beginner', type: 'single', text: '', explanation: '', options: [{ text: '', is_correct: true }, { text: '', is_correct: false }], correct: true, accepted_answers: [''], marks: '' })

function Questions() {
  const cat = useCatalog()
  const [skill, setSkill] = useState('')
  const [diff, setDiff] = useState('')
  const [term, setTerm] = useState('')
  const [rows, setRows] = useState<AdminQ[] | null>(null)
  const [total, setTotal] = useState(0)
  const [form, setForm] = useState<{ id?: number; v: Record<string, unknown> } | null>(null)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const toast = useToast()
  const load = async () => {
    const qs = new URLSearchParams({ per_page: '50', ...(skill ? { skill_id: skill } : {}), ...(diff ? { difficulty: diff } : {}), ...(term ? { q: term } : {}) })
    const r = await http.get<AdminQ[]>(`/api/admin/questions?${qs}`); setRows(r.data); setTotal(r.meta?.total ?? r.data.length)
  }
  useEffect(() => { void load() }, [skill, diff]) // eslint-disable-line react-hooks/exhaustive-deps
  const v = form?.v ?? {}
  const set = (k: string, val: unknown) => { setForm({ ...form!, v: { ...v, [k]: val } }); setErrors({ ...errors, [k]: '' }) }
  const save = async () => {
    const body = { ...v, marks: v.marks === '' || v.marks == null ? undefined : Number(v.marks) }
    try {
      if (form!.id) await http.put(`/api/admin/questions/${form!.id}`, body); else await http.post('/api/admin/questions', body)
      toast.success('Question saved.'); setForm(null); await load()
    } catch (e) { if (e instanceof ApiError) setErrors(e.fields); toast.error(msg(e)) }
  }
  const retire = async (q: AdminQ) => { try { await http.del(`/api/admin/questions/${q.id}`); toast.success('Question retired. Past results are unaffected.'); await load() } catch (e) { toast.error(msg(e)) } }
  const skills = cat.data?.skills ?? []
  const options = v.options as { text: string; is_correct: boolean }[] | undefined
  const answers = v.accepted_answers as string[] | undefined

  if (form) return (
    <Panel title={form.id ? `Edit question #${form.id}` : 'New question'} action={<Button variant="secondary" onClick={() => setForm(null)}>Cancel</Button>}>
      <div className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-3">
          <Select label="Skill" value={String(v.skill_id ?? '')} error={errors.skill_id} options={skills.map((s) => ({ value: s.id, label: s.name }))} onChange={(e) => set('skill_id', Number(e.target.value))} />
          <Select label="Difficulty" value={String(v.difficulty)} error={errors.difficulty} options={['beginner', 'intermediate', 'advanced'].map((d) => ({ value: d, label: d }))} onChange={(e) => set('difficulty', e.target.value)} />
          <Select label="Type" value={String(v.type)} error={errors.type} options={[{ value: 'single', label: 'Single choice' }, { value: 'multiple', label: 'Multiple select' }, { value: 'true_false', label: 'True / False' }, { value: 'short', label: 'Short answer' }]} onChange={(e) => set('type', e.target.value)} />
          <Input label="Topic" value={String(v.topic ?? '')} error={errors.topic} onChange={(e) => set('topic', e.target.value)} />
          <Input label="Marks (blank = by difficulty)" type="number" value={String(v.marks ?? '')} error={errors.marks} onChange={(e) => set('marks', e.target.value)} />
        </div>
        <Textarea label="Question text" value={String(v.text ?? '')} error={errors.text} onChange={(e) => set('text', e.target.value)} />
        {(v.type === 'single' || v.type === 'multiple') && (
          <div><p className="mb-1.5 text-sm font-medium">Options <span className="font-normal text-muted">(tick the correct {v.type === 'single' ? 'one' : 'ones'})</span></p>
            <div className="space-y-2">{options?.map((o, i) => (
              <div key={i} className="flex items-center gap-2">
                <input aria-label={`Option ${i + 1} is correct`} type={v.type === 'single' ? 'radio' : 'checkbox'} name="correct" checked={o.is_correct} className="h-4 w-4 accent-[rgb(var(--c-primary))]"
                  onChange={(e) => set('options', options.map((x, j) => (v.type === 'single' ? { ...x, is_correct: j === i } : j === i ? { ...x, is_correct: e.target.checked } : x)))} />
                <input aria-label={`Option ${i + 1} text`} value={o.text} onChange={(e) => set('options', options.map((x, j) => (j === i ? { ...x, text: e.target.value } : x)))} className="h-10 flex-1 rounded-md border border-line bg-surface px-3 text-sm" />
                <button type="button" aria-label={`Remove option ${i + 1}`} disabled={options.length <= 2} onClick={() => set('options', options.filter((_, j) => j !== i))} className="text-muted hover:text-danger disabled:opacity-30"><Trash2 className="h-4 w-4" /></button>
              </div>))}</div>
            <Button type="button" variant="secondary" className="mt-2" onClick={() => set('options', [...options!, { text: '', is_correct: false }])}><Plus className="h-4 w-4" />Add option</Button>
            {errors.options && <p role="alert" className="mt-1 text-xs font-medium text-danger">{errors.options}</p>}</div>)}
        {v.type === 'true_false' && <Select label="Correct answer" value={String(v.correct)} error={errors.correct} options={[{ value: 'true', label: 'True' }, { value: 'false', label: 'False' }]} onChange={(e) => set('correct', e.target.value === 'true')} />}
        {v.type === 'short' && <Textarea label="Accepted answers (one per line)" value={(answers ?? []).join('\n')} error={errors.accepted_answers} hint="Matching ignores case, spaces and punctuation." onChange={(e) => set('accepted_answers', e.target.value.split('\n'))} className="min-h-20" />}
        <Textarea label="Explanation (shown after the assessment)" value={String(v.explanation ?? '')} onChange={(e) => set('explanation', e.target.value)} className="min-h-20" />
        <div className="flex justify-end"><Button onClick={save}>Save question</Button></div>
      </div>
    </Panel>)

  return (
    <Panel title={`Question bank${rows ? ` (${total})` : ''}`} action={<Button onClick={() => { setErrors({}); setForm({ v: blank(Number(skill) || skills[0]?.id || 0) }) }}><Plus className="h-4 w-4" />New question</Button>}>
      <div className="mb-4 grid gap-3 sm:grid-cols-4">
        <Select label="Skill" value={skill} placeholder="All skills" options={skills.map((s) => ({ value: s.id, label: s.name }))} onChange={(e) => setSkill(e.target.value)} />
        <Select label="Difficulty" value={diff} placeholder="All" options={['beginner', 'intermediate', 'advanced'].map((d) => ({ value: d, label: d }))} onChange={(e) => setDiff(e.target.value)} />
        <div className="sm:col-span-2"><Input label="Search text" value={term} onChange={(e) => setTerm(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') void load() }} placeholder="Press Enter to search" /></div>
      </div>
      {!rows ? <Skeleton className="h-40" /> : rows.length === 0 ? <p className="text-sm text-muted">No questions match.</p> : (
        <ul className="divide-y divide-line">{rows.map((q) => (
          <li key={q.id} className="flex flex-wrap items-start gap-3 py-3 text-sm">
            <div className="min-w-0 flex-1"><p className={q.is_active ? 'font-medium' : 'font-medium text-muted line-through'}>{q.text}</p>
              <p className="mt-0.5 text-xs text-muted">{q.skill} · {q.topic} · {q.difficulty} · {q.type.replace('_', '/')} · {q.marks} mark{q.marks === 1 ? '' : 's'}{!q.is_active && ' · retired'}</p></div>
            <Button variant="secondary" onClick={() => { setErrors({}); setForm({ id: q.id, v: { ...q, correct: q.options.find((o) => o.is_correct)?.text === 'True', accepted_answers: q.accepted_answers ?? [''], marks: q.marks } }) }}>Edit</Button>
            {q.is_active && <Button variant="ghost" onClick={() => void retire(q)}>Retire</Button>}
          </li>))}</ul>)}
    </Panel>
  )
}

interface AdminRole { id: number; name: string; description: string | null; interest_tags: string[]; education_keywords: string[]; is_active: boolean; skills: { skill_id: number; skill: string; weight: number; min_level_pct: number; is_core: boolean }[] }
function Roles() {
  const roles = useAsync(() => http.get<AdminRole[]>('/api/admin/roles').then((r) => r.data))
  const cat = useCatalog()
  const toast = useToast()
  const [sel, setSel] = useState<number | null>(null)
  const [skills, setSkills] = useState<AdminRole['skills']>([])
  const [meta, setMeta] = useState({ description: '', tags: '', edu: '' })
  const [add, setAdd] = useState('')
  const [newName, setNewName] = useState('')
  const role = roles.data?.find((r) => r.id === sel)
  useEffect(() => { if (role) { setSkills(role.skills); setMeta({ description: role.description ?? '', tags: role.interest_tags.join(', '), edu: role.education_keywords.join(', ') }) } }, [role?.id]) // eslint-disable-line react-hooks/exhaustive-deps
  const split = (s: string) => s.split(',').map((x) => x.trim()).filter(Boolean)
  const upd = (i: number, patch: Partial<AdminRole['skills'][0]>) => setSkills(skills.map((s, j) => (j === i ? { ...s, ...patch } : s)))
  const save = async () => {
    try {
      await http.put(`/api/admin/roles/${sel}`, { description: meta.description, interest_tags: split(meta.tags), education_keywords: split(meta.edu) })
      await http.put(`/api/admin/roles/${sel}/skills`, { skills: skills.map(({ skill_id, weight, min_level_pct, is_core }) => ({ skill_id, weight: Number(weight), min_level_pct: Number(min_level_pct), is_core })) })
      toast.success('Role saved. Matches update immediately.'); await roles.reload()
    } catch (e) { toast.error(msg(e)) }
  }
  const create = async () => { try { const r = await http.post<AdminRole>('/api/admin/roles', { name: newName }); setNewName(''); await roles.reload(); setSel(r.data.id) } catch (e) { toast.error(msg(e)) } }
  return (
    <div className="grid gap-6 lg:grid-cols-[16rem_minmax(0,1fr)]">
      <Panel title="Roles">
        <ul className="-mx-2 mb-4 space-y-0.5">{(roles.data ?? []).map((r) => <li key={r.id}><button onClick={() => setSel(r.id)} className={`w-full rounded-md px-2 py-1.5 text-left text-sm ${sel === r.id ? 'bg-primary/12 font-semibold text-primary' : 'hover:bg-sunken'}`}>{r.name}</button></li>)}</ul>
        <Input label="New role" value={newName} onChange={(e) => setNewName(e.target.value)} /><Button className="mt-2 w-full" variant="secondary" disabled={!newName.trim()} onClick={create}>Add role</Button>
      </Panel>
      {!role ? <Panel><p className="text-sm text-muted">Select a role to edit its required skills.</p></Panel> : (
        <Panel title={role.name} action={<Button onClick={save}>Save role</Button>}>
          <div className="space-y-4">
            <Textarea label="Description" value={meta.description} onChange={(e) => setMeta({ ...meta, description: e.target.value })} className="min-h-16" />
            <div className="grid gap-4 sm:grid-cols-2"><Input label="Interest tags (comma separated)" value={meta.tags} onChange={(e) => setMeta({ ...meta, tags: e.target.value })} /><Input label="Education keywords" value={meta.edu} onChange={(e) => setMeta({ ...meta, edu: e.target.value })} /></div>
            <div className="overflow-x-auto"><table className="w-full min-w-[32rem] text-left text-sm"><thead className="border-b border-line text-xs text-muted"><tr><th className="py-2 font-medium">Skill</th><th className="font-medium">Weight (0-5)</th><th className="font-medium">Required level %</th><th className="font-medium">Core</th><th /></tr></thead>
              <tbody className="divide-y divide-line">{skills.map((s, i) => (
                <tr key={s.skill_id}><td className="py-2 font-medium">{s.skill}</td>
                  <td><input aria-label={`${s.skill} weight`} type="number" step="0.5" min="0.5" max="5" value={s.weight} onChange={(e) => upd(i, { weight: Number(e.target.value) })} className="h-9 w-20 rounded-md border border-line bg-surface px-2" /></td>
                  <td><input aria-label={`${s.skill} required level`} type="number" min="1" max="100" value={s.min_level_pct} onChange={(e) => upd(i, { min_level_pct: Number(e.target.value) })} className="h-9 w-24 rounded-md border border-line bg-surface px-2" /></td>
                  <td><input aria-label={`${s.skill} is core`} type="checkbox" checked={s.is_core} onChange={(e) => upd(i, { is_core: e.target.checked })} className="h-4 w-4 accent-[rgb(var(--c-primary))]" /></td>
                  <td className="text-right"><button aria-label={`Remove ${s.skill}`} onClick={() => setSkills(skills.filter((_, j) => j !== i))} className="text-muted hover:text-danger"><Trash2 className="h-4 w-4" /></button></td></tr>))}</tbody></table></div>
            <div className="flex items-end gap-2"><div className="flex-1"><Select label="Add required skill" value={add} placeholder="Choose…" options={(cat.data?.skills ?? []).filter((s) => !skills.some((x) => x.skill_id === s.id)).map((s) => ({ value: s.id, label: s.name }))} onChange={(e) => setAdd(e.target.value)} /></div>
              <Button variant="secondary" disabled={!add} onClick={() => { const s = cat.data!.skills.find((x) => x.id === Number(add))!; setSkills([...skills, { skill_id: s.id, skill: s.name, weight: 1, min_level_pct: 60, is_core: false }]); setAdd('') }}>Add</Button></div>
          </div>
        </Panel>)}
    </div>
  )
}

interface Resource { id: number; skill_id: number; skill: string; title: string; url: string | null; kind: string; level: string }
function Content() {
  const cat = useCatalog()
  const res = useAsync(() => http.get<Resource[]>('/api/admin/resources').then((r) => r.data))
  const toast = useToast()
  const [catName, setCatName] = useState('')
  const [sk, setSk] = useState({ name: '', category: '' })
  const [as, setAs] = useState({ category_id: '', skill_id: '', title: '' })
  const [r, setR] = useState({ skill_id: '', title: '', url: '', kind: 'docs', level: 'beginner' })
  const run = async (fn: () => Promise<unknown>, ok: string, after: () => void) => { try { await fn(); toast.success(ok); after(); await cat.reload(); await res.reload() } catch (e) { toast.error(msg(e)) } }
  const skills = (cat.data?.skills ?? []).map((s) => ({ value: s.id, label: s.name }))
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Panel title="Assessment categories"><ul className="mb-4 space-y-1 text-sm">{(cat.data?.categories ?? []).map((c) => <li key={c.id} className="flex justify-between"><span>{c.name}</span>{!c.is_active && <Badge>hidden</Badge>}</li>)}</ul>
        <div className="flex items-end gap-2"><div className="flex-1"><Input label="New category" value={catName} onChange={(e) => setCatName(e.target.value)} /></div><Button variant="secondary" disabled={!catName.trim()} onClick={() => run(() => http.post('/api/admin/categories', { name: catName }), 'Category added.', () => setCatName(''))}>Add</Button></div></Panel>
      <Panel title="Add a skill"><div className="space-y-3"><Input label="Skill name" value={sk.name} onChange={(e) => setSk({ ...sk, name: e.target.value })} />
        <Select label="Category" value={sk.category} placeholder="Choose…" options={(cat.data?.skill_categories ?? []).map((c) => ({ value: c, label: c }))} onChange={(e) => setSk({ ...sk, category: e.target.value })} />
        <Button variant="secondary" disabled={!sk.name.trim() || !sk.category} onClick={() => run(() => http.post('/api/admin/skills', sk), 'Skill added.', () => setSk({ name: '', category: '' }))}>Add skill</Button></div></Panel>
      <Panel title="Create an assessment for a skill"><div className="space-y-3">
        <Select label="Category" value={as.category_id} placeholder="Choose…" options={(cat.data?.categories ?? []).map((c) => ({ value: c.id, label: c.name }))} onChange={(e) => setAs({ ...as, category_id: e.target.value })} />
        <Select label="Skill" value={as.skill_id} placeholder="Choose…" options={skills.filter((s) => !cat.data?.assessments.some((a) => a.skill_id === s.value))} onChange={(e) => setAs({ ...as, skill_id: e.target.value })} />
        <Input label="Title" value={as.title} onChange={(e) => setAs({ ...as, title: e.target.value })} />
        <Button variant="secondary" disabled={!as.category_id || !as.skill_id || !as.title.trim()} onClick={() => run(() => http.post('/api/admin/assessments', { category_id: Number(as.category_id), skill_id: Number(as.skill_id), title: as.title }), 'Assessment created. Add questions so users can take it.', () => setAs({ category_id: '', skill_id: '', title: '' }))}>Create</Button></div></Panel>
      <Panel title="Assessments"><ul className="max-h-72 space-y-1 overflow-auto text-sm">{(cat.data?.assessments ?? []).map((a) => <li key={a.id} className="flex items-center justify-between gap-2"><span>{a.title}</span><span className="text-xs text-muted">{a.questions} questions</span>
        <button className="text-xs font-medium text-primary hover:underline" onClick={() => run(() => http.put(`/api/admin/assessments/${a.id}`, { is_active: !a.is_active }), 'Updated.', () => undefined)}>{a.is_active ? 'Hide' : 'Show'}</button></li>)}</ul></Panel>
      <Panel title="Learning resources" className="lg:col-span-2">
        <div className="mb-5 grid gap-3 sm:grid-cols-6 sm:items-end">
          <div className="sm:col-span-2"><Select label="Skill" value={r.skill_id} placeholder="Choose…" options={skills} onChange={(e) => setR({ ...r, skill_id: e.target.value })} /></div>
          <div className="sm:col-span-2"><Input label="Title" value={r.title} onChange={(e) => setR({ ...r, title: e.target.value })} /></div>
          <div className="sm:col-span-2"><Input label="Link" value={r.url} placeholder="https://" onChange={(e) => setR({ ...r, url: e.target.value })} /></div>
          <Select label="Type" value={r.kind} options={['docs', 'article', 'video', 'course', 'book'].map((v) => ({ value: v, label: v }))} onChange={(e) => setR({ ...r, kind: e.target.value })} />
          <Select label="Level" value={r.level} options={['beginner', 'intermediate', 'advanced'].map((v) => ({ value: v, label: v }))} onChange={(e) => setR({ ...r, level: e.target.value })} />
          <Button disabled={!r.skill_id || !r.title.trim()} onClick={() => run(() => http.post('/api/admin/resources', { ...r, skill_id: Number(r.skill_id) }), 'Resource added.', () => setR({ ...r, title: '', url: '' }))}>Add</Button>
        </div>
        <ul className="max-h-80 divide-y divide-line overflow-auto text-sm">{(res.data ?? []).map((x) => <li key={x.id} className="flex items-center gap-3 py-2"><span className="w-36 shrink-0 text-muted">{x.skill}</span><span className="flex-1 truncate">{x.title}</span><Badge>{x.level}</Badge>
          <button aria-label={`Delete ${x.title}`} className="text-muted hover:text-danger" onClick={() => run(() => http.del(`/api/admin/resources/${x.id}`), 'Resource deleted.', () => undefined)}><Trash2 className="h-4 w-4" /></button></li>)}</ul>
      </Panel>
    </div>
  )
}

interface AdminProject {
  id: number; title: string; description: string; difficulty: string; skill_slugs: string[]
  skills: string[]; objectives: string[]; steps: string[]; expected_outcome: string | null; is_active: boolean
}
interface ProjectDraft {
  id?: number; title: string; description: string; difficulty: string; skill_slugs: string[]
  objectives: string; steps: string; expected_outcome: string
}
interface AdminInterviewQuestion {
  id: number; skill_id: number | null; skill: string; difficulty: string; text: string; keywords: string[]; is_active: boolean
}
interface InterviewDraft { id?: number; skill_id: string; difficulty: string; text: string; keywords: string }

const emptyProject = (): ProjectDraft => ({ title: '', description: '', difficulty: 'beginner', skill_slugs: [], objectives: '', steps: '', expected_outcome: '' })
const emptyInterviewQuestion = (): InterviewDraft => ({ skill_id: '', difficulty: 'beginner', text: '', keywords: '' })
const lines = (value: string) => value.split('\n').map((item) => item.trim()).filter(Boolean)

function Banks() {
  const cat = useCatalog()
  const projects = useAsync(() => http.get<AdminProject[]>('/api/admin/projects').then((r) => r.data))
  const questions = useAsync(() => http.get<AdminInterviewQuestion[]>('/api/admin/interview-questions').then((r) => r.data))
  const toast = useToast()
  const [project, setProject] = useState<ProjectDraft | null>(null)
  const [question, setQuestion] = useState<InterviewDraft | null>(null)
  const [filter, setFilter] = useState('')
  const skills = cat.data?.skills ?? []
  const visibleQuestions = (questions.data ?? []).filter((row) => `${row.skill} ${row.text}`.toLowerCase().includes(filter.toLowerCase()))

  const saveProject = async () => {
    if (!project) return
    const body = { ...project, objectives: lines(project.objectives), steps: lines(project.steps) }
    try {
      if (project.id) await http.put(`/api/admin/projects/${project.id}`, body)
      else await http.post('/api/admin/projects', body)
      toast.success('Practice project saved.')
      setProject(null)
      await projects.reload()
    } catch (e) { toast.error(msg(e)) }
  }
  const toggleProject = async (row: AdminProject) => {
    try {
      await http.put(`/api/admin/projects/${row.id}`, { is_active: !row.is_active })
      toast.success(row.is_active ? 'Project retired.' : 'Project restored.')
      await projects.reload()
    } catch (e) { toast.error(msg(e)) }
  }
  const saveQuestion = async () => {
    if (!question) return
    const body = { ...question, skill_id: question.skill_id ? Number(question.skill_id) : null, keywords: lines(question.keywords) }
    try {
      if (question.id) await http.put(`/api/admin/interview-questions/${question.id}`, body)
      else await http.post('/api/admin/interview-questions', body)
      toast.success('Interview question saved.')
      setQuestion(null)
      await questions.reload()
    } catch (e) { toast.error(msg(e)) }
  }
  const toggleQuestion = async (row: AdminInterviewQuestion) => {
    try {
      await http.put(`/api/admin/interview-questions/${row.id}`, { is_active: !row.is_active })
      toast.success(row.is_active ? 'Interview question retired.' : 'Interview question restored.')
      await questions.reload()
    } catch (e) { toast.error(msg(e)) }
  }

  return (
    <div className="space-y-6">
      <Panel title="Practice project bank" action={<Button onClick={() => setProject(emptyProject())}><Plus className="h-4 w-4" />New project</Button>}>
        {project && <div className="mb-5 space-y-3 rounded-lg border border-line bg-sunken/40 p-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <Input label="Title" value={project.title} onChange={(e) => setProject({ ...project, title: e.target.value })} />
            <Select label="Difficulty" value={project.difficulty} options={['beginner', 'intermediate', 'advanced'].map((value) => ({ value, label: value }))} onChange={(e) => setProject({ ...project, difficulty: e.target.value })} />
          </div>
          <Textarea label="Description" value={project.description} onChange={(e) => setProject({ ...project, description: e.target.value })} />
          <div><p className="mb-1.5 text-sm font-medium">Skills</p><div className="grid max-h-36 grid-cols-2 gap-1 overflow-auto rounded-md border border-line bg-surface p-2 text-sm sm:grid-cols-3">
            {skills.map((skill) => <label key={skill.id} className="flex items-center gap-2"><input type="checkbox" checked={project.skill_slugs.includes(skill.slug)}
              onChange={(e) => setProject({ ...project, skill_slugs: e.target.checked ? [...project.skill_slugs, skill.slug] : project.skill_slugs.filter((item) => item !== skill.slug) })} />{skill.name}</label>)}
          </div></div>
          <div className="grid gap-3 sm:grid-cols-2">
            <Textarea label="Objectives (one per line)" value={project.objectives} onChange={(e) => setProject({ ...project, objectives: e.target.value })} className="min-h-24" />
            <Textarea label="Steps (one per line)" value={project.steps} onChange={(e) => setProject({ ...project, steps: e.target.value })} className="min-h-24" />
          </div>
          <Textarea label="Expected outcome" value={project.expected_outcome} onChange={(e) => setProject({ ...project, expected_outcome: e.target.value })} />
          <div className="flex justify-end gap-2"><Button variant="secondary" onClick={() => setProject(null)}>Cancel</Button><Button disabled={!project.title.trim() || !project.description.trim()} onClick={() => void saveProject()}>Save project</Button></div>
        </div>}
        {projects.error && <Alert>{projects.error}</Alert>}
        {!projects.data ? <Skeleton className="h-24" /> : <ul className="divide-y divide-line">
          {projects.data.map((row) => <li key={row.id} className="flex flex-wrap items-start gap-3 py-3 text-sm">
            <div className="min-w-0 flex-1"><p className={row.is_active ? 'font-medium' : 'font-medium text-muted line-through'}>{row.title}</p>
              <p className="text-xs text-muted">{row.difficulty} · {row.skills.length ? row.skills.join(', ') : 'No skills'} · {row.steps.length} steps{!row.is_active && ' · retired'}</p></div>
            <Button variant="secondary" onClick={() => setProject({ id: row.id, title: row.title, description: row.description, difficulty: row.difficulty,
              skill_slugs: row.skill_slugs, objectives: row.objectives.join('\n'), steps: row.steps.join('\n'), expected_outcome: row.expected_outcome ?? '' })}>Edit</Button>
            <Button variant="ghost" onClick={() => void toggleProject(row)}>{row.is_active ? 'Retire' : 'Restore'}</Button>
          </li>)}
        </ul>}
      </Panel>

      <Panel title="Interview question bank" action={<Button onClick={() => setQuestion(emptyInterviewQuestion())}><Plus className="h-4 w-4" />New question</Button>}>
        {question && <div className="mb-5 space-y-3 rounded-lg border border-line bg-sunken/40 p-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <Select label="Skill group" value={question.skill_id} placeholder="Behavioural" options={skills.map((skill) => ({ value: skill.id, label: skill.name }))} onChange={(e) => setQuestion({ ...question, skill_id: e.target.value })} />
            <Select label="Difficulty" value={question.difficulty} options={['beginner', 'intermediate', 'advanced'].map((value) => ({ value, label: value }))} onChange={(e) => setQuestion({ ...question, difficulty: e.target.value })} />
          </div>
          <Textarea label="Question text" value={question.text} onChange={(e) => setQuestion({ ...question, text: e.target.value })} />
          <Textarea label="Key points (one per line)" value={question.keywords} onChange={(e) => setQuestion({ ...question, keywords: e.target.value })} className="min-h-24" />
          <div className="flex justify-end gap-2"><Button variant="secondary" onClick={() => setQuestion(null)}>Cancel</Button><Button disabled={!question.text.trim()} onClick={() => void saveQuestion()}>Save question</Button></div>
        </div>}
        <div className="mb-3 max-w-sm"><Input label="Filter by skill or question" value={filter} onChange={(e) => setFilter(e.target.value)} /></div>
        {questions.error && <Alert>{questions.error}</Alert>}
        {!questions.data ? <Skeleton className="h-24" /> : visibleQuestions.length === 0 ? <p className="text-sm text-muted">No questions match.</p> : <ul className="max-h-[32rem] divide-y divide-line overflow-auto">
          {visibleQuestions.map((row) => <li key={row.id} className="flex flex-wrap items-start gap-3 py-3 text-sm">
            <div className="min-w-0 flex-1"><p className={row.is_active ? 'font-medium' : 'font-medium text-muted line-through'}>{row.text}</p>
              <p className="mt-0.5 text-xs text-muted">{row.skill} · {row.difficulty} · Key points: {row.keywords.join(', ')}{!row.is_active && ' · retired'}</p></div>
            <Button variant="secondary" onClick={() => setQuestion({ id: row.id, skill_id: row.skill_id ? String(row.skill_id) : '', difficulty: row.difficulty, text: row.text, keywords: row.keywords.join('\n') })}>Edit</Button>
            <Button variant="ghost" onClick={() => void toggleQuestion(row)}>{row.is_active ? 'Retire' : 'Restore'}</Button>
          </li>)}
        </ul>}
      </Panel>
    </div>
  )
}

export function AdminPage() {
  const [tab, setTab] = useState<'overview' | 'users' | 'questions' | 'roles' | 'content' | 'banks'>('overview')
  return (
    <>
      <PageHeader title="Administration" subtitle="Manage users, assessments, questions, career requirements and learning content." />
      <Tabs tabs={[{ id: 'overview', label: 'Overview' }, { id: 'users', label: 'Users' }, { id: 'questions', label: 'Questions' }, { id: 'roles', label: 'Career roles' }, { id: 'content', label: 'Skills & content' }, { id: 'banks', label: 'Practice & interview banks' }]} value={tab} onChange={setTab} />
      {tab === 'overview' && <Overview />}{tab === 'users' && <Users />}{tab === 'questions' && <Questions />}{tab === 'roles' && <Roles />}{tab === 'content' && <Content />}{tab === 'banks' && <Banks />}
    </>
  )
}
