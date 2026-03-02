import { AlertCircle } from 'lucide-react'

function ErrorMessage({ message }) {
  return (
    <div className="mt-4 p-4 rounded-md flex items-start gap-3 bg-destructive/10 border border-destructive/30">
      <AlertCircle className="w-5 h-5 text-destructive flex-shrink-0 mt-0.5" />
      <div>
        <p className="text-destructive font-medium">错误</p>
        <p className="text-destructive/80 text-sm mt-1">{message}</p>
      </div>
    </div>
  )
}

export default ErrorMessage
