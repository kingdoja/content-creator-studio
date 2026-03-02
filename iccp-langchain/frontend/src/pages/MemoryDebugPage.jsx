import { useEffect, useState } from 'react'
import { RefreshCw, Trash2 } from 'lucide-react'
import { deleteMemoryEntry, getMemoryConfig, getMemoryStats, listMemoryEntries } from '../services/api'
import ErrorMessage from '../components/ErrorMessage'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'

function MemoryDebugPage() {
  const [entries, setEntries] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [timeoutConfig, setTimeoutConfig] = useState(null)
  const [filters, setFilters] = useState({
    memory_type: '',
    source_module: '',
    created_from: '',
    created_to: '',
    offset: 0,
    limit: 20,
  })
  const [pagination, setPagination] = useState({ total: 0, offset: 0, limit: 20, has_more: false })

  const loadData = async (nextFilters = filters) => {
    setLoading(true)
    setError('')
    try {
      const [statsResp, configResp, entriesResp] = await Promise.all([
        getMemoryStats(),
        getMemoryConfig().catch(() => null),
        listMemoryEntries({
          ...nextFilters,
        }),
      ])
      setStats(statsResp?.stats || null)
      setTimeoutConfig(configResp?.config || null)
      setEntries(entriesResp?.entries || [])
      setPagination(entriesResp?.pagination || { total: 0, offset: 0, limit: 20, has_more: false })
    } catch (e) {
      setError(e.message || '加载记忆数据失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleSearch = async () => {
    const next = { ...filters, offset: 0 }
    setFilters(next)
    await loadData(next)
  }

  const handleDelete = async (entryId) => {
    try {
      await deleteMemoryEntry(entryId)
      await loadData()
    } catch (e) {
      setError(e.message || '删除记忆失败')
    }
  }

  const handlePageChange = async (nextOffset) => {
    const next = { ...filters, offset: Math.max(0, nextOffset) }
    setFilters(next)
    await loadData(next)
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex items-center justify-end">
        <Button variant="outline" size="sm" onClick={() => loadData()}>
          <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          刷新
        </Button>
      </div>

      <Card className="p-5 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-6 gap-3">
        <Input
          value={filters.memory_type}
          onChange={(e) => setFilters((prev) => ({ ...prev, memory_type: e.target.value }))}
          placeholder="类型 episodic/semantic"
        />
        <Input
          value={filters.source_module}
          onChange={(e) => setFilters((prev) => ({ ...prev, source_module: e.target.value }))}
          placeholder="来源模块 chat/content/video"
        />
        <Input
          value={filters.created_from}
          onChange={(e) => setFilters((prev) => ({ ...prev, created_from: e.target.value }))}
          placeholder="开始时间 ISO"
        />
        <Input
          value={filters.created_to}
          onChange={(e) => setFilters((prev) => ({ ...prev, created_to: e.target.value }))}
          placeholder="结束时间 ISO"
        />
        <Input
          type="number"
          min={1}
          max={100}
          value={filters.limit}
          onChange={(e) => setFilters((prev) => ({ ...prev, limit: Number(e.target.value || 20) }))}
          placeholder="每页数量"
        />
        <Button onClick={handleSearch}>
          查询
        </Button>
      </Card>

      {stats ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Card className="p-4 text-sm text-foreground">总数：{stats.total}</Card>
          <Card className="p-4 text-sm text-foreground">episodic：{stats.episodic}</Card>
          <Card className="p-4 text-sm text-foreground">semantic：{stats.semantic}</Card>
          <Card className="p-4 text-sm text-foreground">procedural：{stats.procedural}</Card>
        </div>
      ) : null}

      <Card className="p-5">
        <p className="text-sm text-foreground mb-2">当前超时配置说明</p>
        {timeoutConfig ? (
          <div className="text-xs text-muted-foreground space-y-1">
            <p>
              记忆召回超时：{timeoutConfig.memory_recall_timeout_seconds}s（超时自动降级，不中断主流程）
            </p>
            <p>
              视频润色超时：{timeoutConfig.video_polish_timeout_seconds}s（超时返回可解释错误）
            </p>
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">未读取到后端配置，可能是旧版本后端或接口不可用。</p>
        )}
      </Card>

      <Card className="p-5 space-y-3">
        {entries.length === 0 ? (
          <p className="text-sm text-muted-foreground">暂无记忆数据</p>
        ) : (
          entries.map((item) => (
            <div key={item.id} className="rounded-md border bg-muted/50 p-3">
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs text-primary">
                  {item.source_module} · {item.memory_type} · importance={item.importance}
                </p>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => handleDelete(item.id)}
                  className="text-destructive hover:text-destructive"
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
              </div>
              <p className="text-sm text-foreground mt-2 whitespace-pre-wrap">{(item.content || '').slice(0, 320)}</p>
              <p className="text-[11px] text-muted-foreground mt-2">{item.created_at}</p>
            </div>
          ))
        )}
        <div className="flex items-center justify-between pt-2">
          <p className="text-xs text-muted-foreground">
            total={pagination.total} · offset={pagination.offset} · limit={pagination.limit}
          </p>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={pagination.offset <= 0}
              onClick={() => handlePageChange(pagination.offset - pagination.limit)}
            >
              上一页
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={!pagination.has_more}
              onClick={() => handlePageChange(pagination.offset + pagination.limit)}
            >
              下一页
            </Button>
          </div>
        </div>
      </Card>

      {error ? <ErrorMessage message={error} /> : null}
    </div>
  )
}

export default MemoryDebugPage
