import { useRef, useState, type DragEvent } from 'react'
import { Link } from 'react-router-dom'
import { FileText, Loader2, UploadCloud } from 'lucide-react'
import { Alert, Badge, Button, ConfirmDialog, PageHeader, Panel, ProgressBar, Skeleton } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useToast } from '../context/ToastContext'
import { ApiError, http, uploadResume } from '../services/api'
import type { ResumeInfo } from '../types'

const MAX_MB = 5
const ok = (f: File) => /\.(pdf|docx)$/i.test(f.name)
const kb = (n: number) => (n > 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`)
const STATUS: Record<string, { label: string; tone: 'neutral' | 'good' | 'warn' | 'bad' | 'info' }> = {
  uploaded: { label: 'Uploaded', tone: 'neutral' }, processing: { label: 'Processing', tone: 'info' },
  parsed: { label: 'Ready to review', tone: 'warn' }, confirmed: { label: 'Confirmed', tone: 'good' }, failed: { label: 'Failed', tone: 'bad' },
}

export function ResumePage() {
  const { data, loading, error, reload } = useAsync(() => http.get<{ resume: ResumeInfo | null; ai_enabled: boolean }>('/api/resumes/current').then((r) => r.data))
  const toast = useToast()
  const input = useRef<HTMLInputElement>(null)
  const [drag, setDrag] = useState(false)
  const [progress, setProgress] = useState<number | null>(null)
  const [processing, setProcessing] = useState(false)
  const [problem, setProblem] = useState('')
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [confirmReplace, setConfirmReplace] = useState<File | null>(null)
  const resume = data?.resume ?? null

  const send = async (file: File) => {
    setProblem('')
    if (!ok(file)) return setProblem('Choose a PDF or DOCX file.')
    if (file.size > MAX_MB * 1024 * 1024) return setProblem(`That file is ${kb(file.size)}. The limit is ${MAX_MB} MB.`)
    if (file.size === 0) return setProblem('That file is empty.')
    setProgress(0)
    try {
      await uploadResume(file, (p) => { setProgress(p); if (p >= 100) setProcessing(true) })
      toast.success('Resume analysed. Review what we found.')
      await reload()
    } catch (e) { setProblem(e instanceof ApiError ? e.message : 'Upload failed. Please try again.') }
    finally { setProgress(null); setProcessing(false) }
  }
  const pick = (file?: File) => { if (!file) return; if (resume) setConfirmReplace(file); else void send(file) }
  const onDrop = (e: DragEvent) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files[0]) }
  const remove = async () => {
    try { await http.del(`/api/resumes/${resume!.id}`); toast.success('Resume deleted. Your saved profile is unchanged.'); setConfirmDelete(false); await reload() }
    catch (e) { toast.error(e instanceof ApiError ? e.message : 'Couldn’t delete the resume.') }
  }
  const busy = progress !== null

  return (
    <>
      <PageHeader title="Resume Analyzer" subtitle="Upload your resume. We extract your details and skills, and you decide what gets saved." />
      {loading && !data && <Skeleton className="h-64" />}
      {error && <Alert>{error}</Alert>}
      {data && (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
          <div className="space-y-6">
            <div onDragOver={(e) => { e.preventDefault(); setDrag(true) }} onDragLeave={() => setDrag(false)} onDrop={onDrop}
              className={`rounded-lg border-2 border-dashed p-10 text-center transition-colors ${drag ? 'border-primary bg-primary/5' : 'border-line bg-surface'}`}>
              {busy ? (
                <div className="mx-auto max-w-sm" aria-live="polite">
                  <Loader2 className="mx-auto h-8 w-8 animate-spin text-primary" aria-hidden />
                  <p className="mt-3 text-sm font-medium">{processing ? 'Analysing your resume…' : `Uploading… ${progress}%`}</p>
                  <div className="mt-3"><ProgressBar value={processing ? 100 : progress ?? 0} label="Upload progress" /></div>
                </div>
              ) : (
                <>
                  <UploadCloud className="mx-auto h-9 w-9 text-muted" aria-hidden />
                  <p className="mt-3 font-medium">{resume ? 'Replace your resume' : 'Drag your resume here'}</p>
                  <p className="mt-1 text-sm text-muted">PDF or DOCX, up to {MAX_MB} MB. Text-based files only; scanned images aren’t supported yet.</p>
                  <Button className="mt-5" onClick={() => input.current?.click()}>Choose a file</Button>
                  <input ref={input} type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    className="sr-only" aria-label="Resume file" onChange={(e) => { pick(e.target.files?.[0]); e.target.value = '' }} />
                </>
              )}
            </div>
            {problem && <Alert>{problem}</Alert>}

            {resume && (
              <Panel title="Current resume">
                <div className="flex flex-wrap items-center gap-4">
                  <FileText className="h-8 w-8 text-muted" aria-hidden />
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium">{resume.filename}</p>
                    <p className="text-sm text-muted">{kb(resume.size)} · uploaded {new Date(resume.uploaded_at + 'Z').toLocaleDateString()}
                      {resume.parse_method && ` · read by ${resume.parse_method === 'ai' ? 'AI' : 'built-in parser'}`}</p>
                  </div>
                  <Badge tone={STATUS[resume.status]?.tone}>{STATUS[resume.status]?.label ?? resume.status}</Badge>
                </div>
                {resume.status === 'failed' && <div className="mt-4"><Alert>{resume.error}</Alert></div>}
                <div className="mt-5 flex flex-wrap gap-2">
                  {resume.has_draft && <Link to={`/resume/review/${resume.id}`}><Button>{resume.status === 'confirmed' ? 'Review again' : 'Review and confirm'}</Button></Link>}
                  <Button variant="secondary" onClick={() => setConfirmDelete(true)}>Delete resume</Button>
                </div>
              </Panel>
            )}
          </div>

          <aside className="space-y-6">
            <Panel title="How it works">
              <ol className="space-y-3 text-sm">
                <li><strong>1. We read it.</strong> <span className="text-muted">Contact details, education, experience, projects, certifications and skills.</span></li>
                <li><strong>2. You review it.</strong> <span className="text-muted">Edit anything, accept or reject each skill, and add what’s missing.</span></li>
                <li><strong>3. You confirm.</strong> <span className="text-muted">Only then is your profile updated. Nothing is overwritten automatically.</span></li>
              </ol>
              <p className="mt-4 rounded-md bg-sunken p-3 text-xs text-muted">A skill on your resume is a claim, not proof. Skill levels come only from assessments you take.
                {data.ai_enabled ? ' AI-assisted reading is on for this server.' : ' AI is off, so the built-in parser is used.'}</p>
            </Panel>
          </aside>
        </div>
      )}
      <ConfirmDialog open={confirmDelete} title="Delete this resume?" confirmLabel="Delete" danger onConfirm={remove} onCancel={() => setConfirmDelete(false)}>
        The file and its analysis are removed. Details you already confirmed stay in your profile.
      </ConfirmDialog>
      <ConfirmDialog open={!!confirmReplace} title="Replace your resume?" confirmLabel="Replace and analyse"
        onConfirm={() => { const f = confirmReplace!; setConfirmReplace(null); void send(f) }} onCancel={() => setConfirmReplace(null)}>
        The new resume is compared with your saved profile and you choose what to update. Your saved profile isn’t changed until you confirm.
      </ConfirmDialog>
    </>
  )
}
