import { useState } from 'react'
import { UserCircle2 } from 'lucide-react'
import { useLocation, useNavigate } from 'react-router-dom'
import { getMe, getObservabilityStatus, login, logout, register } from '../services/api'
import ErrorMessage from './ErrorMessage'
import { Card } from './ui/Card'
import { Button } from './ui/Button'
import { Input } from './ui/Input'

function AuthCenter() {
  const navigate = useNavigate()
  const location = useLocation()
  const [mode, setMode] = useState('login')
  const [form, setForm] = useState({ username: '', email: '', password: '' })
  const [me, setMe] = useState(null)
  const [obs, setObs] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      if (mode === 'register') {
        await register({
          username: form.username.trim(),
          email: form.email.trim(),
          password: form.password,
        })
      } else {
        await login({ email: form.email.trim(), password: form.password })
      }
      const profile = await getMe()
      setMe(profile.user || null)
      const redirectPath = new URLSearchParams(location.search).get('redirect')
      if (redirectPath) navigate(redirectPath, { replace: true })
    } catch (err) {
      setError(err.message || '认证失败')
    } finally {
      setLoading(false)
    }
  }

  const handleLoadObs = async () => {
    setError('')
    try {
      const resp = await getObservabilityStatus()
      setObs(resp.langsmith || null)
    } catch (err) {
      setError(err.message || '获取可观测状态失败')
    }
  }

  const handleLogout = () => {
    logout()
    setMe(null)
  }

  return (
    <div className="max-w-lg mx-auto space-y-6">
      <Card className="p-6">
        <div className="flex gap-2 mb-4">
          <Button
            variant={mode === 'login' ? 'default' : 'secondary'}
            onClick={() => setMode('login')}
          >
            登录
          </Button>
          <Button
            variant={mode === 'register' ? 'default' : 'secondary'}
            onClick={() => setMode('register')}
          >
            注册
          </Button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          {mode === 'register' && (
            <Input
              value={form.username}
              onChange={(e) => setForm((p) => ({ ...p, username: e.target.value }))}
              placeholder="用户名"
            />
          )}
          <Input
            value={form.email}
            onChange={(e) => setForm((p) => ({ ...p, email: e.target.value }))}
            placeholder="邮箱"
          />
          <Input
            type="password"
            value={form.password}
            onChange={(e) => setForm((p) => ({ ...p, password: e.target.value }))}
            placeholder="密码"
          />
          <Button type="submit" disabled={loading}>
            {loading ? '处理中...' : mode === 'register' ? '注册并登录' : '登录'}
          </Button>
        </form>

        {me && (
          <div className="mt-4 p-4 rounded-md border bg-muted">
            <p className="text-sm text-foreground flex items-center gap-2">
              <UserCircle2 className="w-4 h-4 text-green-600" />
              当前用户：{me.username}（{me.email}）
            </p>
            <p className="text-xs text-muted-foreground mt-2">角色：{me.role || 'user'}</p>
            <Button
              variant="outline"
              size="sm"
              onClick={handleLogout}
              className="mt-3 text-destructive border-destructive/30 hover:bg-destructive/10"
            >
              退出登录
            </Button>
          </div>
        )}
      </Card>

      <Card className="p-6 space-y-3">
        <p className="text-foreground font-semibold text-sm">LangSmith 可观测状态</p>
        <Button variant="outline" onClick={handleLoadObs}>
          刷新状态
        </Button>
        {obs && (
          <div className="text-sm text-foreground">
            <p>enabled: {String(obs.enabled)}</p>
            <p>project: {obs.project}</p>
          </div>
        )}
      </Card>

      {error && <ErrorMessage message={error} />}
    </div>
  )
}

export default AuthCenter
