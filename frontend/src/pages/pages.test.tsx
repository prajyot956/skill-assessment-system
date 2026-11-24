import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, vi } from 'vitest'
import { AuthProvider } from '../context/AuthContext'
import { ThemeProvider } from '../context/ThemeContext'
import { ToastProvider } from '../context/ToastContext'
import { DashboardPage } from './DashboardPage'
import { LoginPage, RegisterPage } from './AuthPages'
import { enabledNav } from '../nav'
import { api, ApiError } from '../services/api'
import type { Dashboard } from '../types'

const wrap = (ui: React.ReactElement) => render(
  <ThemeProvider><ToastProvider><AuthProvider><MemoryRouter>{ui}</MemoryRouter></AuthProvider></ToastProvider></ThemeProvider>)

afterEach(() => vi.restoreAllMocks())

describe('auth forms', () => {
  it('shows validation messages and does not call the API on an empty login', async () => {
    vi.spyOn(api.auth, 'me').mockRejectedValue(new ApiError('unauthorized', 'Please sign in to continue.', 401))
    const login = vi.spyOn(api.auth, 'login')
    wrap(<LoginPage />)
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByText('Enter a valid email address.')).toBeInTheDocument()
    expect(screen.getByText('Enter your password.')).toBeInTheDocument()
    expect(login).not.toHaveBeenCalled()
  })

  it('blocks registration when passwords differ', async () => {
    vi.spyOn(api.auth, 'me').mockRejectedValue(new ApiError('unauthorized', 'Please sign in to continue.', 401))
    const register = vi.spyOn(api.auth, 'register')
    wrap(<RegisterPage />)
    await userEvent.type(screen.getByLabelText('Full name'), 'Ana Rao')
    await userEvent.type(screen.getByLabelText('Email'), 'ana@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'Str0ngPass1')
    await userEvent.type(screen.getByLabelText('Confirm password'), 'Different1')
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }))
    expect(await screen.findByText('Passwords do not match.')).toBeInTheDocument()
    expect(register).not.toHaveBeenCalled()
  })
})

describe('dashboard', () => {
  const empty: Dashboard = {
    profile: { completion: { percent: 0, items: [{ key: 'phone', label: 'Add a phone number', done: false }] }, resume_status: 'not_uploaded', confirmed_skills: 0 },
    assessments: { completed: 0, pending: 0, average_score: null, recent: [] },
    skills: { strongest: [], weakest: [], unassessed: [] },
    career: { target_role_id: null, top_matches: [] }, learning: null, activity: [],
  }
  it('shows empty states and no invented numbers for a new user', async () => {
    vi.spyOn(api.auth, 'me').mockResolvedValue({ id: 1, full_name: 'Ana Rao', email: 'a@b.com', is_admin: false, created_at: '' })
    vi.spyOn(api.dashboard, 'get').mockResolvedValue(empty)
    wrap(<DashboardPage />)
    await waitFor(() => expect(screen.getByText('No assessments taken')).toBeInTheDocument())
    expect(screen.getByText('No skills yet')).toBeInTheDocument()
    expect(screen.getByText('No career matches yet')).toBeInTheDocument()
    expect(screen.getByText('—')).toBeInTheDocument() // average score is unknown, not 0
    expect(screen.getByText('Not uploaded')).toBeInTheDocument()
  })
  it('shows an error with a retry when the API fails', async () => {
    vi.spyOn(api.auth, 'me').mockResolvedValue({ id: 1, full_name: 'Ana Rao', email: 'a@b.com', is_admin: false, created_at: '' })
    vi.spyOn(api.dashboard, 'get').mockRejectedValue(new Error('boom'))
    wrap(<DashboardPage />)
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })
})

describe('navigation', () => {
  it('lists the ten learner pages, and Admin only for admins', () => {
    const user = enabledNav(false).map((n) => n.path)
    expect(user).toEqual(['/', '/profile', '/resume', '/assessments', '/history', '/analysis', '/careers', '/roadmap', '/practice', '/settings'])
    expect(enabledNav(true).map((n) => n.path)).toContain('/admin')
    expect(user).not.toContain('/admin')
  })
})
