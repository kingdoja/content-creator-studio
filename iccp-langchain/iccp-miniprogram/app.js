const { login, checkSession } = require('./utils/auth')
const { API_BASE, MODE } = require('./utils/env')

App({
  globalData: {
    userInfo: null,
    token: null,
    // API 地址统一从 utils/env.js 读取，避免多处手改
    apiBase: API_BASE,
  },

  onLaunch() {
    console.info('[api env]', MODE, this.globalData.apiBase)
    this.initAuth()
  },

  async initAuth() {
    try {
      const token = wx.getStorageSync('token')
      const userInfo = wx.getStorageSync('userInfo')
      if (token && userInfo) {
        this.globalData.token = token
        this.globalData.userInfo = userInfo
        const valid = await checkSession()
        if (!valid) await this.silentLogin()
      } else {
        await this.silentLogin()
      }
    } catch {
      await this.silentLogin()
    }
  },

  async silentLogin() {
    try {
      const res = await login()
      if (res && res.token) {
        this.globalData.token = res.token
        this.globalData.userInfo = res.user
        wx.setStorageSync('token', res.token)
        wx.setStorageSync('userInfo', res.user)
      }
    } catch (err) {
      console.warn('silent login failed', err)
    }
  },

  getToken() {
    return this.globalData.token || wx.getStorageSync('token') || ''
  },

  getUserInfo() {
    return this.globalData.userInfo || wx.getStorageSync('userInfo') || null
  },
})
