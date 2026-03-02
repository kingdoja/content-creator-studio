import { useCallback, useEffect, useState } from 'react'
import {
  MessageSquare, PenTool, Image, Video, Database, Gauge,
  ShieldCheck, Activity, ArrowRight, Clock,
} from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { getContentDetail, getContentHistory, getKnowledgeStats, getObservabilityStatus, healthCheck } from '../services/api'
import { saveRefineDraft } from '../constants/editorDraft'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'

const QUICK_LINKS = [
  {
    to: '/chat',
    title: '对话创作',
    desc: '与 AI 实时对话，流式生成内容',
    icon: MessageSquare,
    color: 'text-blue-600',
    bg: 'bg-blue-50',
  },
  {
    to: '/writing',
    title: '文章写作',
    desc: '多 Agent 协同深度写作',
    icon: PenTool,
    color: 'text-violet-600',
    bg: 'bg-violet-50',
  },
  {
    to: '/cover',
    title: '封面生成',
    desc: 'AI 文生图，一键生成封面',
    icon: Image,
    color: 'text-emerald-600',
    bg: 'bg-emerald-50',
  },
  {
    to: '/video',
    title: '故事视频',
    desc: '剧情润色 + 文生视频',
    icon: Video,
    color: 'text-rose-600',
    bg: 'bg-rose-50',
  },
]

function DashboardPage() {
  const navigate = useNavigate()
  const [stats, setStats] = useState({ docs: 0, chunks: 0, health: '-', tracing: '-' })
  const [history, setHistory] = useState([])
  const [detail, setDetail] = useState(null)
  const [detailOpen, setDetailOpen] = useState(false)
  const [loadingDetail, setLoadingDetail] = useState(false)

  const loadDashboardData = useCallback(async () => {
    const [knowledge, health, obs] = await Promise.all([
      getKnowledgeStats().catch(() => null),
      healthCheck().catch(() => null),
      getObservabilityStatus().catch(() => null),
    ])
    const historyResp = await getContentHistory(6).catch(() => null)
    setStats({
      docs: knowledge?.stats?.documents ?? 0,
      chunks: knowledge?.stats?.chunks ?? 0,
      health: health?.status ?? 'down',
      tracing: obs?.langsmith?.enabled ? 'on' : 'off',
    })
    setHistory(historyResp?.items || [])
  }, [])

  useEffect(() => {
    let mounted = true
    ;(async () => {
      try { await loadDashboardData() } catch { if (!mounted) return }
    })()
    const onRefresh = async () => { if (mounted) await loadDashboardData() }
    window.addEventListener('iccp:refresh-system-status', onRefresh)
    return () => { mounted = false; window.removeEventListener('iccp:refresh-system-status', onRefresh) }
  }, [loadDashboardData])

  const handleOpenDetail = async (recordId) => {
    setLoadingDetail(true)
    setDetailOpen(true)
    try {
      const resp = await getContentDetail(recordId)
      setDetail(resp?.item || null)
    } catch { setDetail(null) } finally { setLoadingDetail(false) }
  }

  const handleRefineFromHistory = () => {
    if (!detail) return
    saveRefineDraft({ workspace: 'content', category: detail.category, topic: detail.topic, draft_content: detail.content, style: 'professional', length: 'medium', requirements: '请基于该历史内容做二次优化，保留核心观点并提升结构与表达。' })
    setDetailOpen(false)
    navigate('/writing?mode=refine')
  }

  const handleRefineToChat = () => {
    if (!detail) return
    saveRefineDraft({ workspace: 'chat', category: detail.category, topic: detail.topic, draft_content: detail.content, style: 'professional', length: 'medium', requirements: '请在对话中协作优化这段内容。' })
    setDetailOpen(false)
    navigate('/chat?mode=refine')
  }

  return (
    <div className="space-y-8">
      {/* Welcome */}
      <div>
        <h1 className="text-2xl font-bold text-foreground">欢迎回来</h1>
        <p className="text-muted-foreground text-sm mt-1">选择一个工具开始创作，或查看近期任务</p>
      </div>

      {/* Quick links */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        {QUICK_LINKS.map((link) => {
          const Icon = link.icon
          return (
            <Link key={link.to} to={link.to} className="group">
              <Card className="p-5 h-full hover:shadow-md transition-shadow">
                <div className="flex items-start justify-between mb-4">
                  <div className={`p-2.5 rounded-lg ${link.bg}`}>
                    <Icon className={`w-5 h-5 ${link.color}`} />
                  </div>
                  <ArrowRight className="w-4 h-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                </div>
                <h3 className="text-sm font-semibold text-foreground">{link.title}</h3>
                <p className="text-xs text-muted-foreground mt-1 leading-relaxed">{link.desc}</p>
              </Card>
            </Link>
          )
        })}
      </div>

      {/* System status strip */}
      <Card className="px-5 py-3">
        <div className="flex items-center gap-6 text-xs overflow-x-auto">
          <div className="flex items-center gap-2 text-muted-foreground whitespace-nowrap">
            <Database className="w-3.5 h-3.5" />
            <span>文档 <strong className="text-foreground">{stats.docs}</strong></span>
            <span className="text-border">|</span>
            <span>分块 <strong className="text-foreground">{stats.chunks}</strong></span>
          </div>
          <div className="flex items-center gap-2 text-muted-foreground whitespace-nowrap">
            <Gauge className="w-3.5 h-3.5" />
            <span>后端 <strong className={stats.health === 'ok' ? 'text-green-600' : 'text-foreground'}>{stats.health}</strong></span>
          </div>
          <div className="flex items-center gap-2 text-muted-foreground whitespace-nowrap">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>追踪 <strong className="text-foreground">{stats.tracing}</strong></span>
          </div>
          <div className="flex items-center gap-2 text-muted-foreground whitespace-nowrap">
            <Activity className="w-3.5 h-3.5" />
            <span className="text-green-600 font-medium">Ready</span>
          </div>
        </div>
      </Card>

      {/* Recent tasks */}
      <div>
        <h2 className="text-base font-semibold text-foreground mb-3 flex items-center gap-2">
          <Clock className="w-4 h-4 text-muted-foreground" />
          近期任务
        </h2>
        {history.length === 0 ? (
          <Card className="p-8 text-center">
            <p className="text-sm text-muted-foreground">暂无历史记录</p>
            <p className="text-xs text-muted-foreground mt-1">去「对话」或「写作」创建你的第一条内容</p>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {history.map((item) => (
              <Card key={item.id} className="px-4 py-3 hover:shadow-sm transition-shadow">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm text-foreground font-medium truncate">{item.topic}</p>
                    <div className="flex items-center gap-2 mt-1.5 text-xs text-muted-foreground">
                      <span className="px-1.5 py-0.5 rounded border text-primary text-[10px]">{item.agent || '-'}</span>
                      <span>{item.category}</span>
                      <span>{new Date(item.created_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleOpenDetail(item.id)}
                    className="text-xs text-primary hover:underline whitespace-nowrap shrink-0"
                  >
                    查看
                  </button>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Detail modal */}
      {detailOpen && (
        <div className="fixed inset-0 z-40 bg-black/40" onClick={() => setDetailOpen(false)}>
          <div className="max-w-2xl mx-auto mt-[10vh]" onClick={(e) => e.stopPropagation()}>
            <Card className="p-6 shadow-xl">
              {loadingDetail ? (
                <p className="text-sm text-muted-foreground">加载中...</p>
              ) : !detail ? (
                <p className="text-sm text-destructive">获取失败</p>
              ) : (
                <div className="space-y-4">
                  <div className="flex items-center justify-between gap-3">
                    <h4 className="text-base font-semibold text-foreground truncate">{detail.topic}</h4>
                    <span className="text-xs px-2 py-0.5 rounded border text-primary shrink-0">{detail.agent}</span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {detail.category} · {new Date(detail.created_at).toLocaleString()}
                  </p>
                  <div className="rounded-md border bg-muted p-3 max-h-72 overflow-auto">
                    <pre className="text-sm text-foreground whitespace-pre-wrap">{detail.content}</pre>
                  </div>
                  <div className="flex items-center justify-end gap-2">
                    <Button variant="outline" size="sm" onClick={() => setDetailOpen(false)}>关闭</Button>
                    <Button size="sm" onClick={handleRefineFromHistory}>编辑到写作</Button>
                    <Button variant="secondary" size="sm" onClick={handleRefineToChat}>回填到对话</Button>
                  </div>
                </div>
              )}
            </Card>
          </div>
        </div>
      )}
    </div>
  )
}

export default DashboardPage
