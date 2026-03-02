import { useEffect, useState } from 'react'
import { BookText, Search, Trash2, Upload } from 'lucide-react'
import {
  deleteKnowledgeDocument,
  getChatSession,
  getChatSessionMessages,
  getContentDetail,
  getMemoryEntry,
  healthCheck,
  getKnowledgeReferences,
  getKnowledgeStats,
  listKnowledgeDocuments,
  listMemoryLinks,
  searchKnowledge,
  uploadKnowledge,
} from '../services/api'
import ErrorMessage from './ErrorMessage'
import { Card } from './ui/Card'
import { Button } from './ui/Button'
import { Input } from './ui/Input'
import { Textarea } from './ui/Textarea'

function KnowledgeBase() {
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [query, setQuery] = useState('')
  const [docs, setDocs] = useState([])
  const [results, setResults] = useState([])
  const [references, setReferences] = useState([])
  const [referenceLinks, setReferenceLinks] = useState([])
  const [activeReferenceDocId, setActiveReferenceDocId] = useState('')
  const [linksLoading, setLinksLoading] = useState(false)
  const [linksError, setLinksError] = useState('')
  const [sourceContext, setSourceContext] = useState(null)
  const [sourceContextLoading, setSourceContextLoading] = useState(false)
  const [sourceContextError, setSourceContextError] = useState('')
  const [activeSourceKey, setActiveSourceKey] = useState('')
  const [stats, setStats] = useState({ documents: 0, chunks: 0 })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [backendReady, setBackendReady] = useState(false)
  const [backendCheckLoading, setBackendCheckLoading] = useState(false)

  const loadData = async () => {
    setError('')
    try {
      const [docResp, statsResp, refResp] = await Promise.all([
        listKnowledgeDocuments(),
        getKnowledgeStats(),
        getKnowledgeReferences({ limit: 10 }),
      ])
      setDocs(docResp.documents || [])
      setStats(statsResp.stats || { documents: 0, chunks: 0 })
      setReferences(refResp.references || [])
    } catch (e) {
      setError(e.message || '加载知识库失败')
    }
  }

  const waitForBackendReady = async (maxAttempts = 6, intervalMs = 1000) => {
    setBackendCheckLoading(true)
    setError('')
    for (let i = 0; i < maxAttempts; i += 1) {
      try {
        const resp = await healthCheck()
        if (resp?.status === 'healthy') {
          setBackendReady(true)
          setBackendCheckLoading(false)
          return true
        }
      } catch (e) {
        // retry
      }
      await new Promise((resolve) => setTimeout(resolve, intervalMs))
    }
    setBackendCheckLoading(false)
    setBackendReady(false)
    setError('后端仍在启动中，已暂停自动加载知识库，请稍后重试。')
    return false
  }

  useEffect(() => {
    let cancelled = false
    const init = async () => {
      const ready = await waitForBackendReady()
      if (!ready || cancelled) return
      await loadData()
    }
    init()
    return () => {
      cancelled = true
    }
  }, [])

  const handleUpload = async (e) => {
    e.preventDefault()
    if (!title.trim() || !content.trim()) {
      setError('标题和内容不能为空')
      return
    }
    setLoading(true)
    setError('')
    try {
      await uploadKnowledge({ title: title.trim(), content: content.trim(), source_type: 'text' })
      setTitle('')
      setContent('')
      await loadData()
    } catch (e) {
      setError(e.message || '上传失败')
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (id) => {
    setError('')
    try {
      await deleteKnowledgeDocument(id)
      await loadData()
    } catch (e) {
      setError(e.message || '删除失败')
    }
  }

  const handleSearch = async () => {
    if (!query.trim()) {
      setError('请输入检索词')
      return
    }
    setLoading(true)
    setError('')
    try {
      const resp = await searchKnowledge({ query: query.trim(), top_k: 6 })
      setResults(resp.results || [])
    } catch (e) {
      setError(e.message || '检索失败')
    } finally {
      setLoading(false)
    }
  }

  const handleLoadReferenceLinks = async (documentId) => {
    if (!documentId) return
    if (activeReferenceDocId === documentId) {
      setActiveReferenceDocId('')
      setReferenceLinks([])
      setLinksError('')
      return
    }
    setLinksLoading(true)
    setLinksError('')
    try {
      const resp = await listMemoryLinks({
        target_type: 'knowledge_document',
        target_id: documentId,
        relation: 'knowledge_citation',
        limit: 50,
      })
      setActiveReferenceDocId(documentId)
      setReferenceLinks(resp?.items || [])
      setActiveSourceKey('')
      setSourceContext(null)
      setSourceContextError('')
    } catch (e) {
      setLinksError(e.message || '加载关联链路失败')
    } finally {
      setLinksLoading(false)
    }
  }

  const handleLoadSourceContext = async (link) => {
    const sourceType = link?.source_type || ''
    const sourceId = link?.source_id || ''
    const sourceKey = `${sourceType}:${sourceId}`
    if (!sourceType || !sourceId) return
    if (activeSourceKey === sourceKey) {
      setActiveSourceKey('')
      setSourceContext(null)
      setSourceContextError('')
      return
    }

    setSourceContextLoading(true)
    setSourceContextError('')
    try {
      if (sourceType === 'content_record') {
        const resp = await getContentDetail(sourceId)
        setSourceContext({
          type: sourceType,
          id: sourceId,
          title: resp?.item?.topic || '内容记录',
          summary: (resp?.item?.content || '').slice(0, 600),
          meta: `agent=${resp?.item?.agent || '-'} · created_at=${resp?.item?.created_at || '-'}`,
        })
      } else if (sourceType === 'session' || sourceType === 'conversation_session') {
        const [sessionResp, messagesResp] = await Promise.all([
          getChatSession(sourceId),
          getChatSessionMessages(sourceId, 6),
        ])
        const messages = messagesResp?.messages || []
        const messagePreview = messages
          .slice(-4)
          .map((msg) => `${msg.role}: ${(msg.content || '').slice(0, 120)}`)
          .join('\n')
        setSourceContext({
          type: 'session',
          id: sourceId,
          title: sessionResp?.session?.title || '会话',
          summary: messagePreview || (sessionResp?.session?.summary || ''),
          meta: `module=${sessionResp?.session?.module || '-'} · updated_at=${sessionResp?.session?.updated_at || '-'}`,
        })
      } else if (sourceType === 'memory_entry') {
        const resp = await getMemoryEntry(sourceId)
        const entry = resp?.entry || {}
        setSourceContext({
          type: sourceType,
          id: sourceId,
          title: `记忆条目（${entry.memory_type || '-'}/${entry.source_module || '-'})`,
          summary: (entry.content || '').slice(0, 700),
          meta: `source_id=${entry.source_id || '-'} · importance=${entry.importance ?? '-'} · created_at=${entry.created_at || '-'}`,
        })
      } else {
        setSourceContext({
          type: sourceType,
          id: sourceId,
          title: '未适配来源类型',
          summary: `当前 source_type=${sourceType} 暂未接入详情接口，可先根据 source_id 在对应模块检索。`,
          meta: '',
        })
      }
      setActiveSourceKey(sourceKey)
    } catch (e) {
      setSourceContextError(e.message || '加载来源上下文失败')
    } finally {
      setSourceContextLoading(false)
    }
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {!backendReady ? (
        <Card className="p-4 border-amber-200 bg-amber-50">
          <p className="text-sm text-amber-800">
            {backendCheckLoading
              ? '正在等待后端启动完成，暂不自动拉取知识库数据...'
              : '后端未就绪，知识库自动加载已暂停。'}
          </p>
          {!backendCheckLoading ? (
            <Button
              variant="outline"
              size="sm"
              onClick={async () => {
                const ready = await waitForBackendReady()
                if (ready) await loadData()
              }}
              className="mt-3"
            >
              重新检测并加载
            </Button>
          ) : null}
        </Card>
      ) : null}
      <div className="flex items-center justify-end">
        <div className="text-xs text-muted-foreground bg-muted border rounded-md px-3 py-1.5">
          文档 {stats.documents} · 分块 {stats.chunks}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="p-6">
          <form onSubmit={handleUpload} className="space-y-4">
            <div className="flex items-center gap-2 text-foreground font-semibold">
              <Upload className="w-4 h-4 text-primary" />
              上传文本资料
            </div>
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="资料标题"
            />
            <Textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              rows={8}
              placeholder="粘贴知识内容（后续可扩展 PDF/URL 上传）"
              className="resize-none"
            />
            <Button type="submit" disabled={loading} className="w-full">
              {loading ? '处理中...' : '上传到知识库'}
            </Button>
          </form>
        </Card>

        <Card className="p-6 space-y-4">
          <div className="flex items-center gap-2 text-foreground font-semibold">
            <BookText className="w-4 h-4 text-primary" />
            文档列表
          </div>
          <div className="max-h-80 overflow-auto space-y-3">
            {docs.length === 0 ? (
              <p className="text-muted-foreground text-sm">暂无文档</p>
            ) : (
              docs.map((doc) => (
                <div key={doc.id} className="bg-muted border rounded-md p-3">
                  <div className="flex items-center justify-between gap-2">
                    <div>
                      <p className="text-foreground text-sm font-medium">{doc.title}</p>
                      <p className="text-muted-foreground text-xs mt-1">分块 {doc.chunk_count}</p>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleDelete(doc.id)}
                      className="text-destructive hover:text-destructive"
                      title="删除"
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              ))
            )}
          </div>
        </Card>
      </div>

      <Card className="p-6 space-y-4">
        <div className="flex items-center gap-2 text-foreground font-semibold">
          <Search className="w-4 h-4 text-green-600" />
          语义检索测试
        </div>
        <div className="flex gap-3">
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="输入问题，查看检索片段"
            className="flex-1"
          />
          <Button variant="outline" onClick={handleSearch} disabled={loading}>
            检索
          </Button>
        </div>

        <div className="space-y-3">
          {results.map((item) => (
            <div key={item.chunk_id} className="bg-muted border rounded-md p-4">
              <p className="text-xs text-muted-foreground">来源：{item.document_title} · 分数：{item.score}</p>
              <p className="text-sm text-foreground mt-2 whitespace-pre-wrap">{item.content}</p>
            </div>
          ))}
        </div>
      </Card>

      <Card className="p-6 space-y-4">
        <div className="flex items-center gap-2 text-foreground font-semibold">
          <BookText className="w-4 h-4 text-primary" />
          知识引用追踪
        </div>
        <div className="space-y-2">
          {references.length === 0 ? (
            <p className="text-muted-foreground text-sm">暂无引用记录（生成内容后会自动统计）</p>
          ) : (
            references.map((item) => (
              <button
                key={item.document_id}
                type="button"
                onClick={() => handleLoadReferenceLinks(item.document_id)}
                className={`w-full text-left bg-muted border rounded-md p-3 transition-colors ${
                  activeReferenceDocId === item.document_id
                    ? 'border-primary/40 bg-primary/5'
                    : 'hover:border-primary/30'
                }`}
              >
                <p className="text-sm text-foreground">{item.document_title || item.document_id}</p>
                <p className="text-xs text-muted-foreground mt-1">
                  引用次数 {item.reference_count} · 最近引用 {item.last_referenced_at || '-'}
                </p>
                <p className="text-[11px] text-primary mt-2">点击查看关联链路</p>
              </button>
            ))
          )}
        </div>
      </Card>

      <Card className="p-6 space-y-4">
        <div className="flex items-center gap-2 text-foreground font-semibold">
          <BookText className="w-4 h-4 text-primary" />
          关联链路详情
        </div>
        {!activeReferenceDocId ? (
          <p className="text-muted-foreground text-sm">点击上方"知识引用追踪"中的条目查看链路详情</p>
        ) : linksLoading ? (
          <p className="text-muted-foreground text-sm">加载中...</p>
        ) : linksError ? (
          <p className="text-destructive text-sm">{linksError}</p>
        ) : referenceLinks.length === 0 ? (
          <p className="text-muted-foreground text-sm">当前文档暂无可展示的关联链路</p>
        ) : (
          <div className="space-y-2">
            {referenceLinks.map((link) => (
              <div key={link.id} className="bg-muted border rounded-md p-3">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs text-foreground">
                    来源：{link.source_type} /
                    {' '}
                    <button
                      type="button"
                      onClick={() => handleLoadSourceContext(link)}
                      className="underline text-primary hover:text-primary/80"
                    >
                      {link.source_id}
                    </button>
                  </p>
                  <span className="text-[11px] text-muted-foreground">点击 source_id 回溯上下文</span>
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  关系：{link.relation} · 强度：{link.strength} · 时间：{link.created_at || '-'}
                </p>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card className="p-6 space-y-4">
        <div className="flex items-center gap-2 text-foreground font-semibold">
          <BookText className="w-4 h-4 text-primary" />
          来源上下文回溯
        </div>
        {!activeSourceKey ? (
          <p className="text-muted-foreground text-sm">在"关联链路详情"里点击 source_id 查看对应上下文</p>
        ) : sourceContextLoading ? (
          <p className="text-muted-foreground text-sm">正在加载来源上下文...</p>
        ) : sourceContextError ? (
          <p className="text-destructive text-sm">{sourceContextError}</p>
        ) : sourceContext ? (
          <div className="rounded-md border bg-muted p-4">
            <p className="text-sm text-foreground">{sourceContext.title}</p>
            {sourceContext.meta ? <p className="text-xs text-muted-foreground mt-1">{sourceContext.meta}</p> : null}
            <p className="text-sm text-foreground mt-3 whitespace-pre-wrap">{sourceContext.summary || '无可展示内容'}</p>
          </div>
        ) : (
          <p className="text-muted-foreground text-sm">未获取到来源上下文</p>
        )}
      </Card>

      {error && <ErrorMessage message={error} />}
    </div>
  )
}

export default KnowledgeBase
