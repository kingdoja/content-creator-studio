import { useEffect, useState } from 'react'
import { Loader2, Sparkles, BookOpen, Layers, AlignLeft, Bot, Plus } from 'lucide-react'
import { useLocation } from 'react-router-dom'
import {
  closeChatSession,
  createChatSession,
  createContentStream,
  getCategoryPrompt,
  listChatSessions,
  refineContentStream,
  suggestAgent,
  updateCategoryPrompt,
} from '../services/api'
import { clearRefineDraft, getDraftTarget, loadRefineDraft } from '../constants/editorDraft'
import CategorySelect from './CategorySelect'
import ResultDisplay from './ResultDisplay'
import LoadingSpinner from './LoadingSpinner'
import ErrorMessage from './ErrorMessage'
import AgentFlowVisualization from './AgentFlowVisualization'
import MemoryIndicator from './MemoryIndicator'
import { Card } from './ui/Card'
import { Button } from './ui/Button'
import { Input } from './ui/Input'
import { Textarea } from './ui/Textarea'
import { Select } from './ui/Select'

const CATEGORIES = [
  { id: 'finance', name: '财经' },
  { id: 'ai', name: '人工智能' },
  { id: 'lifestyle', name: '生活' },
  { id: 'tech', name: '科技' },
  { id: 'books', name: '书籍' },
  { id: 'investment', name: '投资' },
  { id: 'growth', name: '成长' },
]
function ContentCreator() {
  const location = useLocation()
  const [formData, setFormData] = useState({
    category: 'ai',
    topic: '',
    requirements: '',
    length: 'medium',
    style: 'professional',
    force_simple: false,
    draft_content: '',
  })
  
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [agentSuggestion, setAgentSuggestion] = useState(null)
  const [streamTrace, setStreamTrace] = useState([])
  const [refineMode, setRefineMode] = useState(false)
  const [refineRounds, setRefineRounds] = useState([])
  const [sessions, setSessions] = useState([])
  const [sessionId, setSessionId] = useState('')
  const [useMemory, setUseMemory] = useState(true)
  const [categoryPrompt, setCategoryPrompt] = useState('')
  const [promptLoading, setPromptLoading] = useState(false)
  const [promptSaving, setPromptSaving] = useState(false)

  useEffect(() => {
    const draft = loadRefineDraft()
    const queryMode = new URLSearchParams(location.search).get('mode')
    if (draft && queryMode === 'refine' && getDraftTarget(draft) === 'content') {
      setFormData((prev) => ({
        ...prev,
        category: draft.category || prev.category,
        topic: draft.topic || prev.topic,
        requirements: draft.requirements || prev.requirements,
        length: draft.length || prev.length,
        style: draft.style || prev.style,
        draft_content: draft.draft_content || '',
      }))
      setRefineMode(true)
      setRefineRounds([])
    }
  }, [location.search])

  useEffect(() => {
    if (refineMode) return
    const initContentSessions = async () => {
      try {
        const resp = await listChatSessions({
          module: 'content',
          limit: 20,
        })
        const list = resp?.sessions || []
        setSessions(list)
        if (list.length > 0) {
          setSessionId(list[0].id)
        } else {
          const created = await createChatSession({
            module: 'content',
            title: '内容创作会话',
          })
          const createdSession = created?.session
          if (createdSession?.id) {
            setSessionId(createdSession.id)
            setSessions([createdSession])
          }
        }
      } catch (err) {
        setError(err.message || '加载创作会话失败')
      }
    }
    initContentSessions()
  }, [refineMode])

  useEffect(() => {
    const loadCategoryPrompt = async () => {
      try {
        setPromptLoading(true)
        const resp = await getCategoryPrompt(formData.category)
        setCategoryPrompt(resp?.content || '')
      } catch (err) {
        setError(err.message || '加载板块 Prompt 失败')
      } finally {
        setPromptLoading(false)
      }
    }
    loadCategoryPrompt()
  }, [formData.category])

  const buildDiffSummary = (beforeText, afterText) => {
    const beforeLines = (beforeText || '').split('\n')
    const afterLines = (afterText || '').split('\n')
    const maxLen = Math.max(beforeLines.length, afterLines.length)
    let added = 0
    let removed = 0
    let changed = 0
    const preview = []

    for (let i = 0; i < maxLen; i += 1) {
      const beforeLine = beforeLines[i]
      const afterLine = afterLines[i]
      if (beforeLine === undefined && afterLine !== undefined) {
        added += 1
        if (preview.length < 2) preview.push(`+ ${afterLine}`)
      } else if (beforeLine !== undefined && afterLine === undefined) {
        removed += 1
        if (preview.length < 2) preview.push(`- ${beforeLine}`)
      } else if (beforeLine !== afterLine) {
        changed += 1
        if (preview.length < 2) preview.push(`~ ${afterLine || ''}`)
      }
    }

    return {
      added,
      removed,
      changed,
      beforeChars: (beforeText || '').length,
      afterChars: (afterText || '').length,
      preview,
    }
  }

  const exportRefineHistory = () => {
    if (refineRounds.length === 0) return
    const payload = {
      topic: formData.topic,
      category: formData.category,
      exported_at: new Date().toISOString(),
      rounds: refineRounds,
    }
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `refine-history-${Date.now()}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target
    setFormData(prev => ({ ...prev, [name]: type === 'checkbox' ? checked : value }))
    setError(null)
    setResult(null)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    
    if (!formData.topic.trim()) {
      setError('请输入主题')
      return
    }

    setLoading(true)
    setError(null)
    setResult(null)

    try {
      if (refineMode && formData.draft_content.trim()) {
        const previousDraft = formData.draft_content
        const currentInstruction = formData.topic.trim()
        let finalResult = null
        await refineContentStream(
          {
            category: formData.category,
            topic: formData.topic,
            draft_content: formData.draft_content,
            requirements: formData.requirements,
            length: formData.length,
            style: formData.style,
          },
          {
            onStart: () => setStreamTrace(['stream:start', 'node:reflection_start']),
            onNodeUpdate: (payload) => setStreamTrace((prev) => [...prev, `node:${payload.node}`]),
            onContentChunk: (payload) => {
              setResult((prev) => ({
                success: true,
                content: payload.content || prev?.content || '',
                agent: 'reflection',
                tools_used: prev?.tools_used || [],
                iterations: prev?.iterations || 0,
                request: formData,
              }))
            },
            onComplete: (payload) => {
              finalResult = payload
              if (payload?.content) {
                const summary = buildDiffSummary(previousDraft, payload.content)
                setRefineRounds((prev) => [
                  ...prev,
                  {
                    round: prev.length + 1,
                    instruction: currentInstruction,
                    ...summary,
                  },
                ])
                setFormData((prev) => ({ ...prev, draft_content: payload.content }))
              }
            },
            onError: (payload) => {
              throw new Error(payload?.error || '流式二次编辑失败')
            },
          },
        )
        if (finalResult?.success) {
          setResult({ ...finalResult, request: formData })
        } else {
          setError(finalResult?.error || '二次编辑失败')
        }
      } else {
        let finalResult = null
        const payload = {
          ...formData,
          session_id: sessionId || null,
          use_memory: useMemory,
          memory_top_k: 4,
        }
        await createContentStream(payload, {
          onStart: () => {
            setStreamTrace(['stream:start'])
          },
          onNodeUpdate: (payload) => {
            setStreamTrace((prev) => [...prev, `node:${payload.node}`])
          },
          onContentChunk: (payload) => {
            setResult((prev) => ({
              success: true,
              content: payload.content || prev?.content || '',
              agent: prev?.agent || '',
              tools_used: prev?.tools_used || [],
              iterations: prev?.iterations || 0,
              request: formData,
            }))
          },
          onComplete: (payload) => {
            finalResult = payload
          },
          onError: (payload) => {
            throw new Error(payload?.error || '流式生成失败')
          },
        })

        if (finalResult?.success) {
          setResult({ ...finalResult, request: formData })
        } else {
          setError(finalResult?.error || '生成失败')
        }
      }
    } catch (err) {
      setError(err.message || '请求失败，请检查后端服务是否运行')
    } finally {
      setLoading(false)
    }
  }

  const handleGetSuggestion = async () => {
    if (!formData.topic.trim()) {
      setError('请先输入主题')
      return
    }

    try {
      const suggestion = await suggestAgent(formData)
      setAgentSuggestion(suggestion)
    } catch (err) {
      console.error('获取Agent建议失败:', err)
    }
  }

  const handleCreateSession = async () => {
    try {
      const created = await createChatSession({
        module: 'content',
        title: '内容创作会话',
      })
      const createdSession = created?.session
      if (!createdSession?.id) return
      const refreshed = await listChatSessions({
        module: 'content',
        limit: 20,
      })
      setSessions(refreshed?.sessions || [createdSession])
      setSessionId(createdSession.id)
    } catch (err) {
      setError(err.message || '新建会话失败')
    }
  }

  const handleCloseSession = async () => {
    if (!sessionId) return
    try {
      await closeChatSession(sessionId)
      const refreshed = await listChatSessions({
        module: 'content',
        limit: 20,
      })
      const list = refreshed?.sessions || []
      setSessions(list)
      if (list.length > 0) {
        setSessionId(list[0].id)
      } else {
        const created = await createChatSession({
          module: 'content',
          title: '内容创作会话',
        })
        const createdSession = created?.session
        if (createdSession?.id) {
          setSessionId(createdSession.id)
          setSessions([createdSession])
        }
      }
    } catch (err) {
      setError(err.message || '关闭会话失败')
    }
  }

  const handleSaveCategoryPrompt = async () => {
    if (!categoryPrompt.trim()) {
      setError('Prompt 不能为空')
      return
    }
    try {
      setPromptSaving(true)
      setError(null)
      await updateCategoryPrompt(formData.category, { content: categoryPrompt })
    } catch (err) {
      setError(err.message || '保存 Prompt 失败')
    } finally {
      setPromptSaving(false)
    }
  }

  return (
    <div className="max-w-6xl mx-auto">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-5 space-y-6">
          <Card className="p-6 lg:p-8">
            <form onSubmit={handleSubmit} className="space-y-6">
              {refineMode ? (
                <div className="rounded-md border bg-muted p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-sm text-foreground font-semibold">已进入二次编辑模式</p>
                      <p className="text-xs text-muted-foreground mt-1">将基于历史草稿调用 Reflection 二次优化</p>
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setRefineMode(false)
                        setRefineRounds([])
                        clearRefineDraft()
                        setFormData((prev) => ({ ...prev, draft_content: '' }))
                      }}
                    >
                      退出
                    </Button>
                  </div>
                </div>
              ) : null}

              <div>
                <label className="block text-sm font-semibold text-foreground mb-4 flex items-center gap-2">
                  <Layers className="w-4 h-4 text-primary" />
                  内容板块
                </label>
                <CategorySelect
                  value={formData.category}
                  onChange={(value) => setFormData(prev => ({ ...prev, category: value }))}
                  categories={CATEGORIES}
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="block text-sm font-semibold text-foreground">板块 Prompt（可实时编辑）</label>
                  <div className="flex items-center gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={async () => {
                        try {
                          setPromptLoading(true)
                          const resp = await getCategoryPrompt(formData.category)
                          setCategoryPrompt(resp?.content || '')
                        } catch (err) {
                          setError(err.message || '刷新 Prompt 失败')
                        } finally {
                          setPromptLoading(false)
                        }
                      }}
                      disabled={promptLoading || promptSaving}
                    >
                      刷新
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      onClick={handleSaveCategoryPrompt}
                      disabled={promptLoading || promptSaving || !categoryPrompt.trim()}
                    >
                      {promptSaving ? '保存中...' : '保存 Prompt'}
                    </Button>
                  </div>
                </div>
                <Textarea
                  value={categoryPrompt}
                  onChange={(e) => setCategoryPrompt(e.target.value)}
                  rows="8"
                  placeholder={promptLoading ? '正在加载 prompt...' : '请输入板块 prompt'}
                  className="resize-y font-mono text-xs"
                  disabled={promptLoading}
                />
                <p className="text-xs text-muted-foreground mt-2">
                  保存后下一次创作将立即使用最新 Prompt。
                </p>
              </div>

              {!refineMode ? (
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-semibold text-foreground mb-2">创作会话</label>
                    <div className="flex items-center gap-2">
                      <Select
                        value={sessionId}
                        onChange={(e) => setSessionId(e.target.value)}
                        className="flex-1"
                      >
                        {sessions.map((item) => (
                          <option key={item.id} value={item.id}>
                            {(item.title || '内容创作会话').slice(0, 24)}
                          </option>
                        ))}
                      </Select>
                      <Button
                        type="button"
                        variant="outline"
                        size="icon"
                        onClick={handleCreateSession}
                        title="新建创作会话"
                      >
                        <Plus className="w-4 h-4" />
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        onClick={handleCloseSession}
                        disabled={!sessionId}
                        title="关闭会话并摘要沉淀"
                      >
                        关闭
                      </Button>
                    </div>
                  </div>
                  <div className="flex items-center justify-between bg-muted border rounded-md px-4 py-3">
                    <div>
                      <p className="text-sm text-foreground font-medium">启用长期记忆增强</p>
                      <p className="text-xs text-muted-foreground">会基于历史创作会话注入相关上下文</p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={useMemory}
                        onChange={(e) => setUseMemory(e.target.checked)}
                        className="sr-only peer"
                      />
                      <div className="w-11 h-6 bg-muted-foreground/30 rounded-full peer peer-checked:bg-primary transition-colors" />
                      <div className="absolute left-1 top-1 w-4 h-4 bg-white rounded-full transition-transform peer-checked:translate-x-5" />
                    </label>
                  </div>
                </div>
              ) : null}

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-semibold text-foreground mb-2 flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-primary" />
                    创作主题
                  </label>
                  <Input
                    type="text"
                    name="topic"
                    value={formData.topic}
                    onChange={handleChange}
                    placeholder="例如：2024年AI发展趋势"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-semibold text-foreground mb-2 flex items-center gap-2">
                    <AlignLeft className="w-4 h-4 text-primary" />
                    额外要求（可选）
                  </label>
                  <Textarea
                    name="requirements"
                    value={formData.requirements}
                    onChange={handleChange}
                    placeholder="例如：需要引用最新论文和数据..."
                    rows="3"
                    className="resize-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider pl-1">
                    篇幅
                  </label>
                  <Select name="length" value={formData.length} onChange={handleChange}>
                    <option value="short">短篇 (500-800字)</option>
                    <option value="medium">中篇 (1000-1500字)</option>
                    <option value="long">长篇 (2000-3000字)</option>
                  </Select>
                </div>

                <div className="space-y-2">
                  <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider pl-1">
                    风格
                  </label>
                  <Select name="style" value={formData.style} onChange={handleChange}>
                    <option value="casual">轻松友好</option>
                    <option value="professional">专业严谨</option>
                    <option value="humorous">幽默风趣</option>
                  </Select>
                </div>
              </div>

              <div className="flex items-center justify-between bg-muted border rounded-md px-4 py-3">
                <div>
                  <p className="text-sm text-foreground font-medium">强制简单问答模式</p>
                  <p className="text-xs text-muted-foreground">开启后优先命中 simpleagent，适合短问短答</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    name="force_simple"
                    checked={!!formData.force_simple}
                    onChange={handleChange}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-muted-foreground/30 rounded-full peer peer-checked:bg-primary transition-colors" />
                  <div className="absolute left-1 top-1 w-4 h-4 bg-white rounded-full transition-transform peer-checked:translate-x-5" />
                </label>
              </div>

              {refineMode ? (
                <div>
                  <label className="block text-sm font-semibold text-foreground mb-2">历史草稿（可修改）</label>
                  <Textarea
                    name="draft_content"
                    value={formData.draft_content}
                    onChange={handleChange}
                    rows="8"
                    placeholder="这里是待二次编辑的草稿内容"
                    className="resize-y"
                  />
                </div>
              ) : null}

              <div className="pt-4 flex flex-col gap-3">
                <Button type="submit" disabled={loading} size="lg" className="w-full">
                  {loading ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin mr-2" />
                      正在创作中...
                    </>
                  ) : (
                    refineMode ? '开始二次编辑' : '开始创作'
                  )}
                </Button>

                <Button
                  type="button"
                  variant="outline"
                  onClick={handleGetSuggestion}
                  disabled={loading || !formData.topic.trim()}
                  className="w-full"
                >
                  <Bot className="w-4 h-4 mr-2" />
                  获取 Agent 建议
                </Button>
                {refineMode ? (
                  <Button
                    type="button"
                    variant="outline"
                    onClick={exportRefineHistory}
                    disabled={refineRounds.length === 0}
                    className="w-full"
                  >
                    导出优化历史（JSON）
                  </Button>
                ) : null}
              </div>
            </form>

            {agentSuggestion && (
              <div className="mt-6 p-4 bg-muted border rounded-md">
                <p className="text-sm text-foreground flex items-center gap-2 mb-2">
                  <span className="font-bold bg-primary/10 px-2 py-0.5 rounded text-primary border">推荐</span>
                  {agentSuggestion.recommended}
                </p>
                <p className="text-xs text-muted-foreground leading-relaxed pl-1">{agentSuggestion.reason}</p>
              </div>
            )}

            {streamTrace.length > 0 && <div className="mt-4"><AgentFlowVisualization trace={streamTrace} /></div>}
            {refineMode && refineRounds.length > 0 ? (
              <div className="mt-4 rounded-md border bg-muted p-4 max-h-56 overflow-auto">
                <p className="text-sm text-foreground mb-2">逐轮差异追踪（diff）</p>
                <div className="space-y-2">
                  {refineRounds.map((item) => (
                    <div key={`content-round-${item.round}`} className="text-xs text-muted-foreground border rounded p-2">
                      <p className="text-foreground">第 {item.round} 轮：{item.instruction}</p>
                      <p className="mt-1">
                        +{item.added} / -{item.removed} / ~{item.changed} 行，字符 {item.beforeChars} -&gt; {item.afterChars}
                      </p>
                      {item.preview.length > 0 ? <p className="mt-1">{item.preview.join(' | ')}</p> : null}
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            {error && <ErrorMessage message={error} />}
          </Card>
        </div>

        <div className="lg:col-span-7">
          <Card className="p-8 min-h-[600px] flex flex-col">
            {loading ? (
              <div className="flex-1 flex flex-col items-center justify-center">
                <LoadingSpinner />
                <p className="mt-6 text-muted-foreground text-sm font-medium">
                  AI 正在思考、搜索并撰写内容...
                </p>
              </div>
            ) : result ? (
              <div>
                {typeof result.memory_recalled_count === 'number' && (
                  <MemoryIndicator
                    count={result.memory_recalled_count}
                    items={result.memory_recalled || []}
                    title="本轮命中记忆"
                  />
                )}
                <ResultDisplay result={result} />
              </div>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground space-y-6">
                <div className="w-32 h-32 rounded-full bg-muted flex items-center justify-center">
                  <BookOpen className="w-12 h-12 text-muted-foreground" />
                </div>
                <div className="text-center space-y-2">
                  <p className="text-xl font-medium text-foreground">准备创作</p>
                  <p className="text-sm text-muted-foreground max-w-xs mx-auto leading-relaxed">
                    在左侧填写主题，让 AI 为你生成深度内容
                  </p>
                </div>
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  )
}

export default ContentCreator
