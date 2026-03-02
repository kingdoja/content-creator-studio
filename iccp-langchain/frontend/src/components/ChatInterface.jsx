import { useEffect, useState } from 'react'
import { Bot, Plus, Send, User } from 'lucide-react'
import { useLocation } from 'react-router-dom'
import {
  closeChatSession,
  createChatSession,
  getChatSessionMessages,
  listChatSessions,
  refineContentStream,
  sendChatSessionMessageStream,
} from '../services/api'
import { clearRefineDraft, getDraftTarget, loadRefineDraft } from '../constants/editorDraft'
import ErrorMessage from './ErrorMessage'
import { Card } from './ui/Card'
import { Button } from './ui/Button'
import { Input } from './ui/Input'
import { Textarea } from './ui/Textarea'
import { Select } from './ui/Select'

function ChatInterface() {
  const location = useLocation()
  const [topic, setTopic] = useState('')
  const [draftContent, setDraftContent] = useState('')
  const [refineMode, setRefineMode] = useState(false)
  const [draftCategory, setDraftCategory] = useState('ai')
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [status, setStatus] = useState('')
  const [forceSimple, setForceSimple] = useState(false)
  const [refineRounds, setRefineRounds] = useState([])
  const [sessions, setSessions] = useState([])
  const [sessionId, setSessionId] = useState('')

  useEffect(() => {
    const queryMode = new URLSearchParams(location.search).get('mode')
    const draft = loadRefineDraft()
    if (queryMode === 'refine' && draft && getDraftTarget(draft) === 'chat') {
      setTopic(draft.topic || '')
      setDraftContent(draft.draft_content || '')
      setDraftCategory(draft.category || 'ai')
      setRefineMode(true)
      setRefineRounds([])
      setStatus('已加载历史草稿，当前为二次编辑模式')
    }
  }, [location.search])

  useEffect(() => {
    if (refineMode) return
    const initSessions = async () => {
      try {
        const resp = await listChatSessions({ module: 'chat', limit: 20 })
        const list = resp?.sessions || []
        setSessions(list)
        if (list.length > 0) {
          setSessionId(list[0].id)
          await loadSessionMessages(list[0].id)
        } else {
          await handleCreateSession(true)
        }
      } catch (e) {
        setError(e.message || '加载会话失败')
      }
    }
    initSessions()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refineMode])

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

  const loadSessionMessages = async (targetSessionId) => {
    try {
      const resp = await getChatSessionMessages(targetSessionId, 80)
      const normalized = (resp?.messages || []).map((msg) => {
        if (msg.role === 'user' || msg.role === 'assistant') {
          return { role: msg.role, text: msg.content || '' }
        }
        return { role: 'assistant', text: `[系统] ${msg.content || ''}` }
      })
      setMessages(normalized)
    } catch (e) {
      setError(e.message || '加载消息失败')
    }
  }

  const handleCreateSession = async (silent = false) => {
    try {
      const created = await createChatSession({
        module: 'chat',
        title: '新会话',
      })
      const createdSession = created?.session
      if (!createdSession?.id) return
      const refreshed = await listChatSessions({ module: 'chat', limit: 20 })
      setSessions(refreshed?.sessions || [createdSession])
      setSessionId(createdSession.id)
      setMessages([])
      if (!silent) setStatus('已创建新会话')
    } catch (e) {
      setError(e.message || '创建会话失败')
    }
  }

  const handleSelectSession = async (targetId) => {
    setSessionId(targetId)
    setStatus('正在切换会话...')
    await loadSessionMessages(targetId)
    setStatus('会话已切换')
  }

  const handleCloseSession = async () => {
    if (!sessionId) return
    try {
      await closeChatSession(sessionId)
      setStatus('会话已关闭并沉淀摘要记忆')
      const refreshed = await listChatSessions({ module: 'chat', limit: 20 })
      const list = refreshed?.sessions || []
      setSessions(list)
      if (list.length > 0) {
        setSessionId(list[0].id)
        await loadSessionMessages(list[0].id)
      } else {
        await handleCreateSession(true)
      }
    } catch (e) {
      setError(e.message || '关闭会话失败')
    }
  }

  const handleSend = async () => {
    if (!topic.trim()) return
    if (refineMode && !draftContent.trim()) {
      setError('二次编辑模式下请提供草稿内容')
      return
    }
    setError('')
    setLoading(true)
    const userText = topic.trim()
    const previousDraft = draftContent
    if (!refineMode) setTopic('')
    setMessages((prev) => [...prev, { role: 'user', text: userText }, { role: 'assistant', text: '...' }])

    try {
      if (refineMode) {
        let final = null
        const streamPayload = {
            category: draftCategory || 'ai',
            topic: userText,
            draft_content: draftContent,
            requirements: '请保持核心观点并优化表达、结构与可读性。',
            length: 'medium',
            style: 'professional',
          }
        await refineContentStream(streamPayload, {
          onStart: () => {
            setStatus('连接成功，开始执行...')
          },
          onNodeUpdate: (payload) => {
            const node = payload?.node || 'unknown'
            setStatus(`执行节点：${node}`)
            setMessages((prev) => {
              const copy = [...prev]
              const idx = copy.length - 1
              if (
                idx >= 0 &&
                copy[idx]?.role === 'assistant' &&
                (copy[idx].text === '...' || copy[idx].text.startsWith('正在执行'))
              ) {
                copy[idx] = { role: 'assistant', text: `正在执行 ${node} ...` }
              }
              return copy
            })
          },
          onContentChunk: (payload) => {
            setMessages((prev) => {
              const copy = [...prev]
              const idx = copy.length - 1
              copy[idx] = { role: 'assistant', text: payload.content || '' }
              return copy
            })
          },
          onComplete: (payload) => {
            final = payload
            setStatus('执行完成')
            if (payload?.content) {
              setMessages((prev) => {
                const copy = [...prev]
                const idx = copy.length - 1
                if (idx >= 0 && copy[idx]?.role === 'assistant') {
                  copy[idx] = { role: 'assistant', text: payload.content }
                }
                return copy
              })
              const summary = buildDiffSummary(previousDraft, payload.content)
              setRefineRounds((prev) => [
                ...prev,
                {
                  round: prev.length + 1,
                  instruction: userText,
                  ...summary,
                },
              ])
              setDraftContent(payload.content)
            }
          },
          onError: (payload) => {
            throw new Error(payload?.error || '生成失败')
          },
        })

        if (!final?.success) {
          throw new Error(final?.error || '生成失败')
        }
      } else {
        let targetSessionId = sessionId
        if (!targetSessionId) {
          const created = await createChatSession({
            module: 'chat',
            title: '新会话',
          })
          targetSessionId = created?.session?.id || ''
          if (targetSessionId) {
            setSessionId(targetSessionId)
            const refreshed = await listChatSessions({ module: 'chat', limit: 20 })
            setSessions(refreshed?.sessions || [])
          }
        }
        if (!targetSessionId) throw new Error('会话创建失败，请重试')

        setStatus('连接中...')
        let finalPayload = null
        await sendChatSessionMessageStream(
          targetSessionId,
          {
            content: userText,
            category: 'ai',
            style: 'professional',
            length: 'medium',
            requirements: '',
            use_memory: false,
            memory_top_k: 1,
            force_simple: forceSimple,
          },
          {
            onStart: () => setStatus('连接成功，开始执行...'),
            onNodeUpdate: (payload) => {
              const node = payload?.node || 'unknown'
              setStatus(`执行节点：${node}`)
            },
            onContentChunk: (payload) => {
              setMessages((prev) => {
                const copy = [...prev]
                const idx = copy.length - 1
                if (idx >= 0 && copy[idx]?.role === 'assistant') {
                  copy[idx] = { role: 'assistant', text: payload?.content || '' }
                }
                return copy
              })
            },
            onComplete: (payload) => {
              finalPayload = payload
            },
            onError: (payload) => {
              throw new Error(payload?.error || '聊天流式请求失败')
            },
          }
        )
        const assistantText = finalPayload?.assistant?.content || ''
        setMessages((prev) => {
          const copy = [...prev]
          const idx = copy.length - 1
          if (idx >= 0 && copy[idx]?.role === 'assistant') {
            copy[idx] = { role: 'assistant', text: assistantText || '生成失败，请重试' }
          }
          return copy
        })
        const totalMs = finalPayload?.assistant?.timings_ms?.total
        const timingLabel = typeof totalMs === 'number' ? ` · ${totalMs}ms` : ''
        setStatus(`执行完成${timingLabel}`)
        const refreshed = await listChatSessions({ module: 'chat', limit: 20 })
        setSessions(refreshed?.sessions || [])
      }
    } catch (e) {
      setError(e.message || '请求失败')
      setStatus('执行失败')
    } finally {
      setLoading(false)
    }
  }

  const handleExitRefineMode = () => {
    setRefineMode(false)
    setDraftContent('')
    setDraftCategory('ai')
    setRefineRounds([])
    clearRefineDraft()
    setStatus('已退出二次编辑模式')
  }

  return (
    <div className="max-w-5xl mx-auto">
      <Card className="p-5 h-[calc(100vh-7rem)] flex flex-col">
        {!refineMode ? (
          <div className="mb-3 flex items-center gap-2">
            <Select
              value={sessionId}
              onChange={(e) => {
                const targetId = e.target.value
                if (targetId) handleSelectSession(targetId)
              }}
              className="flex-1"
            >
              {sessions.map((item) => (
                <option key={item.id} value={item.id}>
                  {(item.title || '新会话').slice(0, 20)}
                </option>
              ))}
            </Select>
            <Button
              variant="outline"
              size="icon"
              onClick={() => handleCreateSession()}
              title="新建会话"
            >
              <Plus className="w-4 h-4" />
            </Button>
            <Button
              variant="outline"
              onClick={handleCloseSession}
              disabled={!sessionId}
              title="关闭会话并摘要沉淀"
            >
              关闭
            </Button>
          </div>
        ) : null}
        {refineMode ? (
          <div className="mb-3 rounded-md border bg-muted px-3 py-2">
            <div className="flex items-center justify-between gap-3">
              <p className="text-xs text-muted-foreground">二次编辑模式（SSE）：已加载历史草稿，可继续对话优化</p>
              <Button variant="outline" size="sm" onClick={handleExitRefineMode}>
                退出
              </Button>
            </div>
          </div>
        ) : null}
        {status && (
          <div className="mb-3 text-xs text-muted-foreground bg-muted border rounded-md px-3 py-2">
            {status}
          </div>
        )}
        <div className="flex-1 overflow-auto space-y-4 pr-2">
          {messages.length === 0 ? (
            <p className="text-muted-foreground text-sm">输入主题开始对话创作，例如：写一篇关于AI产品冷启动的实战指南</p>
          ) : (
            messages.map((msg, idx) => (
              <div
                key={`${msg.role}-${idx}`}
                className={`rounded-lg p-4 border ${
                  msg.role === 'user'
                    ? 'bg-muted ml-10'
                    : 'bg-card mr-10'
                }`}
              >
                <div className="flex items-center gap-2 mb-2 text-xs text-muted-foreground">
                  {msg.role === 'user' ? <User className="w-3.5 h-3.5" /> : <Bot className="w-3.5 h-3.5" />}
                  {msg.role === 'user' ? '你' : 'AI'}
                </div>
                <div className="text-sm text-foreground whitespace-pre-wrap">{msg.text}</div>
              </div>
            ))
          )}
        </div>

        {refineMode ? (
          <div className="pt-4 mt-4 border-t">
            <label className="block text-xs text-muted-foreground mb-2">当前草稿（可编辑）</label>
            <Textarea
              value={draftContent}
              onChange={(e) => setDraftContent(e.target.value)}
              rows="5"
              placeholder="请输入待优化草稿"
              className="resize-y"
            />
            {refineRounds.length > 0 ? (
              <div className="mt-3 rounded-md border bg-muted p-3 max-h-40 overflow-auto">
                <p className="text-xs text-foreground mb-2">逐轮差异追踪（diff）</p>
                <div className="space-y-2">
                  {refineRounds.map((item) => (
                    <div key={`round-${item.round}`} className="text-xs text-muted-foreground border rounded p-2">
                      <p className="text-foreground">第 {item.round} 轮：{item.instruction}</p>
                      <p className="mt-1">
                        +{item.added} / -{item.removed} / ~{item.changed} 行，字符 {item.beforeChars} -&gt; {item.afterChars}
                      </p>
                      {item.preview.length > 0 ? (
                        <p className="mt-1">{item.preview.join(' | ')}</p>
                      ) : null}
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        ) : null}

        <div className="pt-4 mt-4 border-t flex gap-3">
          <Input
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                if (!loading) handleSend()
              }
            }}
            placeholder={refineMode ? '输入本轮优化目标，如：更口语化、更有结构' : '输入你的创作需求...'}
            className="flex-1"
          />
          <Button onClick={handleSend} disabled={loading}>
            <Send className="w-4 h-4" />
          </Button>
        </div>
        <div className="pt-3 flex items-center justify-between">
          <span className="text-xs text-muted-foreground">强制简单问答模式</span>
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={forceSimple}
              onChange={(e) => setForceSimple(e.target.checked)}
              disabled={refineMode}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-muted rounded-full peer peer-checked:bg-primary transition-colors" />
            <div className="absolute left-1 top-1 w-4 h-4 bg-white rounded-full transition-transform peer-checked:translate-x-5" />
          </label>
        </div>
      </Card>

      {error && <div className="mt-4"><ErrorMessage message={error} /></div>}
    </div>
  )
}

export default ChatInterface
