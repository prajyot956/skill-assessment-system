import { LayoutDashboard, UserRound, FileSearch, ClipboardCheck, History, ChartColumn, Compass, Route, FolderKanban, Settings, ShieldCheck, type LucideIcon } from 'lucide-react'

export interface NavItem { path: string; label: string; icon: LucideIcon; enabled: boolean; keywords?: string; adminOnly?: boolean }

/** Pages appear in the sidebar and search only once they are built (`enabled`). */
export const NAV_ITEMS: NavItem[] = [
  { path: '/', label: 'Dashboard', icon: LayoutDashboard, enabled: true, keywords: 'home overview' },
  { path: '/profile', label: 'My Profile', icon: UserRound, enabled: true, keywords: 'education skills interests summary' },
  { path: '/resume', label: 'Resume Analyzer', icon: FileSearch, enabled: true, keywords: 'upload cv' },
  { path: '/assessments', label: 'Skill Assessments', icon: ClipboardCheck, enabled: true, keywords: 'test quiz' },
  { path: '/history', label: 'Assessment History', icon: History, enabled: true, keywords: 'results attempts' },
  { path: '/analysis', label: 'Skill Analysis', icon: ChartColumn, enabled: true, keywords: 'gap strengths' },
  { path: '/careers', label: 'Career Recommendations', icon: Compass, enabled: true, keywords: 'jobs roles match' },
  { path: '/roadmap', label: 'Learning Roadmap', icon: Route, enabled: true, keywords: 'plan learn' },
  { path: '/practice', label: 'Projects & Practice', icon: FolderKanban, enabled: true, keywords: 'projects interview' },
  { path: '/admin', label: 'Admin', icon: ShieldCheck, enabled: true, adminOnly: true, keywords: 'users questions roles' },
  { path: '/settings', label: 'Settings', icon: Settings, enabled: true, keywords: 'theme password account' },
]

export const enabledNav = (isAdmin = false) => NAV_ITEMS.filter((n) => n.enabled && (!n.adminOnly || isAdmin))
export const isEnabled = (path: string) => NAV_ITEMS.some((n) => n.path === path && n.enabled)
