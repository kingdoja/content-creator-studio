const { generateCover, toAbsoluteApiUrl } = require('../../utils/api')
const { showToast } = require('../../utils/util')

Page({
  data: {
    title: '',
    canGenerate: false,
    styleIndex: 0,
    styleOptions: ['cinematic', 'illustration', 'minimal', 'abstract'],
    styleLabels: ['电影感', '插画', '极简', '抽象'],
    toneIndex: 0,
    toneOptions: ['bright', 'dark', 'warm', 'cool'],
    toneLabels: ['明亮', '暗调', '暖色', '冷色'],
    loading: false,
    result: null,
    showResult: false,
    errorMsg: '',
  },

  onLoad(options) {
    if (options.title) {
      this.setData({ title: options.title, canGenerate: true })
    }
  },

  onTitleInput(e) {
    const title = e.detail.value || ''
    this.setData({ title, canGenerate: title.trim().length > 0 })
  },

  onStyleChange(e) {
    this.setData({ styleIndex: e.detail.value })
  },

  onToneChange(e) {
    this.setData({ toneIndex: e.detail.value })
  },

  async handleGenerate() {
    if (!this.data.title.trim() || this.data.loading) return
    this.setData({ loading: true, showResult: false, result: null, errorMsg: '' })

    try {
      const res = await generateCover({
        title: this.data.title.trim(),
        style: this.data.styleOptions[this.data.styleIndex],
        tone: this.data.toneOptions[this.data.toneIndex],
      })

      if (res.success && res.image_url) {
        const imageUrl = toAbsoluteApiUrl(res.image_url)
        this.setData({
          loading: false,
          result: {
            imageUrl,
            promptUsed: res.prompt_used || '',
            model: res.model || '',
            latencyMs: res.latency_ms || 0,
          },
          showResult: true,
        })
      } else {
        this.setData({
          loading: false,
          errorMsg: res.error || '封面生成失败',
          showResult: true,
        })
      }
    } catch (e) {
      this.setData({
        loading: false,
        errorMsg: e.message || '请求失败',
        showResult: true,
      })
    }
  },

  handleSaveImage() {
    const url = this.data.result?.imageUrl
    if (!url) return
    wx.getImageInfo({
      src: url,
      success: (info) => {
        wx.saveImageToPhotosAlbum({
          filePath: info.path,
          success: () => showToast('已保存到相册'),
          fail: () => showToast('保存失败，请授权相册权限'),
        })
      },
      fail: () => showToast('图片加载失败'),
    })
  },

  handleReset() {
    this.setData({ showResult: false, result: null, errorMsg: '', title: '', canGenerate: false })
  },
})
