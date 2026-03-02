import { useEffect, useMemo, useState } from 'react'
import { NavLink } from 'react-router-dom'
import {
  PenTool, Image, Video, Database, MessageSquare, Scale,
  Lock, LayoutDashboard, Brain, Sparkles, PanelLeftClose, PanelLeft,
  ChevronRight,
} from 'lucide-react'
import { getMe } from '../services/api'
import { cn } from '../lib/utils'

const ROLE_CACHE_KEY = 'iccp:user-role'
const SIDEBAR_COLLAPSED_KEY = 'iccp:sidebar-collapsed'

function Sidebar() {
  const [role, setRole] = useState(() => {
    try { return localStorage.getItem(ROLE_CACHE_KEY) || 'user' } catch { return 'user' }
  })
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === 'true' } catch { return false }
  })

  useEffect(() => {
    let mounted = true
    ;(async () => {
      try {
        const resp = await getMe()
        if (mounted) {
          const latestRole = resp?.user?.role || 'user'
          setRole(latestRole)
          localStorage.setItem(ROLE_CACHE_KEY, latestRole)
        }
      } catch {
        if (mounted) {
          setRole('user')
          localStorage.removeItem(ROLE_CACHE_KEY)
        }
      }
    })()
    return () => { mounted = false }
  }, [])

  const toggleCollapse = () => {
    setCollapsed((prev) => {
      const next = !prev
      localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(next))
      window.dispatchEvent(new Event('sidebar-toggle'))
      return next
    })
  }

  const menuGroups = useMemo(() => [
    {
      title: 'AI 创作',
      items: [
        { path: '/chat', label: '对话', icon: MessageSquare },
        { path: '/writing', label: '写作', icon: PenTool },
        { path: '/cover', label: '封面', icon: Image },
        { path: '/video', label: '视频', icon: Video },
      ],
    },
    {
      title: '数据',
      items: [
        { path: '/knowledge', label: '知识库', icon: Database },
      ],
    },
    {
      title: '管理',
      items: [
        { path: '/model-compare', label: '模型对比', icon: Scale, adminOnly: true },
        { path: '/memory', label: '记忆调试', icon: Brain, adminOnly: true },
        { path: '/auth', label: '认证', icon: Lock },
      ],
    },
  ], [])

  const visibleGroups = useMemo(
    () => menuGroups
      .map((group) => ({
        ...group,
        items: group.items.filter((item) => !item.adminOnly || role === 'admin'),
      }))
      .filter((group) => group.items.length > 0),
    [menuGroups, role],
  )

  return (
    <aside
      className={cn(
        'bg-card border-r flex flex-col h-screen fixed left-0 top-0 z-50 transition-all duration-200',
        collapsed ? 'w-[60px]' : 'w-52'
      )}
    >
      {/* Logo */}
      <div className={cn('border-b flex items-center', collapsed ? 'px-3 py-4 justify-center' : 'px-4 py-4 gap-2.5')}>
        <NavLink to="/dashboard" className="flex items-center gap-2.5 min-w-0">
          <div className="bg-primary p-1.5 rounded-md shrink-0">
            <Sparkles className="w-4 h-4 text-primary-foreground" />
          </div>
          {!collapsed && (
            <span className="text-base font-bold text-foreground tracking-wide truncate">ICCP</span>
          )}
        </NavLink>
      </div>

      {/* Dashboard link */}
      <div className={cn('px-2 pt-3', collapsed ? 'px-1.5' : '')}>
        <NavLink
          to="/dashboard"
          className={({ isActive }) =>
            cn(
              'flex items-center gap-2.5 rounded-md text-sm transition-colors',
              collapsed ? 'justify-center p-2.5' : 'px-3 py-2',
              isActive
                ? 'bg-primary text-primary-foreground font-medium'
                : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
            )
          }
          title={collapsed ? '总览' : undefined}
        >
          <LayoutDashboard className="w-4 h-4 shrink-0" />
          {!collapsed && <span>总览</span>}
        </NavLink>
      </div>

      {/* Nav groups */}
      <nav className={cn('flex-1 overflow-y-auto py-3', collapsed ? 'px-1.5' : 'px-2')}>
        {visibleGroups.map((group) => (
          <div key={group.title} className="mb-4">
            {!collapsed && (
              <p className="px-3 mb-1.5 text-[10px] uppercase tracking-widest text-muted-foreground font-medium">
                {group.title}
              </p>
            )}
            {collapsed && <div className="border-t mx-2 mb-2" />}
            <div className="space-y-0.5">
              {group.items.map((item) => {
                const Icon = item.icon
                return (
                  <NavLink
                    key={item.path}
                    to={item.path}
                    title={collapsed ? item.label : undefined}
                    className={({ isActive }) =>
                      cn(
                        'flex items-center rounded-md text-sm transition-colors',
                        collapsed ? 'justify-center p-2.5' : 'gap-2.5 px-3 py-2',
                        isActive
                          ? 'bg-accent text-accent-foreground font-medium'
                          : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
                      )
                    }
                  >
                    <Icon className="w-4 h-4 shrink-0" />
                    {!collapsed && <span>{item.label}</span>}
                  </NavLink>
                )
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Collapse toggle */}
      <div className="border-t p-2">
        <button
          type="button"
          onClick={toggleCollapse}
          className={cn(
            'w-full flex items-center gap-2 rounded-md text-sm text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors',
            collapsed ? 'justify-center p-2.5' : 'px-3 py-2'
          )}
          title={collapsed ? '展开侧边栏' : '收起侧边栏'}
        >
          {collapsed ? <PanelLeft className="w-4 h-4" /> : <PanelLeftClose className="w-4 h-4" />}
          {!collapsed && <span>收起侧边栏</span>}
        </button>
      </div>
    </aside>
  )
}

export default Sidebar
