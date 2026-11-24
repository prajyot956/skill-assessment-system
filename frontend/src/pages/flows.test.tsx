import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, vi } from 'vitest'
import { AuthProvider } from '../context/AuthContext'
import { ThemeProvider } from '../context/ThemeContext'
import { ToastProvider } from '../context/ToastContext'
import { ApiError, api, http } from '../services/api'
import { ResumePage } from './ResumePage'
import { ResumeReviewPage } from './ResumeReviewPage'
import { AttemptPage } from './AttemptPage'
import { ResultPage } from './ResultPage'
import { CareersPage } from './CareersPage'
import { RoadmapPage } from './RoadmapPage'
import { AssessmentsPage } from './AssessmentsPage'
import type { AttemptData, GapSkill, ResultData, ReviewData, Roadmap, Recommendation } from '../types'

const res = (data: unknown, meta?: Record<string, number>) => Promise.resolve({ data, meta })
const mount = (ui: React.ReactElement, path = '/', route = '*') => render(
  <ThemeProvider><ToastProvider><AuthProvider><MemoryRouter initialEntries={[path]}><Routes><Route path={route} element={ui} /></Routes></MemoryRouter></AuthProvider></ToastProvider></ThemeProvider>)

beforeEach(() => { vi.spyOn(api.auth, 'me').mockRejectedValue(new ApiError('unauthorized', 'x', 401)) })
afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers() })

describe('Resume upload', () => {
  it('rejects wrong type and oversize files without calling the server', async () => {
    vi.spyOn(http, 'get').mockImplementation(() => res({ resume: null, ai_enabled: false }) as never)
    mount(<ResumePage />)
    const input = await screen.findByLabelText('Resume file')
    await userEvent.upload(input, new File(['x'], 'notes.txt', { type: 'text/plain' }), { applyAccept: false })
    expect(await screen.findByText('Choose a PDF or DOCX file.')).toBeInTheDocument()
    await userEvent.upload(input, new File([new Uint8Array(6 * 1024 * 1024)], 'big.pdf', { type: 'application/pdf' }))
    expect(await screen.findByText(/The limit is 5 MB/)).toBeInTheDocument()
  })
  it('says nothing is overwritten and offers review for an existing resume', async () => {
    vi.spyOn(http, 'get').mockImplementation(() => res({ resume: { id: 3, filename: 'cv.pdf', size: 20480, status: 'parsed', parse_method: 'local', error: null, uploaded_at: '2026-01-01T00:00:00', confirmed_at: null, has_draft: true }, ai_enabled: false }) as never)
    mount(<ResumePage />)
    expect(await screen.findByText('cv.pdf')).toBeInTheDocument()
    expect(screen.getByText('Ready to review')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Review and confirm' })).toBeInTheDocument()
    expect(screen.getByText(/Nothing is overwritten automatically/)).toBeInTheDocument()
  })
})

const review: ReviewData = {
  resume: { id: 5, filename: 'cv.pdf', size: 1, status: 'parsed', parse_method: 'local', error: null, uploaded_at: '', confirmed_at: null, has_draft: true },
  draft: {
    personal: {}, summary: null, unmatched_skills: ['Figma'],
    skills: [{ name: 'Python', category: 'Programming', evidence: [{ section: 'skills', snippet: 'Python' }], inferred: false, confidence: 0.95, source_section: 'skills' },
             { name: 'Software Testing', category: 'Software Testing', evidence: [{ section: 'experience', snippet: 'Implied by pytest' }], inferred: true, confidence: 0.4, source_section: 'experience' }],
    analysis: { missing: ['No phone'], strengths: ['1 skill backed by evidence'], improvements: [], explanations: ['Listing a skill is not proof of proficiency.'] },
  },
  diff: {
    personal: [{ field: 'phone', label: 'Phone', current: '111', new: '999', status: 'changed' }, { field: 'location', label: 'Location', current: null, new: 'Pune', status: 'new' }],
    summary: { current: null, new: null, status: 'same' },
    education: { new: [{ degree: 'B.Tech', specialization: null, institution: 'PIT', graduation_year: 2025, details: null }], changed: [], unchanged: 0, missing: [] },
    experience: { new: [], changed: [], unchanged: 0, missing: [] }, certifications: { new: [], changed: [], unchanged: 0, missing: [] },
    projects: { new: [], changed: [{ id: 9, current: { name: 'Tracker', description: 'old', technologies: [], role: null }, item: { name: 'Tracker', description: 'new text', technologies: [], role: null }, changes: [{ field: 'description', current: 'old', new: 'new text' }] }], unchanged: 0, missing: [] },
    skills: { new: [], existing: [], missing: [] },
  },
}
review.diff.skills.new = review.draft.skills

describe('Resume review', () => {
  const open = async () => {
    vi.spyOn(http, 'get').mockImplementation(((url: string) => url.includes('/review') ? res(review) : res({ skills: [{ id: 1, name: 'Python', category: 'Programming' }], categories: ['Programming'] })) as never)
    mount(<ResumeReviewPage />, '/resume/review/5', '/resume/review/:id')
    await screen.findByText('Analysis report')
  }
  it('saves nothing until the user confirms, and sends only what was selected', async () => {
    await open()
    const post = vi.spyOn(http, 'post').mockImplementation(() => res({ applied: {} }) as never)
    expect(post).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button', { name: 'Confirm and update profile' }))
    expect(post).not.toHaveBeenCalled() // a dialog asks first
    await userEvent.click(await screen.findByRole('button', { name: 'Yes, update my profile' }))
    await waitFor(() => expect(post).toHaveBeenCalledTimes(1))
    const [url, body] = post.mock.calls[0] as [string, Record<string, any>]
    expect(url).toBe('/api/resumes/5/confirm')
    expect(body.confirm).toBe(true)
    expect(body.profile).toEqual({ location: 'Pune' })                 // "changed" phone was NOT ticked, so it isn't sent
    expect(body.education.add).toHaveLength(1)
    expect(body.projects.update).toEqual([])                           // changed project not ticked
    expect(body.skills).toEqual([{ name: 'Python' }])                  // inferred skill is not pre-accepted
  })
  it('shows inferred skills as inferred and lets the user accept them', async () => {
    await open()
    expect(screen.getAllByText('Inferred').length).toBeGreaterThan(0)
    expect(screen.getAllByText(/not proof of proficiency|Levels come from assessments/).length).toBeGreaterThan(0)
    expect(screen.getByLabelText('Software Testing')).not.toBeChecked()
    expect(screen.getByLabelText('Python')).toBeChecked()
  })
  it('requires a deliberate choice to update an existing item', async () => {
    await open()
    expect(screen.getByText('Differs from saved')).toBeInTheDocument()
    const box = screen.getAllByRole('checkbox', { name: 'Save this' }).find((b) => !(b as HTMLInputElement).checked)!
    expect(box).not.toBeChecked()
  })
})

const attempt: AttemptData = {
  id: 7, title: 'Python', skill: 'Python', difficulty: 'beginner', duration_seconds: 600, finished: false, status: 'in_progress',
  expires_at: new Date(Date.now() + 600_000).toISOString(), server_now: new Date().toISOString(), answers: {},
  questions: [{ id: 11, text: 'Which keyword defines a function?', type: 'single', marks: 1, topic: 'Functions', options: [{ id: 1, text: 'func' }, { id: 2, text: 'def' }] },
              { id: 12, text: 'Name the built-in length function', type: 'short', marks: 1, topic: 'Built-ins' }],
}

describe('Assessment attempt', () => {
  it('autosaves answers, shows a timer, and never reveals answers', async () => {
    vi.spyOn(http, 'get').mockImplementation(() => res(attempt) as never)
    const put = vi.spyOn(http, 'put').mockImplementation(() => res({ saved: true }) as never)
    mount(<AttemptPage />, '/assessments/attempt/7', '/assessments/attempt/:id')
    await screen.findByText('Which keyword defines a function?')
    await waitFor(() => expect(screen.getByRole('timer')).toHaveTextContent(/^\d+:\d\d$/))
    expect(screen.queryByText(/correct|explanation/i)).not.toBeInTheDocument()
    await userEvent.click(screen.getByLabelText('def'))
    await waitFor(() => expect(put).toHaveBeenCalledWith('/api/assessments/attempts/7/answers', { answers: { '11': 2 } }), { timeout: 3000 })
    expect(await screen.findByText('All answers saved')).toBeInTheDocument()
  })
  it('warns about unanswered questions before submitting', async () => {
    vi.spyOn(http, 'get').mockImplementation(() => res(attempt) as never)
    const post = vi.spyOn(http, 'post').mockImplementation(() => res({}) as never)
    mount(<AttemptPage />, '/assessments/attempt/7', '/assessments/attempt/:id')
    await screen.findByText('Which keyword defines a function?')
    await userEvent.click(screen.getByRole('button', { name: 'Submit' }))
    expect(await screen.findByText(/2 questions are unanswered and will score zero/)).toBeInTheDocument()
    expect(post).not.toHaveBeenCalled()
  })
  it('submits automatically when the server-synced clock runs out', async () => {
    const soon = { ...attempt, server_now: new Date().toISOString(), expires_at: new Date(Date.now() + 1500).toISOString() }  // fresh server time, or the clock offset is stale
    vi.spyOn(http, 'get').mockImplementation(() => res(soon) as never)
    const post = vi.spyOn(http, 'post').mockImplementation(() => res({}) as never)
    mount(<AttemptPage />, '/assessments/attempt/7', '/assessments/attempt/:id')
    await screen.findByText('Which keyword defines a function?')
    await waitFor(() => expect(post).toHaveBeenCalledWith('/api/assessments/attempts/7/submit', expect.anything()), { timeout: 4000 })
  })
})

describe('Assessment catalog', () => {
  it('disables assessments that have no questions', async () => {
    vi.spyOn(http, 'get').mockImplementation(() => res({ ai_enabled: false, categories: [{ id: 1, name: 'Programming', description: null, assessments: [
      { id: 1, title: 'Python', skill: 'Python', available: true, proficiency_pct: null, in_progress_attempt_id: null, questions: { beginner: 5, intermediate: 5, advanced: 3, total: 13 } },
      { id: 2, title: 'Java', skill: 'Java', available: false, proficiency_pct: null, in_progress_attempt_id: null, questions: { beginner: 0, intermediate: 0, advanced: 0, total: 0 } }] }] }) as never)
    mount(<AssessmentsPage />)
    expect(await screen.findByText('Questions coming soon')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Set up Java' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Set up Python' })).toBeEnabled()
  })

  it('offers AI quick questions only when AI is enabled', async () => {
    vi.spyOn(http, 'get').mockImplementation(() => res({ ai_enabled: true, categories: [{ id: 1, name: 'Programming', description: null, assessments: [
      { id: 2, title: 'Java', skill: 'Java', available: false, proficiency_pct: null, in_progress_attempt_id: null, questions: { beginner: 0, intermediate: 0, advanced: 0, total: 0 } }] }] }) as never)
    const post = vi.spyOn(http, 'post').mockImplementation(() => res({ attempt_id: 9 }) as never)
    mount(<AssessmentsPage />)
    expect(await screen.findByText('Quick questions generated by AI')).toBeInTheDocument()
    const button = screen.getByRole('button', { name: 'Set up Java' })
    expect(button).toBeEnabled()
    await userEvent.click(button)
    await waitFor(() => expect(post).toHaveBeenCalledWith('/api/assessments/attempts/ai-generate', {
      assessment_id: 2, difficulty: 'intermediate', num_questions: 5,
    }))
  })
})

describe('Result page', () => {
  it('shows score, correct answers and explanations after submission', async () => {
    const r: ResultData = {
      attempt_id: 7, skill: 'Python', title: 'Python', difficulty: 'beginner', status: 'submitted', submitted_at: '2026-01-01T00:00:00Z', total_marks: 2, obtained_marks: 1, percentage: 50,
      accuracy: 50, performance_category: 'Developing', correct: 1, incorrect: 1, unanswered: 0, strengths: ['Functions'], weaknesses: ['Built-ins'], proficiency_pct: 30,
      topics: [{ name: 'Functions', percentage: 100, correct: 1, count: 1 }, { name: 'Built-ins', percentage: 0, correct: 0, count: 1 }], difficulties: [{ name: 'beginner', percentage: 50, correct: 1, count: 2 }],
      review: [{ id: 12, text: 'Name the built-in length function', type: 'short', topic: 'Built-ins', difficulty: 'beginner', marks: 1, awarded: 0, status: 'incorrect', your_answer: 'size', explanation: 'len(obj) returns the item count.', correct_answer: 'len' }],
    }
    vi.spyOn(http, 'get').mockImplementation(() => res(r) as never)
    mount(<ResultPage />, '/assessments/results/7', '/assessments/results/:id')
    expect(await screen.findByRole('heading', { level: 1, name: /Python results/ })).toBeInTheDocument()
    expect(screen.getAllByText('50%').length).toBeGreaterThan(0)
    expect(screen.getByText('Developing')).toBeInTheDocument()
    expect(screen.getByText('len')).toBeInTheDocument()
    expect(screen.getByText('len(obj) returns the item count.')).toBeInTheDocument()
    expect(screen.getByText(/score × beginner weighting/)).toBeInTheDocument()
  })
})

const gap = (over: Partial<GapSkill>): GapSkill => ({ skill_id: 1, skill: 'HTML', category: 'Web', weight: 3, required_level: 70, is_core: true, state: 'met', evidence_level: 'assessment_verified', proficiency_pct: 80, priority: 'none', assessment_id: 1, assessment_available: true, ...over })
const rec: Recommendation = { role_id: 2, role: 'Frontend Developer', description: 'Builds UIs', match_pct: 42.5, base_pct: 40.7, adjustments: [{ name: 'Interests', points: 1.8, detail: 'You listed web' }], is_target: false,
  why: ['Assessments show you meet the required level in HTML.'], matching_skills: [gap({})], partial_skills: [], unverified_skills: [gap({ skill: 'CSS', state: 'unverified', proficiency_pct: null })], missing_skills: [gap({ skill: 'React', state: 'missing', proficiency_pct: null })], improvement_areas: ['React'], next_steps: ['Learn React (no assessment available yet)'] }

describe('Careers', () => {
  it('shows an honest empty state with no fabricated matches', async () => {
    vi.spyOn(http, 'get').mockImplementation(((u: string) => u.includes('recommendations') ? res({ recommendations: [], target: null, message: 'Confirm skills from your resume, or take an assessment, to get career matches.', ai_enabled: false }) : res([])) as never)
    mount(<CareersPage />)
    expect(await screen.findByText('No matches yet')).toBeInTheDocument()
    expect(screen.queryByText(/%/)).not.toBeInTheDocument()
  })
  it('explains a match using the documented breakdown and sets a target', async () => {
    vi.spyOn(http, 'get').mockImplementation(((u: string) => u.includes('recommendations') ? res({ recommendations: [rec], target: null, message: null, ai_enabled: false }) : u.includes('/gap') ? res({ skills: [gap({})] }) : res([{ id: 2, name: 'Frontend Developer', skill_count: 7 }])) as never)
    const put = vi.spyOn(http, 'put').mockImplementation(() => res({}) as never)
    mount(<CareersPage />)
    expect(await screen.findByText('42.5%')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Why this match?' }))
    expect(await screen.findByText(/Score = 40.7% from your skills \+ 1.8 interests/)).toBeInTheDocument()
    expect(screen.getByText('Learn React (no assessment available yet)')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Set as target' }))
    expect(put).toHaveBeenCalledWith('/api/careers/target', { role_id: 2 })
  })
})

describe('Roadmap', () => {
  const road: Roadmap = { id: 1, role: 'Frontend Developer', role_id: 2, is_stale: true, total: 2, completed: 0, in_progress: 0, pending: 2, progress_pct: 0, generated_at: '',
    items: [{ id: 10, skill: 'CSS', type: 'learn', title: 'Learn CSS: MDN', description: null, priority: 'high', status: 'pending', resource_url: 'https://developer.mozilla.org', assessment_id: null, completed_at: null },
            { id: 11, skill: 'CSS', type: 'assess', title: 'Take the CSS assessment', description: null, priority: 'high', status: 'pending', resource_url: null, assessment_id: 3, completed_at: null }] }
  it('offers to create a roadmap when none exists', async () => {
    vi.spyOn(http, 'get').mockImplementation(((u: string) => u.includes('/roadmap') ? res({ roadmap: null, target_role_id: null, ai_enabled: false }) : res([{ id: 2, name: 'Frontend Developer' }])) as never)
    mount(<RoadmapPage />)
    expect(await screen.findByText('Choose a target career')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Build roadmap' })).toBeDisabled()
  })
  it('flags an out-of-date roadmap and only changes progress when the user acts', async () => {
    vi.spyOn(http, 'get').mockImplementation(((u: string) => u.includes('/roadmap') ? res({ roadmap: road, target_role_id: 2, ai_enabled: false }) : res([])) as never)
    const patch = vi.spyOn(http, 'patch').mockImplementation(() => res({ ...road, is_stale: false, in_progress: 1, pending: 1, items: road.items.map((i) => (i.id === 10 ? { ...i, status: 'in_progress' } : i)) }) as never)
    mount(<RoadmapPage />)
    expect(await screen.findByText(/Your skills or target changed/)).toBeInTheDocument()
    expect(screen.getByRole('progressbar', { name: 'Roadmap progress' })).toHaveAttribute('aria-valuenow', '0')
    expect(patch).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button', { name: 'Start: Learn CSS: MDN' }))
    expect(patch).toHaveBeenCalledWith('/api/roadmap/items/10', { status: 'in_progress' })
    const link = screen.getByRole('link', { name: /Open resource/ })
    expect(link).toHaveAttribute('rel', 'noopener noreferrer')
    expect(within(link.closest('li')!).getByText(/Learn CSS: MDN/)).toBeInTheDocument()
  })
})
