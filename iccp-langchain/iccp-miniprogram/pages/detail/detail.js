const { getContentDetail } = require('../../utils/api')
const { getCategoryInfo, formatTime, showToast } = require('../../utils/util')

Page({
  data: {
    item: null,
    loading: true,
  },

  onLoad(options) {
    if (options.id) this.loadDetail(options.id)
    else { showToast('缺少记录ID'); wx.navigateBack() }
  },

  async loadDetail(id) {
    try {
      const res = await getContentDetail(id)
      if (res.success && res.item) {
        const item = res.item
        item.cat = getCategoryInfo(item.category)
        item.timeLabel = item.created_at ? formatTime(item.created_at) : ''
        this.setData({ item, loading: false })
        wx.setNavigationBarTitle({ title: item.topic || '内容详情' })
      } else {
        showToast('记录不存在')
        wx.navigateBack()
      }
    } catch (e) {
      showToast(e.message || '加载失败')
      this.setData({ loading: false })
    }
  },

  handleCopy() {
    if (!this.data.item?.content) return
    wx.setClipboardData({
      data: this.data.item.content,
      success: () => showToast('已复制到剪贴板'),
    })
  },

  handleShare() {
    // 微信小程序原生分享在 onShareAppMessage 中处理
  },

  onShareAppMessage() {
    const item = this.data.item
    return {
      title: item?.topic || 'ICCP智能创作',
      path: `/pages/detail/detail?id=${item?.id || ''}`,
    }
  },
})
