import { useState } from 'react'
import { compareModels } from '../services/api'
import ErrorMessage from './ErrorMessage'
import { Card } from './ui/Card'
import { Button } from './ui/Button'
import { Input } from './ui/Input'
import { Textarea } from './ui/Textarea'

function ModelComparator() {
  const [form, setForm] = useState({
    category: 'ai',
    topic: '',
    requirements: '',
    length: 'medium',
    style: 'professional',
    modelsText: 'gpt-4,gpt-4o-mini',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)

  const handleCompare = async () => {
    if (!form.topic.trim()) {
      setError('请输入主题')
      return
    }
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const models = form.modelsText
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean)
      const resp = await compareModels({
        category: form.category,
        topic: form.topic,
        requirements: form.requirements,
        length: form.length,
        style: form.style,
        models,
      })
      setResult(resp)
    } catch (e) {
      setError(e.message || '对比失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <Card className="p-6 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Input
            value={form.topic}
            onChange={(e) => setForm((p) => ({ ...p, topic: e.target.value }))}
            placeholder="输入主题"
          />
          <Input
            value={form.modelsText}
            onChange={(e) => setForm((p) => ({ ...p, modelsText: e.target.value }))}
            placeholder="模型列表，英文逗号分隔"
          />
        </div>
        <Textarea
          value={form.requirements}
          onChange={(e) => setForm((p) => ({ ...p, requirements: e.target.value }))}
          rows={3}
          placeholder="额外要求（可选）"
          className="resize-none"
        />
        <Button onClick={handleCompare} disabled={loading}>
          {loading ? '对比中...' : '开始对比'}
        </Button>
      </Card>

      {result?.results?.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {result.results.map((item) => (
            <Card key={item.model} className="p-5 space-y-3">
              <div className="flex items-center justify-between">
                <p className="text-foreground font-semibold">{item.model}</p>
                <p
                  className={`text-xs px-2 py-1 rounded ${
                    result.winner === item.model ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-muted text-muted-foreground'
                  }`}
                >
                  {result.winner === item.model ? 'Winner' : 'Compared'}
                </p>
              </div>
              <p className="text-xs text-muted-foreground">评分：{item.evaluation?.total_score ?? 0}</p>
              <div className="max-h-60 overflow-auto bg-muted rounded-md border p-3">
                <p className="text-sm text-foreground whitespace-pre-wrap">{item.content || item.error}</p>
              </div>
            </Card>
          ))}
        </div>
      )}

      {error && <ErrorMessage message={error} />}
    </div>
  )
}

export default ModelComparator
