function formatTime(date) {
  if (typeof date === 'string') date = new Date(date)
  const y = date.getFullYear()
  const m = (date.getMonth() + 1).toString().padStart(2, '0')
  const d = date.getDate().toString().padStart(2, '0')
  const h = date.getHours().toString().padStart(2, '0')
  const min = date.getMinutes().toString().padStart(2, '0')
  return `${y}-${m}-${d} ${h}:${min}`
}

function formatRelativeTime(dateStr) {
  if (!dateStr) return ''
  const diff = Date.now() - new Date(dateStr).getTime()
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  if (diff < 604800000) return `${Math.floor(diff / 86400000)}天前`
  return formatTime(new Date(dateStr))
}

function truncate(str, len = 50) {
  if (!str) return ''
  return str.length > len ? str.slice(0, len) + '...' : str
}

function showToast(title, icon = 'none') {
  wx.showToast({ title, icon, duration: 2000 })
}

function showLoading(title = '加载中...') {
  wx.showLoading({ title, mask: true })
}

function hideLoading() {
  wx.hideLoading()
}

const CATEGORY_MAP = {
  finance:    { name: '财经',     icon: '💰', color: '#f59e0b' },
  ai:         { name: '人工智能', icon: '🤖', color: '#6366f1' },
  lifestyle:  { name: '生活',     icon: '🌿', color: '#10b981' },
  tech:       { name: '科技',     icon: '💻', color: '#3b82f6' },
  books:      { name: '书籍',     icon: '📚', color: '#8b5cf6' },
  investment: { name: '投资',     icon: '📈', color: '#ef4444' },
  growth:     { name: '成长',     icon: '🚀', color: '#ec4899' },
}

function getCategoryInfo(id) {
  return CATEGORY_MAP[id] || { name: id, icon: '📝', color: '#6b7280' }
}

module.exports = {
  formatTime, formatRelativeTime, truncate,
  showToast, showLoading, hideLoading,
  CATEGORY_MAP, getCategoryInfo,
}
