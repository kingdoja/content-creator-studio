import { useEffect, useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { getMe } from '../services/api'
import { Card } from './ui/Card'

function RequireAuth({ children, requiredRole = 'user' }) {
  const location = useLocation()
  const [status, setStatus] = useState('checking')
  const [user, setUser] = useState(null)

  useEffect(() => {
    let mounted = true
    ;(async () => {
      try {
        const resp = await getMe()
        if (mounted) {
          setUser(resp?.user || null)
          setStatus('allowed')
        }
      } catch {
        if (mounted) setStatus('denied')
      }
    })()
    return () => {
      mounted = false
    }
  }, [])

  if (status === 'checking') {
    return (
      <Card className="p-6 text-sm text-muted-foreground">
        正在校验登录状态...
      </Card>
    )
  }

  if (status === 'denied') {
    return <Navigate to={`/auth?redirect=${encodeURIComponent(location.pathname)}`} replace />
  }

  const role = user?.role || 'user'
  if (requiredRole === 'admin' && role !== 'admin') {
    return (
      <Card className="p-6">
        <p className="text-foreground text-sm font-medium">当前页面仅管理员可访问</p>
        <p className="text-muted-foreground text-xs mt-2">
          你的角色：{role}。如需权限，请联系管理员并在 `.env` 设置 `ADMIN_EMAILS`。
        </p>
      </Card>
    )
  }

  return children
}

export default RequireAuth
