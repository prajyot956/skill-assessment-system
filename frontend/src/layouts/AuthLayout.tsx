import type { ReactNode } from 'react'
import { Logo } from '../components/Logo'

const STEPS = ['Upload your resume', 'Confirm your profile', 'Take skill assessments', 'See your gaps', 'Follow a roadmap to your career']

export function AuthLayout({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
      <aside className="hidden flex-col justify-between bg-primary p-12 text-primary-ink lg:flex">
        <div className="flex items-center gap-3">
          <span className="grid h-9 w-9 place-items-center rounded-lg bg-primary-ink/15"><Logo className="h-6 w-6" /></span>
          <span className="font-bold">Skill Assessment System</span>
        </div>
        <div>
          <p className="max-w-sm text-3xl font-bold leading-tight tracking-tight">Assess your skills. Understand your potential. Build your career.</p>
          <ol className="mt-10 space-y-3 text-sm">
            {STEPS.map((s, i) => (
              <li key={s} className="flex items-center gap-3">
                <span className="grid h-6 w-6 place-items-center rounded-full border border-primary-ink/40 text-xs font-semibold">{i + 1}</span>{s}
              </li>
            ))}
          </ol>
        </div>
        <p className="text-xs opacity-70">Your resume tells us what you’ve done. Assessments show what you can do.</p>
      </aside>
      <main className="flex items-center justify-center px-5 py-10">
        <div className="w-full max-w-md">
          <div className="mb-8 flex items-center gap-2.5 lg:hidden"><Logo /><span className="font-bold">Skill Assessment System</span></div>
          <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
          {subtitle && <p className="mt-1.5 text-sm text-muted">{subtitle}</p>}
          <div className="mt-7">{children}</div>
        </div>
      </main>
    </div>
  )
}
