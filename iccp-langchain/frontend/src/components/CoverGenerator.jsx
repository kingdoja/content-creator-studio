import { useState } from 'react'
import { Loader2, Download, Wand2, Palette, Monitor, Type, Layout } from 'lucide-react'
import { generateCover, resolveAssetUrl } from '../services/api'
import ErrorMessage from './ErrorMessage'
import { Card } from './ui/Card'
import { Button } from './ui/Button'
import { Textarea } from './ui/Textarea'
import { Select } from './ui/Select'

function CoverGenerator() {
  const [title, setTitle] = useState('')
  const [category, setCategory] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  
  const [options, setOptions] = useState({
    style: 'cinematic',
    tone: 'bright',
    size: '1536x1024',
    quality: 'high',
    avoid_text: true,
  })

  const handleOptionChange = (e) => {
    const { name, value, type, checked } = e.target
    setOptions((prev) => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value,
    }))
  }

  const handleGenerate = async () => {
    if (!title.trim()) {
      setError('请输入封面标题')
      return
    }

    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const response = await generateCover({
        title,
        category,
        ...options,
      })

      if (response.success) {
        setResult(response)
      } else {
        setError(response.error || '封面图生成失败')
      }
    } catch (err) {
      setError(err.message || '封面图生成失败，请检查后端服务')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-6xl mx-auto">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-4 space-y-6">
          <Card className="p-6 lg:p-8">
            <div className="space-y-6">
              <div>
                <label className="block text-sm font-semibold text-foreground mb-2 flex items-center gap-2">
                  <Type className="w-4 h-4 text-primary" />
                  封面标题 <span className="text-destructive">*</span>
                </label>
                <Textarea
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="输入文章标题或画面描述..."
                  rows="3"
                  className="resize-none"
                />
              </div>

              <div className="space-y-5 pt-6 border-t">
                <div className="flex items-center gap-2 text-foreground font-semibold text-sm">
                  <Palette className="w-4 h-4 text-primary" />
                  <span>视觉风格</span>
                </div>
                
                <Select name="style" value={options.style} onChange={handleOptionChange}>
                  <option value="cinematic">电影感 (Cinematic)</option>
                  <option value="minimal">极简主义 (Minimal)</option>
                  <option value="illustration">扁平插画 (Illustration)</option>
                  <option value="3d">3D 渲染 (3D Render)</option>
                  <option value="photography">真实摄影 (Photography)</option>
                  <option value="cyberpunk">赛博朋克 (Cyberpunk)</option>
                </Select>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <label className="block text-xs font-medium text-muted-foreground uppercase tracking-wider pl-1">色调</label>
                    <Select name="tone" value={options.tone} onChange={handleOptionChange}>
                      <option value="bright">明亮</option>
                      <option value="warm">暖色</option>
                      <option value="cool">冷色</option>
                      <option value="dark">暗色</option>
                      <option value="pastel">柔和</option>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <label className="block text-xs font-medium text-muted-foreground uppercase tracking-wider pl-1">尺寸</label>
                    <Select name="size" value={options.size} onChange={handleOptionChange}>
                      <option value="1536x1024">16:9 横版</option>
                      <option value="1024x1024">1:1 方形</option>
                      <option value="1024x1536">2:3 竖版</option>
                    </Select>
                  </div>
                </div>

                <label className="flex items-center gap-3 p-3 bg-muted rounded-md border cursor-pointer hover:bg-accent transition-colors">
                  <input
                    type="checkbox"
                    name="avoid_text"
                    checked={options.avoid_text}
                    onChange={handleOptionChange}
                    className="h-4 w-4 rounded border-input"
                  />
                  <span className="text-sm text-foreground font-medium">避免生成文字</span>
                </label>
              </div>

              <Button
                onClick={handleGenerate}
                disabled={loading || !title.trim()}
                size="lg"
                className="w-full"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin mr-2" />
                    正在绘制...
                  </>
                ) : (
                  <>
                    <Wand2 className="w-5 h-5 mr-2" />
                    立即生成
                  </>
                )}
              </Button>
            </div>
          </Card>
          
          {error && <ErrorMessage message={error} />}
        </div>

        <div className="lg:col-span-8">
          <Card className="p-6 lg:p-8 min-h-[600px] flex flex-col">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-bold text-foreground flex items-center gap-2">
                <Monitor className="w-5 h-5 text-primary" />
                效果预览
              </h3>
              {result && (
                <a
                  href={resolveAssetUrl(result.image_url)}
                  download
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors text-sm font-medium"
                >
                  <Download className="w-4 h-4" />
                  下载原图
                </a>
              )}
            </div>

            <div className="flex-1 bg-muted rounded-lg border-2 border-dashed overflow-hidden relative group transition-colors hover:border-primary/30">
              {loading ? (
                <div className="absolute inset-0 flex flex-col items-center justify-center bg-background/80 z-10">
                  <Loader2 className="w-12 h-12 text-primary animate-spin mb-4" />
                  <p className="text-muted-foreground font-medium">AI 正在构思画面...</p>
                </div>
              ) : result ? (
                <div className="relative w-full h-full flex items-center justify-center bg-muted">
                  <img
                    src={resolveAssetUrl(result.image_url)}
                    alt="Generated Cover"
                    className="max-w-full max-h-full object-contain shadow-lg rounded-md"
                  />
                  <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 via-black/40 to-transparent p-6 opacity-0 group-hover:opacity-100 transition-all duration-300">
                    <p className="text-white/90 text-sm font-medium line-clamp-2 mb-3">
                      <span className="text-primary-foreground mr-2 font-bold">Prompt:</span>
                      {result.prompt_used}
                    </p>
                    <div className="flex items-center gap-4 text-xs text-white/60 font-mono">
                      <span className="bg-white/10 px-2 py-1 rounded">Model: {result.model}</span>
                      <span className="bg-white/10 px-2 py-1 rounded">Time: {result.latency_ms}ms</span>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <div className="w-24 h-24 bg-muted rounded-full flex items-center justify-center mb-6 border">
                    <Layout className="w-10 h-10 text-muted-foreground" />
                  </div>
                  <p className="text-lg font-medium text-foreground">暂无预览</p>
                  <p className="text-sm text-muted-foreground mt-1">在左侧输入标题并点击生成</p>
                </div>
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}

export default CoverGenerator
