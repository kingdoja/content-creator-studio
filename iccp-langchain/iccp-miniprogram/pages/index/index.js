const { getContentHistory } = require('../../utils/api')
const { getCategoryInfo, formatRelativeTime, truncate } = require('../../utils/util')

Page({
  data: {
    greeting: '',
    recentItems: [],
    quickActions: [
      { id: 'chat', icon: '💬', title: 'AI 对话', desc: '多轮智能创作对话', url: '/pages/chat/chat' },
      { id: 'write', icon: '✍️', title: '内容创作', desc: '7大板块一键生成', url: '/pages/writing/writing' },
      { id: 'cover', icon: '🎨', title: '封面生成', desc: 'AI生成文章封面图', url: '/pages/cover/cover' },
      { id: 'video', icon: '🎬', title: '视频生成', desc: 'AI剧情润色+文生视频', url: '/pages/video/video' },
      { id: 'history', icon: '📋', title: '历史记录', desc: '查看过往创作内容', url: '/pages/history/history' },
    ],
  },

  onLoad() {
    this.setGreeting()
  },

  onShow() {
    this.loadRecentHistory()
  },

  setGreeting() {
    const h = new Date().getHours()
    let greeting = '晚上好'
    if (h < 6) greeting = '夜深了'
    else if (h < 12) greeting = '早上好'
    else if (h < 14) greeting = '中午好'
    else if (h < 18) greeting = '下午好'
    this.setData({ greeting })
  },

  async loadRecentHistory() {
    try {
      const res = await getContentHistory(5)
      const items = (res.items || []).map((item) => ({
        ...item,
        categoryInfo: getCategoryInfo(item.category),
        timeLabel: formatRelativeTime(item.created_at),
        topicShort: truncate(item.topic, 24),
      }))
      this.setData({ recentItems: items })
    } catch {
      // 首页静默失败
    }
  },

  onCategoryChange(e) {
    const { id } = e.detail
    wx.navigateTo({ url: `/pages/writing/writing?category=${id}` })
  },

  onQuickAction(e) {
    const url = e.currentTarget.dataset.url
    if (url) {
      if (url.startsWith('/pages/chat/') || url.startsWith('/pages/writing/')) {
        wx.switchTab({ url })
      } else {
        wx.navigateTo({ url })
      }
    }
  },

  onRecentTap(e) {
    const id = e.currentTarget.dataset.id
    if (id) wx.navigateTo({ url: `/pages/detail/detail?id=${id}` })
  },
})
