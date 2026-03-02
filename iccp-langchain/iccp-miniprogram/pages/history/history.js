const { getContentHistory } = require('../../utils/api')
const { getCategoryInfo, formatRelativeTime, truncate, showToast } = require('../../utils/util')

Page({
  data: {
    items: [],
    loading: false,
    empty: false,
  },

  onLoad() {
    this.loadHistory()
  },

  onPullDownRefresh() {
    this.loadHistory().then(() => wx.stopPullDownRefresh())
  },

  async loadHistory() {
    this.setData({ loading: true })
    try {
      const res = await getContentHistory(30)
      const items = (res.items || []).map((item) => ({
        ...item,
        cat: getCategoryInfo(item.category),
        timeLabel: formatRelativeTime(item.created_at),
        topicShort: truncate(item.topic, 30),
      }))
      this.setData({ items, empty: items.length === 0 })
    } catch (e) {
      showToast(e.message || '加载失败')
    } finally {
      this.setData({ loading: false })
    }
  },

  onItemTap(e) {
    const id = e.currentTarget.dataset.id
    if (id) wx.navigateTo({ url: `/pages/detail/detail?id=${id}` })
  },
})
