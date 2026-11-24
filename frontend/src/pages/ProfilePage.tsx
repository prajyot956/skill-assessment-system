import { useEffect, useState, type FormEvent, type KeyboardEvent } from 'react'
import { Link } from 'react-router-dom'
import { Plus, Sparkles, X } from 'lucide-react'
import { Alert, Badge, Button, ConfirmDialog, EmptyState, Input, PageHeader, Panel, ProgressBar, Select, Skeleton, Textarea } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useToast } from '../context/ToastContext'
import { api, ApiError, http } from '../services/api'
import { isValidPhone, isValidUrl, type FieldErrors } from '../utils/validation'
import { FIELDS, REQUIRED, SECTION_LABEL, type Section } from '../utils/sections'
import type { Profile, UserSkillRow } from '../types'

const WORK_TYPES: [string, string][] = [['full_time', 'Full-time'], ['internship', 'Internship'], ['part_time', 'Part-time'], ['freelance', 'Freelance'], ['remote_only', 'Remote only']]
const LEVEL = { assessment_verified: ['Verified', 'good'], user_confirmed: ['Confirmed', 'info'], resume_detected: ['Detected', 'neutral'] } as const

export function ProfilePage() {
  const { data, error, loading, reload, setData } = useAsync<Profile>(api.profile.get)
  return (
    <>
      <PageHeader title="My Profile" subtitle="Your details, used for assessments and career matching." />
      {loading && !data && <div className="space-y-4" aria-busy="true"><Skeleton className="h-40" /><Skeleton className="h-96" /></div>}
      {error && <div className="space-y-3"><Alert>{error}</Alert><button onClick={reload} className="text-sm font-medium text-primary hover:underline">Try again</button></div>}
      {data && <ProfileBody profile={data} onSaved={setData} refresh={async () => setData(await api.profile.get())} />}
    </>
  )
}

type Item = Record<string, unknown> & { id: number }

function SectionManager({ section, items, refresh }: { section: Section; items: Item[]; refresh: () => Promise<void> }) {
  const toast = useToast()
  const fields = FIELDS[section]
  const [editing, setEditing] = useState<{ id?: number; v: Record<string, unknown> } | null>(null)
  const [errors, setErrors] = useState<FieldErrors>({})
  const [del, setDel] = useState<Item | null>(null)
  const label = (it: Item) => String(it[REQUIRED[section]] ?? '')
  const save = async () => {
    const v = { ...editing!.v }
    for (const f of fields) if (f.kind !== 'list' && f.kind !== 'number' && v[f.key] === '') v[f.key] = null
    try {
      if (editing!.id) await http.put(`/api/profile/${section}/${editing!.id}`, v); else await http.post(`/api/profile/${section}`, v)
      toast.success('Saved.'); setEditing(null); setErrors({}); await refresh()
    } catch (e) { if (e instanceof ApiError && Object.keys(e.fields).length) setErrors(e.fields); else toast.error(e instanceof ApiError ? e.message : 'Couldn’t save.') }
  }
  const remove = async () => { try { await http.del(`/api/profile/${section}/${del!.id}`); toast.success('Removed.'); setDel(null); await refresh() } catch { toast.error('Couldn’t remove that.'); setDel(null) } }
  const set = (k: string, val: unknown) => { setEditing({ ...editing!, v: { ...editing!.v, [k]: val } }); setErrors({ ...errors, [k]: '' }) }

  return (
    <Panel title={SECTION_LABEL[section]} action={!editing && <Button variant="secondary" onClick={() => { setErrors({}); setEditing({ v: section === 'experience' ? { kind: 'job' } : section === 'projects' ? { technologies: [] } : {} }) }}><Plus className="h-4 w-4" />Add</Button>}>
      {editing && (
        <div className="mb-5 rounded-md border border-primary/40 bg-primary/5 p-4">
          <div className="grid gap-3 sm:grid-cols-2">
            {fields.map((f) => { const v = editing.v[f.key]; const wide = f.wide ? 'sm:col-span-2' : ''; const err = errors[f.key]
              if (f.kind === 'area') return <div key={f.key} className={wide}><Textarea label={f.label} value={(v as string) ?? ''} error={err} className="min-h-20" onChange={(e) => set(f.key, e.target.value)} /></div>
              if (f.kind === 'choice') return <div key={f.key} className={wide}><Select label={f.label} value={(v as string) ?? f.choices![0]} options={f.choices!.map((c) => ({ value: c, label: c }))} onChange={(e) => set(f.key, e.target.value)} /></div>
              if (f.kind === 'list') return <div key={f.key} className={wide}><Input label={f.label} value={((v as string[]) ?? []).join(', ')} error={err} onChange={(e) => set(f.key, e.target.value.split(',').map((x) => x.trim()).filter(Boolean))} /></div>
              return <div key={f.key} className={wide}><Input label={f.label} type={f.kind === 'number' ? 'number' : 'text'} value={(v as string | number) ?? ''} error={err} onChange={(e) => set(f.key, f.kind === 'number' ? (e.target.value ? Number(e.target.value) : null) : e.target.value)} /></div> })}
          </div>
          <div className="mt-4 flex justify-end gap-2"><Button variant="secondary" onClick={() => { setEditing(null); setErrors({}) }}>Cancel</Button><Button onClick={save}>Save</Button></div>
        </div>)}
      {items.length === 0 && !editing && <EmptyState title={`No ${SECTION_LABEL[section].toLowerCase()} yet`}>Add an entry here, or <Link to="/resume" className="font-medium text-primary hover:underline">import it from your resume</Link>.</EmptyState>}
      <ul className="-my-2 divide-y divide-line">{items.map((it) => (
        <li key={it.id} className="flex items-start gap-3 py-3 text-sm">
          <div className="min-w-0 flex-1"><p className="font-medium">{section === 'education' ? [it.degree, it.specialization].filter(Boolean).join(', ') || label(it) : section === 'experience' ? `${it.title ?? it.kind} · ${label(it)}` : label(it)}</p>
            <p className="text-muted">{section === 'education' ? `${it.institution}${it.graduation_year ? ` · ${it.graduation_year}` : ''}` : section === 'experience' ? String(it.duration ?? '') : section === 'projects' ? String(it.description ?? '') : [it.issuer, it.completed_on].filter(Boolean).join(' · ')}</p>
            {section === 'projects' && (it.technologies as string[]).length > 0 && <p className="mt-1 text-xs text-muted">{(it.technologies as string[]).join(' · ')}</p>}</div>
          <Button variant="ghost" onClick={() => { setErrors({}); setEditing({ id: it.id, v: { ...it } }) }} aria-label={`Edit ${label(it)}`}>Edit</Button>
          <Button variant="ghost" onClick={() => setDel(it)} aria-label={`Delete ${label(it)}`}>Delete</Button>
        </li>))}</ul>
      <ConfirmDialog open={!!del} title="Delete this entry?" confirmLabel="Delete" danger onConfirm={remove} onCancel={() => setDel(null)}>“{del && label(del)}” will be removed from your profile.</ConfirmDialog>
    </Panel>
  )
}

function SkillsManager() {
  const { data, reload, error } = useAsync(() => http.get<UserSkillRow[]>('/api/skills/mine').then((r) => r.data))
  const tax = useAsync(() => http.get<{ skills: { id: number; name: string; category: string }[]; categories: string[] }>('/api/skills').then((r) => r.data))
  const toast = useToast()
  const [name, setName] = useState('')
  const [cat, setCat] = useState('')
  const [del, setDel] = useState<UserSkillRow | null>(null)
  const known = tax.data?.skills.some((s) => s.name.toLowerCase() === name.trim().toLowerCase())
  const add = async () => {
    try { await http.post('/api/skills/mine', { name, category: cat || undefined }); setName(''); setCat(''); toast.success('Skill added.'); await reload() }
    catch (e) { toast.error(e instanceof ApiError ? (Object.values(e.fields)[0] ?? e.message) : 'Couldn’t add that skill.') }
  }
  const remove = async () => { try { await http.del(`/api/skills/mine/${del!.id}`); setDel(null); await reload() } catch { toast.error('Couldn’t remove that skill.'); setDel(null) } }
  const groups = (data ?? []).reduce<Record<string, UserSkillRow[]>>((a, s) => { (a[s.category] ??= []).push(s); return a }, {})
  return (
    <Panel title="Skills" action={<Link to="/analysis" className="text-sm font-medium text-primary hover:underline">Skill analysis</Link>}>
      {error && <Alert>{error}</Alert>}
      {data && data.length === 0 && <EmptyState title="No skills yet">Add skills below or <Link to="/resume" className="font-medium text-primary hover:underline">import them from your resume</Link>. Levels come from assessments.</EmptyState>}
      <div className="space-y-4">{Object.entries(groups).map(([c, list]) => (
        <div key={c}><h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted">{c}</h3>
          <ul className="flex flex-wrap gap-2">{list.map((s) => (
            <li key={s.id} className="inline-flex items-center gap-2 rounded-md border border-line px-2.5 py-1 text-sm">{s.name}
              <Badge tone={LEVEL[s.evidence_level][1]}>{s.proficiency_pct !== null ? `${s.proficiency_pct}%` : LEVEL[s.evidence_level][0]}</Badge>
              <button aria-label={`Remove ${s.name}`} onClick={() => setDel(s)} className="text-muted hover:text-danger"><X className="h-3.5 w-3.5" /></button></li>))}</ul></div>))}</div>
      <div className="mt-5 grid gap-3 border-t border-line pt-5 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
        <Input label="Add a skill" list="profile-skills" value={name} onChange={(e) => setName(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); if (name.trim() && (known || cat)) void add() } }} />
        <datalist id="profile-skills">{(tax.data?.skills ?? []).map((s) => <option key={s.id} value={s.name} />)}</datalist>
        <Select label="Category (new skills only)" value={cat} placeholder="Choose…" disabled={!!known || !name.trim()} options={(tax.data?.categories ?? []).map((c) => ({ value: c, label: c }))} onChange={(e) => setCat(e.target.value)} />
        <Button variant="secondary" disabled={!name.trim() || (!known && !cat)} onClick={add}><Plus className="h-4 w-4" />Add</Button>
      </div>
      <ConfirmDialog open={!!del} title="Remove this skill?" confirmLabel="Remove" danger onConfirm={remove} onCancel={() => setDel(null)}>
        {del?.proficiency_pct !== null ? 'Your assessment history is kept, but this skill’s verified level is removed from your profile.' : `“${del?.name}” is removed from your profile.`}</ConfirmDialog>
    </Panel>
  )
}

function ProfileBody({ profile, onSaved, refresh }: { profile: Profile; onSaved: (p: Profile) => void; refresh: () => Promise<void> }) {
  const toast = useToast()
  const roles = useAsync(() => http.get<{ id: number; name: string }[]>('/api/careers/roles').then((r) => r.data))
  const [f, setF] = useState(() => toForm(profile))
  const [tag, setTag] = useState('')
  const [errors, setErrors] = useState<FieldErrors>({})
  const [busy, setBusy] = useState(false)
  const [suggest, setSuggest] = useState<{ summary: string; source: string } | null>(null)
  useEffect(() => { setF(toForm(profile)) }, [profile])

  const set = <K extends keyof typeof f>(k: K, v: (typeof f)[K]) => { setF((p) => ({ ...p, [k]: v })); setErrors((e) => { const n = { ...e }; delete n[k]; return n }) }
  const addTag = () => { const t = tag.trim().replace(/,$/, ''); if (t && !f.interests.some((i) => i.toLowerCase() === t.toLowerCase())) set('interests', [...f.interests, t]); setTag('') }
  const onTagKey = (e: KeyboardEvent) => { if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); addTag() } else if (e.key === 'Backspace' && !tag && f.interests.length) set('interests', f.interests.slice(0, -1)) }
  const getSuggestion = async () => {
    try { setSuggest((await http.post<{ summary: string; source: string }>('/api/profile/suggest-summary')).data) }
    catch (e) { toast.error(e instanceof ApiError ? e.message : 'Couldn’t suggest a summary.') }
  }

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    const errs: FieldErrors = {}
    if (!f.full_name.trim()) errs.full_name = 'Enter your full name.'
    if (f.phone && !isValidPhone(f.phone)) errs.phone = 'Enter a valid phone number.'
    for (const k of ['linkedin_url', 'github_url', 'portfolio_url'] as const) if (f[k] && !isValidUrl(f[k])) errs[k] = 'Enter a full link starting with http:// or https://.'
    setErrors(errs)
    if (Object.keys(errs).length) { toast.error('Fix the highlighted fields and save again.'); return }
    setBusy(true)
    try {
      const saved = await api.profile.update({
        full_name: f.full_name, phone: f.phone || null, location: f.location || null, summary: f.summary || null,
        linkedin_url: f.linkedin_url || null, github_url: f.github_url || null, portfolio_url: f.portfolio_url || null,
        interests: f.interests, preferences: { work_types: f.work_types }, target_role_id: f.target_role_id ? Number(f.target_role_id) : null,
      })
      onSaved(saved); toast.success('Profile saved.')
    } catch (err) {
      if (err instanceof ApiError && Object.keys(err.fields).length) { setErrors(err.fields); toast.error('Fix the highlighted fields and save again.') }
      else toast.error(err instanceof ApiError ? err.message : 'Couldn’t save your profile. Please try again.')
    } finally { setBusy(false) }
  }

  const missing = profile.completion.items.filter((i) => !i.done)
  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
      <form onSubmit={submit} noValidate className="space-y-6">
        <Panel title="Personal information">
          <div className="grid gap-4 sm:grid-cols-2">
            <Input label="Full name" value={f.full_name} error={errors.full_name} onChange={(e) => set('full_name', e.target.value)} />
            <Input label="Email" value={profile.email} readOnly disabled hint="Email can’t be changed here." />
            <Input label="Phone" value={f.phone} error={errors.phone} onChange={(e) => set('phone', e.target.value)} />
            <Input label="Location" value={f.location} error={errors.location} onChange={(e) => set('location', e.target.value)} />
            <Input label="LinkedIn" placeholder="https://linkedin.com/in/…" value={f.linkedin_url} error={errors.linkedin_url} onChange={(e) => set('linkedin_url', e.target.value)} />
            <Input label="GitHub" placeholder="https://github.com/…" value={f.github_url} error={errors.github_url} onChange={(e) => set('github_url', e.target.value)} />
            <div className="sm:col-span-2"><Input label="Portfolio" placeholder="https://…" value={f.portfolio_url} error={errors.portfolio_url} onChange={(e) => set('portfolio_url', e.target.value)} /></div>
          </div>
        </Panel>

        <Panel title="Professional summary" action={<Button type="button" variant="secondary" onClick={getSuggestion}><Sparkles className="h-4 w-4" />Suggest</Button>}>
          <Textarea label="Summary" value={f.summary} error={errors.summary} maxLength={2000} hint="Two or three sentences on your background and what you’re aiming for." onChange={(e) => set('summary', e.target.value)} />
          {suggest && (
            <div className="mt-3 rounded-md border border-primary/40 bg-primary/5 p-3 text-sm">
              <p className="mb-1 text-xs font-semibold text-muted">Suggestion ({suggest.source === 'ai' ? 'AI-written' : 'built from your profile'}). Nothing is saved until you use it and press Save.</p>
              <p>{suggest.summary}</p>
              <div className="mt-2 flex gap-2"><Button type="button" onClick={() => { set('summary', suggest.summary); setSuggest(null) }}>Use this</Button><Button type="button" variant="ghost" onClick={() => setSuggest(null)}>Dismiss</Button></div>
            </div>)}
        </Panel>

        <Panel title="Career preferences and interests">
          <div className="space-y-5">
            <Select label="Target career" value={f.target_role_id} placeholder="Not chosen yet" options={(roles.data ?? []).map((r) => ({ value: r.id, label: r.name }))} error={errors.target_role_id} onChange={(e) => set('target_role_id', e.target.value)} />
            <div>
              <label htmlFor="interest-input" className="mb-1.5 block text-sm font-medium">Interests</label>
              <div className="flex flex-wrap items-center gap-2 rounded-md border border-line bg-surface p-2 focus-within:border-primary">
                {f.interests.map((i) => (
                  <span key={i} className="inline-flex items-center gap-1 rounded bg-sunken px-2 py-1 text-sm">{i}
                    <button type="button" aria-label={`Remove ${i}`} onClick={() => set('interests', f.interests.filter((x) => x !== i))} className="text-muted hover:text-ink"><X className="h-3.5 w-3.5" /></button></span>))}
                <input id="interest-input" value={tag} onChange={(e) => setTag(e.target.value)} onKeyDown={onTagKey} onBlur={addTag} placeholder={f.interests.length ? '' : 'e.g. Machine learning, Web apps'} className="min-w-40 flex-1 bg-transparent px-1 py-1 text-sm outline-none" />
              </div>
              <p className="mt-1 text-xs text-muted">Press Enter or comma to add. Interests give a small, capped boost to matching careers.</p>
              {errors.interests && <p role="alert" className="mt-1 text-xs font-medium text-danger">{errors.interests}</p>}
            </div>
            <fieldset><legend className="mb-1.5 text-sm font-medium">Looking for</legend>
              <div className="flex flex-wrap gap-x-5 gap-y-2">{WORK_TYPES.map(([v, label]) => (
                <label key={v} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.work_types.includes(v)} className="h-4 w-4 accent-[rgb(var(--c-primary))]"
                  onChange={(e) => set('work_types', e.target.checked ? [...f.work_types, v] : f.work_types.filter((x) => x !== v))} />{label}</label>))}</div>
              {errors.preferences && <p role="alert" className="mt-1 text-xs font-medium text-danger">{errors.preferences}</p>}
            </fieldset>
          </div>
        </Panel>
        <div className="flex justify-end"><Button type="submit" loading={busy}>Save profile</Button></div>
      </form>

      <aside className="space-y-6">
        <Panel title="Completion">
          <p className="mb-1 text-2xl font-bold tabular-nums">{profile.completion.percent}%</p>
          <ProgressBar value={profile.completion.percent} label="Profile completion" />
          {missing.length > 0 && <ul className="mt-4 space-y-1.5 text-sm text-muted">{missing.map((m) => <li key={m.key}>{m.label}</li>)}</ul>}
        </Panel>
      </aside>

      <div className="space-y-6 lg:col-span-2">
        <SkillsManager />
        <SectionManager section="education" items={profile.education as unknown as Item[]} refresh={refresh} />
        <SectionManager section="experience" items={profile.experience as unknown as Item[]} refresh={refresh} />
        <SectionManager section="projects" items={profile.projects as unknown as Item[]} refresh={refresh} />
        <SectionManager section="certifications" items={profile.certifications as unknown as Item[]} refresh={refresh} />
      </div>
    </div>
  )
}

function toForm(p: Profile) {
  return {
    full_name: p.full_name, phone: p.phone ?? '', location: p.location ?? '', summary: p.summary ?? '',
    linkedin_url: p.linkedin_url ?? '', github_url: p.github_url ?? '', portfolio_url: p.portfolio_url ?? '',
    interests: p.interests, work_types: p.preferences.work_types ?? [], target_role_id: p.target_role_id ? String(p.target_role_id) : '',
  }
}
