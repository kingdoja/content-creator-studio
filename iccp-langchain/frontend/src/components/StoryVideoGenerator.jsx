import { useEffect, useState } from 'react'
import { Loader2, Wand2, Sparkles, Download, Film, ListVideo, Plus } from 'lucide-react'
import {
  closeChatSession,
  createChatSession,
  getStoryVideoTaskStatus,
  listChatSessions,
  resolveAssetUrl,
  startStoryVideoTask,
} from '../services/api'
import ErrorMessage from './ErrorMessage'
import MemoryIndicator from './MemoryIndicator'
import { Card } from './ui/Card'
import { Button } from './ui/Button'
import { Input } from './ui/Input'
import { Textarea } from './ui/Textarea'
import { Select } from './ui/Select'

function StoryVideoGenerator() {
  const [formData, setFormData] = useState({
    input_text: '',
    genre: 'sci-fi',
    mood: 'epic',
    duration_seconds: 8,
    aspect_ratio: '16:9',
    provider: 'mock',
    model: '',
    resolution: '720p',
    watermark: false,
    camera_fixed: false,
    seed: '',
    extra_requirements: '',
  })
  const [loading, setLoading] = useState(false)
  const [polling, setPolling] = useState(false)
  const [result, setResult] = useState(null)
  const [taskStatus, setTaskStatus] = useState('')
  const [taskId, setTaskId] = useState('')
  const [progressPercent, setProgressPercent] = useState(0)
  const [error, setError] = useState(null)
  const [sessions, setSessions] = useState([])
  const [sessionId, setSessionId] = useState('')
  const [useMemory, setUseMemory] = useState(true)

  useEffect(() => {
    const initVideoSessions = async () => {
      try {
        const resp = await listChatSessions({ module: 'video', limit: 20 })
        const list = resp?.sessions || []
        setSessions(list)
        if (list.length > 0) {
          setSessionId(list[0].id)
        } else {
          const created = await createChatSession({
            module: 'video',
            title: '视频创作会话',
          })
          const s = created?.session
          if (s?.id) {
            setSessionId(s.id)
            setSessions([s])
          }
        }
      } catch (err) {
        setError(err.message || '加载视频会话失败')
      }
    }
    initVideoSessions()
  }, [])

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target
    setFormData((prev) => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value,
    }))
  }

  const statusLabel = (status) => {
    if (status === 'queued') return '排队中'
    if (status === 'running') return '生成中'
    if (status === 'succeeded') return '已完成'
    if (status === 'failed') return '失败'
    if (status === 'cancelled') return '已取消'
    if (status === 'expired') return '已超时'
    if (status === 'mocked') return 'Mock 模式'
    return status || '待开始'
  }

  const pollTask = async (seedanceTaskId, provider) => {
    setPolling(true)
    try {
      let keepPolling = true
      while (keepPolling) {
        const statusResp = await getStoryVideoTaskStatus(seedanceTaskId, provider)
        setTaskStatus(statusResp.status || '')
        setProgressPercent(statusResp.progress_percent ?? 0)
        setResult((prev) => ({
          ...(prev || {}),
          task_id: seedanceTaskId,
          status: statusResp.status,
          video_url: statusResp.video_url || null,
        }))

        if (['succeeded', 'failed', 'cancelled', 'expired', 'mocked'].includes(statusResp.status)) {
          keepPolling = false
          if (statusResp.error) {
            setError(statusResp.error)
          }
          break
        }
        await new Promise((resolve) => setTimeout(resolve, 2000))
      }
    } finally {
      setPolling(false)
      setLoading(false)
    }
  }

  const handleGenerate = async () => {
    if (!formData.input_text.trim()) {
      setError('请输入标题或一段剧情描述')
      return
    }

    setLoading(true)
    setError(null)
    setResult(null)
    setTaskStatus('')
    setTaskId('')
    setProgressPercent(0)
    try {
      const response = await startStoryVideoTask({
        ...formData,
        duration_seconds: Number(formData.duration_seconds),
        seed: formData.seed === '' ? null : Number(formData.seed),
        session_id: sessionId || null,
        use_memory: useMemory,
        memory_top_k: 4,
      })

      if (!response.success) {
        setError(response.error || '视频生成失败')
        setLoading(false)
        return
      }

      setResult(response)
      setTaskStatus(response.status || '')
      setProgressPercent(response.progress_percent ?? 0)
      if (response.task_id) {
        setTaskId(response.task_id)
        await pollTask(response.task_id, formData.provider)
      } else {
        setLoading(false)
      }
    } catch (err) {
      setError(err.message || '视频生成失败，请检查后端服务')
      setLoading(false)
    }
  }

  const handleCreateSession = async () => {
    try {
      const created = await createChatSession({
        module: 'video',
        title: '视频创作会话',
      })
      const s = created?.session
      if (!s?.id) return
      const refreshed = await listChatSessions({ module: 'video', limit: 20 })
      setSessions(refreshed?.sessions || [s])
      setSessionId(s.id)
    } catch (err) {
      setError(err.message || '新建会话失败')
    }
  }

  const handleCloseSession = async () => {
    if (!sessionId) return
    try {
      await closeChatSession(sessionId)
      const refreshed = await listChatSessions({ module: 'video', limit: 20 })
      const list = refreshed?.sessions || []
      setSessions(list)
      if (list.length > 0) {
        setSessionId(list[0].id)
      } else {
        await handleCreateSession()
      }
    } catch (err) {
      setError(err.message || '关闭会话失败')
    }
  }

  return (
    <div className="max-w-6xl mx-auto">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-5 space-y-6">
          <Card className="p-6 lg:p-8">
            <div className="space-y-6">
              <div>
                <label className="block text-sm font-semibold text-foreground mb-2 flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-primary" />
                  输入标题或剧情文本
                </label>
                <Textarea
                  name="input_text"
                  value={formData.input_text}
                  onChange={handleChange}
                  placeholder="例如：一个失去记忆的机器人在雨夜城市寻找自我..."
                  rows="5"
                  className="resize-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider pl-1">剧情类型</label>
                  <Select name="genre" value={formData.genre} onChange={handleChange}>
                    <option value="sci-fi">科幻</option>
                    <option value="suspense">悬疑</option>
                    <option value="healing">治愈</option>
                    <option value="business">商业叙事</option>
                    <option value="fantasy">奇幻</option>
                    <option value="documentary">纪录片风</option>
                  </Select>
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider pl-1">情绪基调</label>
                  <Select name="mood" value={formData.mood} onChange={handleChange}>
                    <option value="epic">史诗</option>
                    <option value="warm">温暖</option>
                    <option value="dark">暗黑</option>
                    <option value="hopeful">希望感</option>
                    <option value="tense">紧张</option>
                  </Select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider pl-1">时长（秒）</label>
                  <Input name="duration_seconds" type="number" min="3" max="20" value={formData.duration_seconds} onChange={handleChange} />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider pl-1">比例</label>
                  <Select name="aspect_ratio" value={formData.aspect_ratio} onChange={handleChange}>
                    <option value="16:9">16:9 横版</option>
                    <option value="9:16">9:16 竖版</option>
                    <option value="1:1">1:1 方形</option>
                  </Select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider pl-1">视频会话</label>
                  <div className="flex items-center gap-2">
                    <Select value={sessionId} onChange={(e) => setSessionId(e.target.value)} className="flex-1">
                      {sessions.map((item) => (
                        <option key={item.id} value={item.id}>
                          {(item.title || '视频创作会话').slice(0, 24)}
                        </option>
                      ))}
                    </Select>
                    <Button variant="outline" size="icon" onClick={handleCreateSession} title="新建视频会话">
                      <Plus className="w-4 h-4" />
                    </Button>
                    <Button variant="outline" onClick={handleCloseSession} disabled={!sessionId} title="关闭会话并摘要沉淀">
                      关闭
                    </Button>
                  </div>
                </div>
                <label className="flex items-center gap-3 p-3 bg-muted rounded-md border cursor-pointer hover:bg-accent transition-colors">
                  <input type="checkbox" checked={useMemory} onChange={(e) => setUseMemory(e.target.checked)} className="h-4 w-4" />
                  <span className="text-sm text-foreground">启用长期记忆延续</span>
                </label>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider pl-1">Provider</label>
                  <Select name="provider" value={formData.provider} onChange={handleChange}>
                    <option value="mock">mock（联调）</option>
                    <option value="seedance">seedance</option>
                    <option value="custom">custom</option>
                  </Select>
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider pl-1">视频模型（可选）</label>
                  <Input name="model" value={formData.model} onChange={handleChange} placeholder="如 seedance-v1-pro" />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider pl-1">分辨率</label>
                  <Select name="resolution" value={formData.resolution} onChange={handleChange}>
                    <option value="480p">480p</option>
                    <option value="720p">720p</option>
                    <option value="1080p">1080p</option>
                  </Select>
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider pl-1">随机种子（可选）</label>
                  <Input name="seed" type="number" value={formData.seed} onChange={handleChange} placeholder="-1 或其他整数" />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <label className="flex items-center gap-3 p-3 bg-muted rounded-md border cursor-pointer hover:bg-accent transition-colors">
                  <input type="checkbox" name="watermark" checked={formData.watermark} onChange={handleChange} className="h-4 w-4" />
                  <span className="text-sm text-foreground">添加水印</span>
                </label>
                <label className="flex items-center gap-3 p-3 bg-muted rounded-md border cursor-pointer hover:bg-accent transition-colors">
                  <input type="checkbox" name="camera_fixed" checked={formData.camera_fixed} onChange={handleChange} className="h-4 w-4" />
                  <span className="text-sm text-foreground">固定机位</span>
                </label>
              </div>

              <div>
                <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wider pl-1 mb-2">
                  额外要求（可选）
                </label>
                <Textarea
                  name="extra_requirements"
                  value={formData.extra_requirements}
                  onChange={handleChange}
                  placeholder="例如：电影感运镜，避免字幕水印，人物动作自然..."
                  rows="3"
                  className="resize-none"
                />
              </div>

              <Button
                onClick={handleGenerate}
                disabled={(loading || polling) || !formData.input_text.trim()}
                size="lg"
                className="w-full"
              >
                {(loading || polling) ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin mr-2" />
                    正在生成剧情与视频...
                  </>
                ) : (
                  <>
                    <Wand2 className="w-5 h-5 mr-2" />
                    生成剧情与视频
                  </>
                )}
              </Button>
            </div>
          </Card>

          {error && <ErrorMessage message={error} />}
        </div>

        <div className="lg:col-span-7">
          <Card className="p-6 lg:p-8 min-h-[620px] flex flex-col">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-bold text-foreground flex items-center gap-2">
                <Film className="w-5 h-5 text-primary" />
                生成结果
              </h3>
              {result?.video_url && (
                <a
                  href={resolveAssetUrl(result.video_url)}
                  target="_blank"
                  rel="noreferrer"
                  download
                  className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors text-sm font-medium"
                >
                  <Download className="w-4 h-4" />
                  下载视频
                </a>
              )}
            </div>

            {!result && !loading && !polling && (
              <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground space-y-4">
                <div className="w-20 h-20 rounded-full bg-muted border flex items-center justify-center">
                  <ListVideo className="w-9 h-9 text-muted-foreground" />
                </div>
                <p className="text-foreground">等待生成结果</p>
              </div>
            )}

            {(loading || polling) && (
              <div className="flex-1 flex flex-col items-center justify-center">
                <Loader2 className="w-10 h-10 text-primary animate-spin mb-4" />
                <p className="text-muted-foreground text-sm mb-4">AI 正在润色剧情并生成视频...</p>
                <div className="w-full max-w-md">
                  <div className="flex items-center justify-between mb-2 text-xs text-foreground">
                    <span>状态：{statusLabel(taskStatus)}</span>
                    <span>{progressPercent}%</span>
                  </div>
                  <div className="w-full h-2 rounded-full bg-muted overflow-hidden border">
                    <div
                      className="h-full bg-primary transition-all duration-500"
                      style={{ width: `${Math.max(0, Math.min(100, progressPercent))}%` }}
                    />
                  </div>
                  {taskId && (
                    <p className="mt-2 text-[11px] text-muted-foreground break-all">Task ID: {taskId}</p>
                  )}
                </div>
              </div>
            )}

            {result && (
              <div className="space-y-5">
                {typeof result.memory_recalled_count === 'number' ? (
                  <MemoryIndicator
                    count={result.memory_recalled_count}
                    items={result.memory_recalled || []}
                    title="本轮命中记忆"
                  />
                ) : null}
                <div className="p-4 rounded-md bg-muted border">
                  <p className="text-xs text-muted-foreground mb-2 uppercase tracking-wider">润色剧情</p>
                  <p className="text-foreground text-sm leading-relaxed whitespace-pre-wrap">{result.storyline}</p>
                </div>

                <div className="p-4 rounded-md bg-muted border">
                  <p className="text-xs text-muted-foreground mb-2 uppercase tracking-wider">视频 Prompt</p>
                  <p className="text-foreground text-sm leading-relaxed whitespace-pre-wrap">{result.video_prompt}</p>
                </div>

                <div className="flex flex-wrap items-center gap-2 text-xs text-foreground">
                  <span className="px-2 py-1 rounded bg-muted border">状态: {statusLabel(result.status)}</span>
                  <span className="px-2 py-1 rounded bg-muted border">Provider: {result.provider || '-'}</span>
                  <span className="px-2 py-1 rounded bg-muted border">Model: {result.model || '-'}</span>
                  <span className="px-2 py-1 rounded bg-muted border">耗时: {result.latency_ms || 0}ms</span>
                </div>

                {result.video_url ? (
                  <video
                    controls
                    src={resolveAssetUrl(result.video_url)}
                    className="w-full rounded-lg border"
                  />
                ) : (
                  <div className="p-4 rounded-md bg-amber-50 border border-amber-200 text-amber-800 text-sm">
                    当前为 mock 模式或视频接口未返回视频地址。你可以配置真实 Provider 后再次生成。
                  </div>
                )}
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  )
}

export default StoryVideoGenerator
