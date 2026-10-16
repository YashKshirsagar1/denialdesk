import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import {
  Activity, BarChart3, Building2, CalendarClock, ClipboardCheck, FileText, FolderOpen, Inbox, LayoutDashboard,
  LogOut, Menu, Receipt, Search, Settings, ShieldCheck, Upload, Users,
} from 'lucide-react'
import { useAuth } from '../auth'
import { getDocumentRequests, getQueueStats } from '../api'
import { initials, ROLE_LABELS } from '../lib/format'

interface NavItem { to: string; label: string; icon: React.ReactNode; end?: boolean; badge?: number }

export function Layout() {
  const { user, signOut, isOps } = useAuth()
  const nav = useNavigate()
  const loc = useLocation()
  const [open, setOpen] = useState(false)
  const [badge, setBadge] = useState(0)
  const [q, setQ] = useState('')

  useEffect(() => setOpen(false), [loc.pathname])

  // Sidebar counters: ops see the review queue, clinics see open document requests.
  useEffect(() => {
    if (!user) return
    let alive = true
    const load = () => {
      const p = isOps
        ? getQueueStats().then((s) => s.awaiting_review)
        : getDocumentRequests().then((r) => r.filter((x) => x.status === 'pending').length)
      p.then((n) => alive && setBadge(n)).catch(() => {})
    }
    load()
    const t = setInterval(load, 30_000)
    return () => { alive = false; clearInterval(t) }
  }, [user, isOps, loc.pathname])

  if (!user) return null
  const role = user.role

  const clinicNav: NavItem[] = [
    { to: '/', label: 'Dashboard', icon: <LayoutDashboard size={18} />, end: true },
    { to: '/claims', label: 'Claims', icon: <FolderOpen size={18} /> },
    { to: '/upload', label: 'Upload denials', icon: <Upload size={18} /> },
    { to: '/requests', label: 'Requests', icon: <Inbox size={18} />, badge: badge },
    { to: '/statements', label: 'Statements', icon: <Receipt size={18} /> },
  ]
  const clinicAdminNav: NavItem[] = [
    { to: '/team', label: 'Team', icon: <Users size={18} /> },
    { to: '/audit', label: 'Access log', icon: <ShieldCheck size={18} /> },
  ]
  const opsNav: NavItem[] = [
    ...(role === 'ops_admin' ? [{ to: '/', label: 'Overview', icon: <LayoutDashboard size={18} />, end: true }] : []),
    { to: '/review', label: 'Review queue', icon: <ClipboardCheck size={18} />, badge },
    { to: '/claims', label: 'All claims', icon: <FolderOpen size={18} /> },
    { to: '/deadlines', label: 'Deadlines', icon: <CalendarClock size={18} /> },
  ]
  const opsAdminNav: NavItem[] = [
    { to: '/practices', label: 'Practices', icon: <Building2 size={18} /> },
    { to: '/analytics', label: 'Analytics', icon: <BarChart3 size={18} /> },
    { to: '/statements', label: 'Billing', icon: <Receipt size={18} /> },
    { to: '/team', label: 'Users', icon: <Users size={18} /> },
    { to: '/audit', label: 'Access log', icon: <ShieldCheck size={18} /> },
  ]

  const sections: { title: string; items: NavItem[] }[] = isOps
    ? [
        { title: 'Work', items: opsNav },
        ...(role === 'ops_admin' ? [{ title: 'Manage', items: opsAdminNav }] : []),
      ]
    : [
        { title: 'Recover', items: clinicNav },
        ...(role === 'clinic_admin' ? [{ title: 'Practice', items: clinicAdminNav }] : []),
      ]

  return (
    <div className="app">
      <aside className={`sidebar${open ? ' open' : ''}`}>
        <div className="brand">
          <span className="brand-mark"><Activity size={18} /></span>
          DenialDesk
        </div>
        <nav className="nav" aria-label="Main">
          {sections.map((s) => (
            <div key={s.title}>
              <div className="nav-section">{s.title}</div>
              {s.items.map((i) => (
                <NavLink key={i.to} to={i.to} end={i.end} className={({ isActive }) => (isActive ? 'active' : '')}>
                  {i.icon}
                  {i.label}
                  {!!i.badge && <span className="count">{i.badge}</span>}
                </NavLink>
              ))}
            </div>
          ))}
          <div className="nav-section">Account</div>
          <NavLink to="/settings" className={({ isActive }) => (isActive ? 'active' : '')}>
            <Settings size={18} /> Settings
          </NavLink>
        </nav>
        <div className="sidebar-foot">
          <div className="avatar">{initials(user.full_name || user.email)}</div>
          <div className="who">
            <div className="n">{user.full_name || user.email}</div>
            <div className="r">{ROLE_LABELS[user.role]}</div>
          </div>
          <button className="icon-btn" onClick={() => signOut()} title="Sign out" aria-label="Sign out"><LogOut size={17} /></button>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <button className="menu-btn" onClick={() => setOpen((o) => !o)} aria-label="Menu"><Menu size={22} /></button>
          <div className="practice">
            <FileText size={17} color="var(--blue-600)" />
            {user.practice_name ?? 'DenialDesk Operations'}
          </div>
          <div className="spacer" />
          <form
            className="search"
            onSubmit={(e) => { e.preventDefault(); nav(`/claims?q=${encodeURIComponent(q)}`) }}
          >
            <Search size={16} />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search claims, patients, payers…" aria-label="Search claims" />
          </form>
        </header>
        <main className="content"><Outlet /></main>
      </div>
    </div>
  )
}
