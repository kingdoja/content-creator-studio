import { Loader2 } from 'lucide-react'

function LoadingSpinner() {
  return (
    <div className="mt-6 p-8 bg-muted rounded-lg border">
      <div className="flex flex-col items-center justify-center">
        <Loader2 className="w-12 h-12 text-primary animate-spin mb-4" />
        <p className="text-foreground font-medium">AI正在思考中，请稍候...</p>
        <p className="text-sm text-muted-foreground mt-2">这可能需要30秒到2分钟</p>
      </div>
    </div>
  )
}

export default LoadingSpinner
