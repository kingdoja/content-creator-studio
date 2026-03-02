const { startStoryVideo, getVideoTaskStatus, toAbsoluteApiUrl } = require('../../utils/api')
const { showToast } = require('../../utils/util')

Page({
  data: {
    inputText: '',
    canGenerate: false,
    genreIndex: 0,
    genreOptions: ['sci-fi', 'fantasy', 'documentary', 'drama', 'action'],
    genreLabels: ['科幻', '奇幻', '纪录片', '剧情', '动作'],
    moodIndex: 0,
    moodOptions: ['epic', 'calm', 'tense', 'dreamy', 'dark'],
    moodLabels: ['史诗', '平静', '紧张', '梦幻', '暗黑'],
    loading: false,
    polling: false,
    progress: 0,
    statusText: '',
    result: null,
    showResult: false,
    errorMsg: '',
  },

  _pollTimer: null,

  onUnload() {
    this._clearPoll()
  },

  _clearPoll() {
    if (this._pollTimer) {
      clearTimeout(this._pollTimer)
      this._pollTimer = null
    }
  },

  onInputText(e) {
    const v = e.detail.value || ''
    this.setData({ inputText: v, canGenerate: v.trim().length > 0 })
  },

  onGenreChange(e) {
    this.setData({ genreIndex: e.detail.value })
  },

  onMoodChange(e) {
    this.setData({ moodIndex: e.detail.value })
  },

  async handleGenerate() {
    if (!this.data.inputText.trim() || this.data.loading) return
    this.setData({
      loading: true,
      polling: false,
      progress: 0,
      statusText: '正在润色剧情...',
      showResult: false,
      result: null,
      errorMsg: '',
    })

    try {
      const res = await startStoryVideo({
        input_text: this.data.inputText.trim(),
        genre: this.data.genreOptions[this.data.genreIndex],
        mood: this.data.moodOptions[this.data.moodIndex],
        duration_seconds: 8,
        aspect_ratio: '16:9',
      })

      if (!res.success) {
        this.setData({ loading: false, errorMsg: res.error || '视频任务创建失败', showResult: true })
        return
      }

      const storyline = res.storyline || ''
      const videoUrl = toAbsoluteApiUrl(res.video_url || '')
      const taskId = res.task_id || ''

      if (videoUrl) {
        this.setData({
          loading: false,
          result: { storyline, videoUrl, provider: res.provider || '', model: res.model || '' },
          showResult: true,
        })
        return
      }

      if (taskId) {
        this.setData({ polling: true, statusText: '视频生成中...', progress: 10 })
        this._pollTaskStatus(taskId, storyline, res.provider, res.model)
      } else {
        this.setData({
          loading: false,
          result: { storyline, videoUrl: '', provider: res.provider || '', model: res.model || '' },
          showResult: true,
        })
      }
    } catch (e) {
      this.setData({ loading: false, errorMsg: e.message || '请求失败', showResult: true })
    }
  },

  _pollTaskStatus(taskId, storyline, provider, model) {
    const poll = async () => {
      try {
        const res = await getVideoTaskStatus(taskId, provider || 'seedance')
        const progress = res.progress_percent || this.data.progress
        this.setData({ progress: Math.max(this.data.progress, progress) })

        if (res.status === 'completed' || res.status === 'success') {
          this.setData({
            loading: false,
            polling: false,
            progress: 100,
            result: {
              storyline,
              videoUrl: toAbsoluteApiUrl(res.video_url || ''),
              provider: provider || '',
              model: model || '',
            },
            showResult: true,
          })
          return
        }

        if (res.status === 'failed' || res.status === 'error') {
          this.setData({
            loading: false,
            polling: false,
            errorMsg: res.error || '视频生成失败',
            showResult: true,
          })
          return
        }

        this.setData({ statusText: `视频生成中 ${progress}%...` })
        this._pollTimer = setTimeout(poll, 3000)
      } catch (e) {
        this.setData({
          loading: false,
          polling: false,
          errorMsg: '查询任务状态失败：' + (e.message || ''),
          showResult: true,
        })
      }
    }
    this._pollTimer = setTimeout(poll, 3000)
  },

  handleReset() {
    this._clearPoll()
    this.setData({
      showResult: false,
      result: null,
      errorMsg: '',
      inputText: '',
      canGenerate: false,
      loading: false,
      polling: false,
      progress: 0,
      statusText: '',
    })
  },
})
