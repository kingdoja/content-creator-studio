import { useState } from 'react'
import { Copy, Check, Bot, Wrench, RotateCcw, Sparkles } from 'lucide-react'
import { evaluateContent, refineContent } from '../services/api'
import { Button } from './ui/Button'
import { Textarea } from './ui/Textarea'

function ResultDisplay({ result }) {
  const [copied, setCopied] = useState(false)
  const [evaluation, setEvaluation] = useState(null)
  const [evaluating, setEvaluating] = useState(false)
  const [draft, setDraft] = useState(result.content || '')
  const [refining, setRefining] = useState(false)
  const [refinedResult, setRefinedResult] = useState(null)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(result.content)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      alert('复制失败，请手动复制')
    }
  }

  const handleEvaluate = async () => {
    setEvaluating(true)
    try {
      const resp = await evaluateContent({ topic: '内容评估', content: result.content })
      setEvaluation(resp.evaluation || null)
    } catch (err) {
      alert(err.message || '评估失败')
    } finally {
      setEvaluating(false)
    }
  }

  const handleRefine = async () => {
    if (!result?.request?.category || !result?.request?.topic || !draft.trim()) return
    setRefining(true)
    try {
      const resp = await refineContent({
        category: result.request.category,
        topic: result.request.topic,
        requirements: result.request.requirements || '',
        length: result.request.length || 'medium',
        style: result.request.style || 'professional',
        draft_content: draft,
      })
      if (resp?.success && resp?.result?.content) {
        setRefinedResult(resp)
        setDraft(resp.result.content)
      } else {
        alert(resp?.result?.error || '优化失败')
      }
    } catch (err) {
      alert(err.message || '优化失败')
    } finally {
      setRefining(false)
    }
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-xl font-bold text-foreground flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-primary" />
          生成结果
        </h3>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={handleEvaluate} disabled={evaluating}>
            {evaluating ? '评估中...' : '质量评估'}
          </Button>
          <Button variant="outline" onClick={handleCopy}>
            {copied ? (
              <>
                <Check className="w-4 h-4 mr-2" />
                已复制
              </>
            ) : (
              <>
                <Copy className="w-4 h-4 mr-2" />
                复制内容
              </>
            )}
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap gap-3 mb-6">
        {result.agent === 'simple' && (
          <div className="flex items-center gap-2 px-3 py-1.5 bg-green-50 rounded-md border border-green-200">
            <span className="text-sm text-green-700 font-semibold">本次命中 simpleagent</span>
          </div>
        )}
        <div className="flex items-center gap-2 px-3 py-1.5 bg-muted rounded-md border">
          <Bot className="w-4 h-4 text-primary" />
          <span className="text-sm text-foreground">
            <span className="font-semibold text-muted-foreground mr-1">Agent:</span> {result.agent}
          </span>
        </div>
        
        {result.tools_used && result.tools_used.length > 0 && (
          <div className="flex items-center gap-2 px-3 py-1.5 bg-muted rounded-md border">
            <Wrench className="w-4 h-4 text-primary" />
            <span className="text-sm text-foreground">
              <span className="font-semibold text-muted-foreground mr-1">工具:</span> {result.tools_used.join(', ')}
            </span>
          </div>
        )}
        
        <div className="flex items-center gap-2 px-3 py-1.5 bg-muted rounded-md border">
          <RotateCcw className="w-4 h-4 text-primary" />
          <span className="text-sm text-foreground">
            <span className="font-semibold text-muted-foreground mr-1">迭代:</span> {result.iterations}次
          </span>
        </div>
      </div>

      <div className="flex-1 bg-muted p-6 rounded-lg border overflow-y-auto">
        <div className="prose max-w-none text-foreground whitespace-pre-wrap leading-relaxed">
          {result.content}
        </div>
      </div>

      <div className="mt-4 p-4 bg-muted border rounded-lg space-y-3">
        <p className="text-sm text-foreground">Human-in-the-loop 协作编辑</p>
        <Textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          rows={8}
          className="resize-none"
        />
        <div className="flex items-center justify-between">
          <p className="text-xs text-muted-foreground">先人工编辑，再让 Reflection Agent 二次优化</p>
          <Button variant="outline" onClick={handleRefine} disabled={refining}>
            {refining ? '优化中...' : '继续优化'}
          </Button>
        </div>
      </div>

      {evaluation && (
        <div className="mt-4 p-4 bg-muted border rounded-lg">
          <p className="text-sm text-foreground">综合评分：{evaluation.total_score}</p>
          <p className="text-xs text-muted-foreground mt-1">
            准确性 {evaluation.dimensions.accuracy} · 相关性 {evaluation.dimensions.relevance} · 完整性{' '}
            {evaluation.dimensions.completeness}
          </p>
          <p className="text-xs text-foreground mt-2">建议：{(evaluation.advice || []).join('；')}</p>
        </div>
      )}

      {refinedResult?.evaluation && (
        <div className="mt-4 p-4 bg-primary/10 border border-primary/20 rounded-lg">
          <p className="text-sm text-primary">优化后评分：{refinedResult.evaluation.total_score}</p>
        </div>
      )}
    </div>
  )
}

export default ResultDisplay
