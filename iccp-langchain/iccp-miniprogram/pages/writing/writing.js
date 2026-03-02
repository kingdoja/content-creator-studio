const { createContent } = require('../../utils/api')
const { getCategoryInfo, showToast } = require('../../utils/util')

Page({
  data: {
    category: 'ai',
    categoryName: '人工智能',
    topic: '',
    requirements: '',
    lengthIndex: 1,
    lengthOptions: ['short', 'medium', 'long'],
    lengthLabels: ['短篇', '中篇', '长篇'],
    styleIndex: 1,
    styleOptions: ['casual', 'professional'],
    styleLabels: ['轻松', '专业'],
    loading: false,
    canGenerate: false,
    result: null,
    showResult: false,
    errorMsg: '',
  },

  onLoad(options) {
    if (options.category) {
      const info = getCategoryInfo(options.category)
      this.setData({ category: options.category, categoryName: info.name })
    }
  },

  onCategoryChange(e) {
    const id = e.detail.id
    const info = getCategoryInfo(id)
    this.setData({ category: id, categoryName: info.name })
  },

  onTopicInput(e) {
    const topic = e.detail.value || ''
    this.setData({
      topic,
      canGenerate: topic.trim().length > 0,
    })
  },

  onRequirementsInput(e) {
    this.setData({ requirements: e.detail.value })
  },

  onLengthChange(e) {
    this.setData({ lengthIndex: e.detail.value })
  },

  onStyleChange(e) {
    this.setData({ styleIndex: e.detail.value })
  },

  async handleGenerate() {
    if (!this.data.topic.trim()) {
      showToast('请输入创作主题')
      return
    }
    if (this.data.loading) return

    this.setData({ loading: true, showResult: false, result: null, errorMsg: '' })

    try {
      const res = await createContent({
        category: this.data.category,
        topic: this.data.topic.trim(),
        requirements: this.data.requirements.trim() || undefined,
        length: this.data.lengthOptions[this.data.lengthIndex],
        style: this.data.styleOptions[this.data.styleIndex],
      })

      const content = res.content || ''
      if (res.success && content) {
        this.setData({
          loading: false,
          result: {
            content,
            agent: res.agent || '',
            toolsUsed: res.tools_used || [],
            iterations: res.iterations || 0,
          },
          showResult: true,
        })
      } else {
        this.setData({
          loading: false,
          errorMsg: res.error || '生成失败，请重试',
          showResult: true,
        })
      }
    } catch (e) {
      this.setData({
        loading: false,
        errorMsg: e.message || '请求超时或网络异常，请重试',
        showResult: true,
      })
    }
  },

  handleCopy() {
    if (!this.data.result?.content) return
    wx.setClipboardData({
      data: this.data.result.content,
      success: () => showToast('已复制到剪贴板'),
    })
  },

  handleReset() {
    this.setData({
      showResult: false,
      result: null,
      errorMsg: '',
      topic: '',
      requirements: '',
      canGenerate: false,
    })
  },
})
