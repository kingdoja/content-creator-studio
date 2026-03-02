const api = require('./api')

function wxLoginCode() {
  return new Promise((resolve, reject) => {
    wx.login({
      success: (res) => {
        if (res.code) resolve(res.code)
        else reject(new Error('wx.login 获取 code 失败'))
      },
      fail: (err) => reject(new Error(err.errMsg || 'wx.login 调用失败')),
    })
  })
}

async function login() {
  const code = await wxLoginCode()
  const res = await api.wxLogin(code)
  if (res.success && res.access_token) {
    return { token: res.access_token, user: res.user || {} }
  }
  throw new Error(res.detail || '微信登录失败')
}

function checkSession() {
  return new Promise((resolve) => {
    wx.checkSession({
      success: () => resolve(true),
      fail: () => resolve(false),
    })
  })
}

function logout() {
  wx.removeStorageSync('token')
  wx.removeStorageSync('userInfo')
  const app = getApp()
  if (app?.globalData) {
    app.globalData.token = null
    app.globalData.userInfo = null
  }
}

module.exports = { login, checkSession, logout }
