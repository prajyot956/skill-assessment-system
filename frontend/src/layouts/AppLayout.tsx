import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { X } from 'lucide-react'
import { Logo } from '../components/Logo'
import { TopBar } from '../components/TopBar'
import { enabledNav } from '../nav'
import { useAuth } from '../context/AuthContext'

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { user } = useAuth()
  return (
    <nav aria-label="Main" className="flex h-full flex-col gap-1 p-3">
      <div className="mb-3 flex items-center gap-2.5 px-2 py-2">
        <Logo />
        <span className="text-sm font-bold leading-tight">Skill Assessment<br />System</span>
      </div>
      {enabledNav(!!user?.is_admin).map(({ path, label, icon: Icon }) => (
        <NavLink key={path} to={path} end={path === '/'} onClick={onNavigate}
          className={({ isActive }) => `flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
            isActive ? 'bg-primary/12 text-primary' : 'text-muted hover:bg-sunken hover:text-ink'}`}>
          <Icon className="h-[18px] w-[18px]" aria-hidden />{label}
        </NavLink>
      ))}
    </nav>
  )
}

export function AppLayout() {
  const [drawer, setDrawer] = useState(false)
  const { pathname } = useLocation()
  useEffect(() => { setDrawer(false); window.scrollTo(0, 0) }, [pathname])

  return (
    <div className="min-h-screen lg:pl-64">
      <aside className="fixed inset-y-0 left-0 hidden w-64 border-r border-line bg-surface lg:block"><Sidebar /></aside>
      {drawer && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
          <div className="absolute inset-0 bg-black/40" onClick={() => setDrawer(false)} />
          <aside className="absolute inset-y-0 left-0 w-64 bg-surface shadow-pop">
            <button onClick={() => setDrawer(false)} aria-label="Close navigation" className="absolute right-2 top-3 grid h-8 w-8 place-items-center rounded-md hover:bg-sunken"><X className="h-4 w-4" /></button>
            <Sidebar onNavigate={() => setDrawer(false)} />
          </aside>
        </div>
      )}
      <TopBar onMenu={() => setDrawer(true)} />
      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6"><Outlet /></main>
    </div>
  )
}
