import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ChevronDown, Plus, X } from 'lucide-react'
import { Alert, Badge, Button, ConfirmDialog, Input, PageHeader, Panel, Select, Skeleton, Textarea } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useToast } from '../context/ToastContext'
import { ApiError, http } from '../services/api'
import type { Draft, DraftSkill, ReviewData, SectionDiff } from '../types'

import { FIELDS, REQUIRED as required, SECTION_LABEL, type Field, type Section } from '../utils/sections'
interface Row<T> { selected: boolean; item: T; id?: number; changes?: { field: string; current: unknown; new: unknown }[] }

function toRows<T>(d: SectionDiff<T>): { fresh: Row<T>[]; changed: Row<T>[] } {
  return {
    fresh: d.new.map((item) => ({ selected: true, item: { ...item } })),
    // changed items start unticked: updating something already saved must be a deliberate choice
    changed: d.changed.map((c) => ({ selected: false, item: { ...c.item }, id: c.id, changes: c.changes })),
  }
}

function ItemEditor<T extends object>({ fields, row, onChange, onRemove, badge }: { fields: Field[]; row: Row<T>; onChange: (r: Row<T>) => void; onRemove?: () => void; badge: React.ReactNode }) {
  const get = (k: string) => (row.item as Record<string, unknown>)[k]
  const set = (k: string, v: unknown) => onChange({ ...row, item: { ...row.item, [k]: v } })
  return (
    <div className={`rounded-md border p-4 ${row.selected ? 'border-primary/50 bg-primary/5' : 'border-line'}`}>
      <div className="mb-3 flex items-center gap-3">
        <label className="flex items-center gap-2 text-sm font-medium"><input type="checkbox" checked={row.selected} onChange={(e) => onChange({ ...row, selected: e.target.checked })} className="h-4 w-4 accent-[rgb(var(--c-primary))]" />Save this</label>
        {badge}
        {onRemove && <button type="button" onClick={onRemove} aria-label="Remove this item" className="ml-auto text-muted hover:text-danger"><X className="h-4 w-4" /></button>}
      </div>
      {row.changes && (
        <ul className="mb-3 space-y-1 rounded bg-sunken p-2 text-xs">
          {row.changes.map((c) => <li key={c.field}><strong>{c.field.replace('_', ' ')}:</strong> <span className="text-muted line-through">{String(c.current ?? 'empty')}</span> → {Array.isArray(c.new) ? c.new.join(', ') : String(c.new)}</li>)}
        </ul>
      )}
      <div className="grid gap-3 sm:grid-cols-2">
        {fields.map((f) => {
          const v = get(f.key)
          const wide = f.wide ? 'sm:col-span-2' : ''
          if (f.kind === 'area') return <div key={f.key} className={wide}><Textarea label={f.label} value={(v as string) ?? ''} onChange={(e) => set(f.key, e.target.value)} className="min-h-20" /></div>
          if (f.kind === 'choice') return <div key={f.key} className={wide}><Select label={f.label} value={(v as string) ?? f.choices![0]} options={f.choices!.map((c) => ({ value: c, label: c }))} onChange={(e) => set(f.key, e.target.value)} /></div>
          if (f.kind === 'list') return <div key={f.key} className={wide}><Input label={f.label} value={((v as string[]) ?? []).join(', ')} onChange={(e) => set(f.key, e.target.value.split(',').map((x) => x.trim()).filter(Boolean))} /></div>
          return <div key={f.key} className={wide}><Input label={f.label} type={f.kind === 'number' ? 'number' : 'text'} value={(v as string | number) ?? ''}
            onChange={(e) => set(f.key, f.kind === 'number' ? (e.target.value ? Number(e.target.value) : null) : e.target.value)} /></div>
        })}
      </div>
    </div>
  )
}

interface SkillRow { skill: DraftSkill; accepted: boolean; existing: boolean }

export function ResumeReviewPage() {
  const { id } = useParams()
  const { data, error, loading } = useAsync<ReviewData>(() => http.get<ReviewData>(`/api/resumes/${id}/review`).then((r) => r.data))
  return (
    <>
      <PageHeader title="Review your resume" subtitle="Check what we found. Nothing is saved until you confirm." action={<Link to="/resume" className="text-sm font-medium text-primary hover:underline">Back to upload</Link>} />
      {loading && <div className="space-y-4"><Skeleton className="h-32" /><Skeleton className="h-64" /></div>}
      {error && <Alert>{error}</Alert>}
      {data && <ReviewForm data={data} resumeId={Number(id)} />}
    </>
  )
}

function ReviewForm({ data, resumeId }: { data: ReviewData; resumeId: number }) {
  const { draft, diff } = data
  const toast = useToast()
  const navigate = useNavigate()
  const taxonomy = useAsync(() => http.get<{ skills: { id: number; name: string; category: string }[]; categories: string[] }>('/api/skills').then((r) => r.data))
  const [personal, setPersonal] = useState(() => diff.personal.map((p) => ({ ...p, selected: p.status === 'new', value: p.new ?? '' })))
  const [summary, setSummary] = useState({ selected: diff.summary.status === 'new', value: diff.summary.new ?? '' })
  const [rows, setRows] = useState(() => Object.fromEntries((Object.keys(FIELDS) as Section[]).map((s) => [s, toRows(diff[s] as SectionDiff<object>)])) as Record<Section, { fresh: Row<object>[]; changed: Row<object>[] }>)
  const [skills, setSkills] = useState<SkillRow[]>(() => [
    ...diff.skills.new.map((s) => ({ skill: s, accepted: !s.inferred && s.confidence >= 0.6, existing: false })),
    ...diff.skills.existing.map((s) => ({ skill: s, accepted: false, existing: true })),
  ])
  const [manual, setManual] = useState<{ name: string; category: string }[]>([])
  const [mName, setMName] = useState('')
  const [mCat, setMCat] = useState('')
  const [open, setOpen] = useState<string | null>(null)
  const [confirm, setConfirm] = useState(false)
  const [busy, setBusy] = useState(false)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const known = useMemo(() => new Map((taxonomy.data?.skills ?? []).map((s) => [s.name.toLowerCase(), s])), [taxonomy.data])
  useEffect(() => { setErrors({}) }, [rows])

  const chosenSkills = [...skills.filter((s) => s.accepted).map((s) => ({ name: s.skill.name })), ...manual]
  const counts = {
    profile: personal.filter((p) => p.selected && p.value).length + (summary.selected && summary.value ? 1 : 0),
    items: (Object.keys(FIELDS) as Section[]).reduce((n, s) => n + rows[s].fresh.filter((r) => r.selected).length + rows[s].changed.filter((r) => r.selected).length, 0),
    skills: chosenSkills.length,
  }

  const addManual = () => {
    const name = mName.trim()
    if (!name) return
    const k = known.get(name.toLowerCase())
    if (!k && !mCat) return setErrors({ manual: 'This skill is new. Choose a category for it.' })
    if (chosenSkills.some((s) => s.name.toLowerCase() === name.toLowerCase())) return setErrors({ manual: 'Already added.' })
    setManual([...manual, { name: k?.name ?? name, ...(k ? {} : { category: mCat }) } as { name: string; category: string }])
    setMName(''); setMCat(''); setErrors({})
  }

  const submit = async () => {
    const body: Record<string, unknown> = { confirm: true, profile: {}, skills: chosenSkills }
    const prof = body.profile as Record<string, string>
    for (const p of personal) if (p.selected && p.value) prof[p.field] = p.value
    if (summary.selected && summary.value) prof.summary = summary.value
    for (const s of Object.keys(FIELDS) as Section[]) {
      body[s] = { add: rows[s].fresh.filter((r) => r.selected).map((r) => r.item),
                  update: rows[s].changed.filter((r) => r.selected).map((r) => ({ id: r.id, ...r.item })) }
    }
    setBusy(true)
    try {
      await http.post(`/api/resumes/${resumeId}/confirm`, body)
      toast.success('Profile updated.')
      navigate('/profile')
    } catch (e) {
      setConfirm(false)
      if (e instanceof ApiError && Object.keys(e.fields).length) { setErrors(e.fields); toast.error('Some items need fixing before they can be saved.') }
      else toast.error(e instanceof ApiError ? e.message : 'Couldn’t save. Please try again.')
    } finally { setBusy(false) }
  }

  const byCat = skills.reduce<Record<string, SkillRow[]>>((a, s) => { (a[s.skill.category] ??= []).push(s); return a }, {})
  const a: Draft['analysis'] = draft.analysis
  const itemErrors = Object.entries(errors).filter(([k]) => k !== 'manual')

  return (
    <div className="space-y-6">
      <Panel title="Analysis report">
        <div className="grid gap-6 md:grid-cols-3">
          <div><h3 className="mb-2 text-sm font-semibold text-success">Strengths</h3>{a.strengths.length ? <ul className="space-y-1.5 text-sm">{a.strengths.map((x) => <li key={x}>{x}</li>)}</ul> : <p className="text-sm text-muted">None detected yet.</p>}</div>
          <div><h3 className="mb-2 text-sm font-semibold text-attention">Could be improved</h3>{a.improvements.length ? <ul className="space-y-1.5 text-sm">{a.improvements.map((x) => <li key={x}>{x}</li>)}</ul> : <p className="text-sm text-muted">Nothing flagged.</p>}</div>
          <div><h3 className="mb-2 text-sm font-semibold">Missing or incomplete</h3>{a.missing.length ? <ul className="space-y-1.5 text-sm">{a.missing.map((x) => <li key={x}>{x}</li>)}</ul> : <p className="text-sm text-muted">Nothing missing.</p>}</div>
        </div>
        <details className="mt-5 text-sm"><summary className="cursor-pointer font-medium">How we read your resume</summary>
          <ul className="mt-2 space-y-1.5 text-muted">{a.explanations.map((x) => <li key={x}>{x}</li>)}</ul></details>
      </Panel>

      {itemErrors.length > 0 && <Alert>Fix these before saving: {itemErrors.map(([k, m]) => `${k.replace(/\./g, ' ')}: ${m}`).join('; ')}</Alert>}

      <Panel title="Contact and summary">
        <div className="space-y-4">
          {personal.filter((p) => p.status !== 'same' || p.current).map((p) => (
            <div key={p.field} className="grid items-start gap-3 sm:grid-cols-[auto_minmax(0,1fr)]">
              <label className="flex items-center gap-2 pt-8 text-sm"><input type="checkbox" checked={p.selected} disabled={!p.new && !p.value}
                onChange={(e) => setPersonal(personal.map((x, j) => (j === personal.indexOf(p) ? { ...x, selected: e.target.checked } : x)))} className="h-4 w-4 accent-[rgb(var(--c-primary))]" /><span className="sr-only">Save {p.label}</span></label>
              <div>
                <Input label={`${p.label}${p.status === 'changed' ? ' (differs from saved)' : p.status === 'same' ? ' (already saved)' : ''}`} value={p.value}
                  onChange={(e) => setPersonal(personal.map((x, j) => (j === personal.indexOf(p) ? { ...x, value: e.target.value, selected: true } : x)))} error={errors[`profile.${p.field}`]} />
                {p.status === 'changed' && <p className="mt-1 text-xs text-muted">Saved now: {p.current}</p>}
              </div>
            </div>
          ))}
          <div className="grid items-start gap-3 sm:grid-cols-[auto_minmax(0,1fr)]">
            <label className="flex items-center gap-2 pt-8 text-sm"><input type="checkbox" checked={summary.selected} onChange={(e) => setSummary({ ...summary, selected: e.target.checked })} className="h-4 w-4 accent-[rgb(var(--c-primary))]" /><span className="sr-only">Save summary</span></label>
            <div><Textarea label={`Professional summary${diff.summary.status === 'changed' ? ' (differs from saved)' : ''}`} value={summary.value} onChange={(e) => setSummary({ selected: true, value: e.target.value })} />
              {diff.summary.status === 'changed' && <p className="mt-1 text-xs text-muted">Saved now: {diff.summary.current}</p>}</div>
          </div>
        </div>
      </Panel>

      {(Object.keys(FIELDS) as Section[]).map((s) => {
        const r = rows[s]; const d = diff[s]
        const set = (kind: 'fresh' | 'changed', i: number, nr: Row<object>) => setRows({ ...rows, [s]: { ...r, [kind]: r[kind].map((x, j) => (j === i ? nr : x)) } })
        const empty = !r.fresh.length && !r.changed.length
        return (
          <Panel key={s} title={SECTION_LABEL[s]} action={d.unchanged > 0 ? <span className="text-xs text-muted">{d.unchanged} already saved</span> : undefined}>
            <div className="space-y-4">
              {empty && <p className="text-sm text-muted">{d.unchanged ? 'Everything found is already in your profile.' : `No ${SECTION_LABEL[s].toLowerCase()} found. You can add them on your profile page.`}</p>}
              {r.fresh.map((row, i) => <ItemEditor key={`n${i}`} fields={FIELDS[s]} row={row} badge={<Badge tone="good">New</Badge>} onChange={(nr) => set('fresh', i, nr)}
                onRemove={() => setRows({ ...rows, [s]: { ...r, fresh: r.fresh.filter((_, j) => j !== i) } })} />)}
              {r.changed.map((row, i) => <ItemEditor key={`c${i}`} fields={FIELDS[s]} row={row} badge={<Badge tone="warn">Differs from saved</Badge>} onChange={(nr) => set('changed', i, nr)} />)}
              {d.missing.length > 0 && <p className="text-xs text-muted">In your profile but not in this resume (kept as is): {d.missing.map((m) => (m as unknown as Record<string, string>)[required[s]]).join(', ')}</p>}
            </div>
          </Panel>
        )
      })}

      <Panel title="Skills">
        <p className="mb-4 text-sm text-muted">Tick the skills that are really yours. A tick means “I have this skill”, not “I’m proficient”. Levels come from assessments.</p>
        {Object.entries(byCat).map(([cat, list]) => (
          <div key={cat} className="mb-5">
            <h3 className="mb-2 text-sm font-semibold">{cat}</h3>
            <ul className="divide-y divide-line rounded-md border border-line">
              {list.map((row) => {
                const k = row.skill.name
                return (
                  <li key={k} className="px-3 py-2.5">
                    <div className="flex flex-wrap items-center gap-3">
                      <label className="flex min-w-0 flex-1 items-center gap-2 text-sm font-medium">
                        <input type="checkbox" checked={row.accepted} onChange={(e) => setSkills(skills.map((s) => (s === row ? { ...s, accepted: e.target.checked } : s)))} className="h-4 w-4 accent-[rgb(var(--c-primary))]" />{k}</label>
                      {row.existing && <Badge>Already in profile · adds evidence</Badge>}
                      <Badge tone={row.skill.inferred ? 'warn' : 'info'}>{row.skill.inferred ? 'Inferred' : 'Stated'}</Badge>
                      <span className="text-xs text-muted">from {row.skill.source_section} · {Math.round(row.skill.confidence * 100)}% confidence</span>
                      <button type="button" onClick={() => setOpen(open === k ? null : k)} aria-expanded={open === k} aria-label={`Evidence for ${k}`} className="text-muted hover:text-ink"><ChevronDown className={`h-4 w-4 ${open === k ? 'rotate-180' : ''}`} /></button>
                    </div>
                    {open === k && <ul className="mt-2 space-y-1 rounded bg-sunken p-2 text-xs text-muted">{row.skill.evidence.map((e, i) => <li key={i}><strong>{e.section}:</strong> {e.snippet}</li>)}</ul>}
                  </li>
                )
              })}
            </ul>
          </div>
        ))}
        {skills.length === 0 && <p className="mb-4 text-sm text-muted">No skills were recognised. Add yours below.</p>}
        {diff.skills.missing.length > 0 && <p className="mb-4 text-xs text-muted">Confirmed earlier but not on this resume (kept as is): {diff.skills.missing.join(', ')}</p>}

        <div className="rounded-md border border-line p-4">
          <h3 className="mb-3 text-sm font-semibold">Add a skill yourself</h3>
          {draft.unmatched_skills.length > 0 && (
            <div className="mb-3 flex flex-wrap items-center gap-2 text-xs"><span className="text-muted">Not recognised on your resume:</span>
              {draft.unmatched_skills.map((u) => <button key={u} type="button" onClick={() => setMName(u)} className="rounded bg-sunken px-2 py-1 hover:bg-line">{u}</button>)}</div>
          )}
          <div className="grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
            <Input label="Skill name" list="skill-names" value={mName} onChange={(e) => setMName(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addManual() } }} />
            <datalist id="skill-names">{(taxonomy.data?.skills ?? []).map((s) => <option key={s.id} value={s.name} />)}</datalist>
            <Select label="Category (new skills only)" value={mCat} placeholder="Choose…" disabled={known.has(mName.trim().toLowerCase())}
              options={(taxonomy.data?.categories ?? []).map((c) => ({ value: c, label: c }))} onChange={(e) => setMCat(e.target.value)} />
            <Button type="button" variant="secondary" onClick={addManual}><Plus className="h-4 w-4" />Add</Button>
          </div>
          {errors.manual && <p role="alert" className="mt-2 text-xs font-medium text-danger">{errors.manual}</p>}
          {manual.length > 0 && <div className="mt-3 flex flex-wrap gap-2">{manual.map((m) => (
            <span key={m.name} className="inline-flex items-center gap-1 rounded bg-primary/15 px-2 py-1 text-sm">{m.name}
              <button type="button" aria-label={`Remove ${m.name}`} onClick={() => setManual(manual.filter((x) => x !== m))}><X className="h-3.5 w-3.5" /></button></span>))}</div>}
        </div>
      </Panel>

      <div className="sticky bottom-0 -mx-4 flex flex-wrap items-center justify-between gap-3 border-t border-line bg-surface/95 px-4 py-3 backdrop-blur sm:-mx-6 sm:px-6">
        <p className="text-sm text-muted">Ready to save: <strong className="text-ink">{counts.profile}</strong> profile fields, <strong className="text-ink">{counts.items}</strong> entries, <strong className="text-ink">{counts.skills}</strong> skills</p>
        <div className="flex gap-2"><Link to="/resume"><Button variant="secondary">Discard</Button></Link>
          <Button onClick={() => setConfirm(true)} disabled={counts.profile + counts.items + counts.skills === 0}>Confirm and update profile</Button></div>
      </div>
      <ConfirmDialog open={confirm} title="Update your profile?" confirmLabel="Yes, update my profile" busy={busy} onConfirm={submit} onCancel={() => setConfirm(false)}>
        This saves {counts.profile} profile fields, {counts.items} entries and {counts.skills} skills. Anything you left unticked is not saved, and existing details you didn’t select stay exactly as they are.
      </ConfirmDialog>
    </div>
  )
}
