import { useEffect, useMemo, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Bell, LogOut, Menu, Moon, Search, Settings, Sun } from 'lucide-react'
import { enabledNav } from '../nav'
import { usePopover } from '../hooks/usePopover'
import { useTheme } from '../context/ThemeContext'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { api } from '../services/api'
import type { AppNotification } from '../types'

function SearchBox() {
  const { user } = useAuth()
  const [q, setQ] = useState('')
  const [focused, setFocused] = useState(false)
  const navigate = useNavigate()
  const results = useMemo(() => {
    const t = q.trim().toLowerCase()
    if (!t) return []
    return enabledNav(!!user?.is_admin).filter((n) => `${n.label} ${n.keywords ?? ''}`.toLowerCase().includes(t))
  }, [q, user])
  const go = (path: string) => { navigate(path); setQ(''); setFocused(false) }
  return (
    <div className="relative w-full max-w-sm">
      <label htmlFor="global-search" className="sr-only">Search pages</label>
      <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" aria-hidden />
      <input id="global-search" value={q} placeholder="Search pages" autoComplete="off"
        onChange={(e) => setQ(e.target.value)} onFocus={() => setFocused(true)}
        onBlur={() => setTimeout(() => setFocused(false), 120)}
        onKeyDown={(e) => { if (e.key === 'Enter' && results[0]) go(results[0].path) }}
        className="h-9 w-full rounded-md border border-line bg-sunken pl-9 pr-3 text-sm placeholder:text-muted focus:border-primary" />
      {focused && q.trim() && (
        <ul className="absolute left-0 right-0 top-11 z-30 overflow-hidden rounded-md border border-line bg-surface shadow-pop">
          {results.length === 0 && <li className="px-3 py-2 text-sm text-muted">No pages match “{q.trim()}”.</li>}
          {results.map((r) => (
            <li key={r.path}>
              <button onMouseDown={() => go(r.path)} className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-sunken">
                <r.icon className="h-4 w-4 text-muted" aria-hidden />{r.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function Notifications() {
  const { open, setOpen, ref } = usePopover()
  const [items, setItems] = useState<AppNotification[]>([])
  const [unread, setUnread] = useState(0)
  const [failed, setFailed] = useState(false)
  const navigate = useNavigate()

  const load = () => api.notifications.list()
    .then((r) => { setItems(r.items); setUnread(r.unread); setFailed(false) })
    .catch(() => setFailed(true))
  useEffect(() => { void load() }, [])

  const markAll = async () => { await api.notifications.readAll().catch(() => undefined); void load() }
  const openOne = async (n: AppNotification) => {
    if (!n.is_read) await api.notifications.read(n.id).catch(() => undefined)
    setOpen(false); void load()
    if (n.link) navigate(n.link)
  }

  return (
    <div className="relative" ref={ref}>
      <button onClick={() => { setOpen(!open); if (!open) void load() }} aria-label={`Notifications${unread ? `, ${unread} unread` : ''}`}
        aria-expanded={open} className="relative grid h-9 w-9 place-items-center rounded-md hover:bg-sunken">
        <Bell className="h-5 w-5" aria-hidden />
        {unread > 0 && <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-attention" />}
      </button>
      {open && (
        <div className="absolute right-0 top-11 z-30 w-80 overflow-hidden rounded-lg border border-line bg-surface shadow-pop">
          <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
            <h2 className="text-sm font-semibold">Notifications</h2>
            {unread > 0 && <button onClick={markAll} className="text-xs font-medium text-primary hover:underline">Mark all read</button>}
          </div>
          <ul className="max-h-80 overflow-auto">
            {failed && <li className="px-4 py-3 text-sm text-danger">Couldn’t load notifications.</li>}
            {!failed && items.length === 0 && <li className="px-4 py-6 text-sm text-muted">You’re all caught up. Updates about your assessments and roadmap will show here.</li>}
            {items.map((n) => (
              <li key={n.id}>
                <button onClick={() => openOne(n)} className="flex w-full gap-3 border-b border-line px-4 py-3 text-left last:border-0 hover:bg-sunken">
                  <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${n.is_read ? 'bg-transparent' : 'bg-attention'}`} />
                  <span><span className="block text-sm font-medium">{n.title}</span>
                    {n.message && <span className="block text-xs text-muted">{n.message}</span>}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function UserMenu() {
  const { user, logout } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()
  const { open, setOpen, ref } = usePopover()
  if (!user) return null
  const initials = user.full_name.split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0]?.toUpperCase()).join('')
  const signOut = async () => {
    try { await logout(); navigate('/login') } catch { toast.error('Couldn’t sign you out. Please try again.') }
  }
  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen(!open)} aria-expanded={open} aria-label="Account menu"
        className="grid h-9 w-9 place-items-center rounded-full bg-primary text-sm font-semibold text-primary-ink">{initials}</button>
      {open && (
        <div className="absolute right-0 top-11 z-30 w-60 overflow-hidden rounded-lg border border-line bg-surface shadow-pop">
          <div className="border-b border-line px-4 py-3">
            <p className="truncate text-sm font-semibold">{user.full_name}</p>
            <p className="truncate text-xs text-muted">{user.email}</p>
          </div>
          <Link to="/settings" onClick={() => setOpen(false)} className="flex items-center gap-2 px-4 py-2.5 text-sm hover:bg-sunken"><Settings className="h-4 w-4" aria-hidden />Settings</Link>
          <button onClick={signOut} className="flex w-full items-center gap-2 px-4 py-2.5 text-left text-sm hover:bg-sunken"><LogOut className="h-4 w-4" aria-hidden />Sign out</button>
        </div>
      )}
    </div>
  )
}

export function TopBar({ onMenu }: { onMenu: () => void }) {
  const { isDark, toggle } = useTheme()
  return (
    <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-line bg-surface/90 px-4 backdrop-blur">
      <button onClick={onMenu} aria-label="Open navigation" className="grid h-9 w-9 place-items-center rounded-md hover:bg-sunken lg:hidden"><Menu className="h-5 w-5" /></button>
      <SearchBox />
      <div className="ml-auto flex items-center gap-1">
        <button onClick={toggle} aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'} className="grid h-9 w-9 place-items-center rounded-md hover:bg-sunken">
          {isDark ? <Sun className="h-5 w-5" aria-hidden /> : <Moon className="h-5 w-5" aria-hidden />}
        </button>
        <Notifications />
        <div className="ml-1"><UserMenu /></div>
      </div>
    </header>
  )
}
