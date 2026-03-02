const { getContentHistory } = require('../../utils/api')
const { logout } = require('../../utils/auth')
const { showToast } = require('../../utils/util')

Page({
  data: {
    userInfo: null,
    stats: { totalCreations: 0 },
    menuItems: [
      { id: 'history', icon: '📋', title: '创作记录', url: '/pages/history/history' },
      { id: 'about', icon: 'ℹ️', title: '关于平台', desc: 'ICCP 多Agent智能创作' },
    ],
  },

  onShow() {
    const app = getApp()
    const userInfo = app.getUserInfo()
    this.setData({ userInfo })
    this.loadStats()
  },

  async loadStats() {
    try {
      const res = await getContentHistory(50)
      this.setData({ 'stats.totalCreations': res?.items?.length || 0 })
    } catch {
      // 静默
    }
  },

  onMenuTap(e) {
    const url = e.currentTarget.dataset.url
    if (url) wx.navigateTo({ url })
  },

  async handleLogin() {
    try {
      const app = getApp()
      await app.silentLogin()
      const userInfo = app.getUserInfo()
      this.setData({ userInfo })
      showToast('登录成功')
    } catch (e) {
      showToast(e.message || '登录失败')
    }
  },

  handleLogout() {
    wx.showModal({
      title: '确认退出',
      content: '退出后需要重新登录',
      success: (res) => {
        if (res.confirm) {
          logout()
          this.setData({ userInfo: null })
          showToast('已退出登录')
        }
      },
    })
  },
})
