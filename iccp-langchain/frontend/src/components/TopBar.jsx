import { useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Search, Command, ChevronRight } from 'lucide-react'

const BREADCRUMB_MAP = {
  '/dashboard': [{ label: '总览' }],
  '/chat': [{ label: 'AI 创作' }, { label: '对话' }],
  '/writing': [{ label: 'AI 创作' }, { label: '写作' }],
  '/cover': [{ label: 'AI 创作' }, { label: '封面' }],
  '/video': [{ label: 'AI 创作' }, { label: '视频' }],
  '/knowledge': [{ label: '数据' }, { label: '知识库' }],
  '/model-compare': [{ label: '管理' }, { label: '模型对比' }],
  '/memory': [{ label: '管理' }, { label: '记忆调试' }],
  '/auth': [{ label: '管理' }, { label: '认证' }],
}

const ROUTE_ITEMS = [
  { key: '/dashboard', label: '总览', path: '/dashboard' },
  { key: '/chat', label: '对话', path: '/chat' },
  { key: '/writing', label: '写作', path: '/writing' },
  { key: '/cover', label: '封面', path: '/cover' },
  { key: '/video', label: '视频', path: '/video' },
  { key: '/knowledge', label: '知识库', path: '/knowledge' },
  { key: '/model-compare', label: '模型对比', path: '/model-compare' },
  { key: '/memory', label: '记忆调试', path: '/memory' },
  { key: '/auth', label: '认证', path: '/auth' },
]

function TopBar() {
  const location = useLocation()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [keyword, setKeyword] = useState('')

  const breadcrumbs = useMemo(
    () => BREADCRUMB_MAP[location.pathname] || [{ label: 'ICCP' }],
    [location.pathname],
  )

  const filtered = useMemo(
    () =>
      ROUTE_ITEMS.filter((item) =>
        `${item.label} ${item.path}`.toLowerCase().includes(keyword.toLowerCase()),
      ),
    [keyword],
  )

  useEffect(() => {
    const onKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setOpen((prev) => !prev)
      }
      if (e.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  const runCommand = (item) => {
    navigate(item.path)
    setOpen(false)
    setKeyword('')
  }

  return (
    <>
      <header className="sticky top-0 z-20 bg-card/80 backdrop-blur-sm border-b">
        <div className="px-6 h-12 flex items-center justify-between gap-4">
          <nav className="flex items-center gap-1 text-sm">
            {breadcrumbs.map((crumb, idx) => (
              <span key={crumb.label} className="flex items-center gap-1">
                {idx > 0 && <ChevronRight className="w-3 h-3 text-muted-foreground" />}
                <span className={idx === breadcrumbs.length - 1 ? 'text-foreground font-medium' : 'text-muted-foreground'}>
                  {crumb.label}
                </span>
              </span>
            ))}
          </nav>
          <button
            type="button"
            onClick={() => setOpen(true)}
            className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-md border bg-background text-muted-foreground text-xs hover:bg-accent transition-colors"
          >
            <Search className="w-3 h-3" />
            <span>搜索...</span>
            <span className="ml-1 inline-flex items-center gap-0.5 text-[10px] border rounded px-1 py-0.5">
              <Command className="w-2.5 h-2.5" />K
            </span>
          </button>
        </div>
      </header>

      {open && (
        <div className="fixed inset-0 z-50 bg-black/40" onClick={() => setOpen(false)}>
          <div className="max-w-lg mx-auto mt-[15vh]" onClick={(e) => e.stopPropagation()}>
            <div className="rounded-lg border bg-card shadow-xl overflow-hidden">
              <div className="flex items-center gap-2 px-4 py-3 border-b">
                <Search className="w-4 h-4 text-muted-foreground" />
                <input
                  autoFocus
                  value={keyword}
                  onChange={(e) => setKeyword(e.target.value)}
                  placeholder="跳转到..."
                  className="w-full bg-transparent outline-none text-sm text-foreground placeholder:text-muted-foreground"
                />
              </div>
              <div className="max-h-72 overflow-auto py-1">
                {filtered.length > 0 ? (
                  filtered.map((item) => (
                    <button
                      key={item.key}
                      type="button"
                      onClick={() => runCommand(item)}
                      className="w-full text-left px-4 py-2.5 hover:bg-accent transition-colors flex items-center justify-between"
                    >
                      <span className="text-sm text-foreground">{item.label}</span>
                      <span className="text-[10px] text-muted-foreground">{item.path}</span>
                    </button>
                  ))
                ) : (
                  <div className="px-4 py-6 text-sm text-muted-foreground text-center">没有匹配项</div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  )
}

export default TopBar
