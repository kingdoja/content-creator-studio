const {
  createChatSession, listChatSessions, getChatMessages,
  sendChatMessage, deleteChatSession,
} = require('../../utils/api')
const { showToast } = require('../../utils/util')

Page({
  data: {
    messages: [],
    sessions: [],
    sessionId: '',
    currentTitle: '新会话',
    inputValue: '',
    loading: false,
    scrollToView: '',
    showSessionPicker: false,
  },

  onLoad() {
    this.initSessions()
  },

  async initSessions() {
    try {
      const res = await listChatSessions({ module: 'chat', limit: 20 })
      const list = res?.sessions || []
      if (list.length > 0) {
        this.setData({ sessions: list, sessionId: list[0].id, currentTitle: list[0].title || '新会话' })
        await this.loadMessages(list[0].id)
      } else {
        await this.handleNewSession(true)
      }
    } catch (e) {
      showToast(e.message || '加载会话失败')
    }
  },

  async loadMessages(sid) {
    try {
      const res = await getChatMessages(sid, 80)
      const msgs = (res?.messages || []).map((m) => ({
        role: m.role,
        text: m.content || '',
        agent: m.metadata?.agent || '',
      }))
      this.setData({ messages: msgs })
      this.scrollToBottom()
    } catch (e) {
      showToast(e.message || '加载消息失败')
    }
  },

  async handleNewSession(silent) {
    try {
      const res = await createChatSession({ module: 'chat', title: '新会话' })
      const sid = res?.session?.id
      if (!sid) return
      const refresh = await listChatSessions({ module: 'chat', limit: 20 })
      this.setData({
        sessions: refresh?.sessions || [],
        sessionId: sid,
        currentTitle: '新会话',
        messages: [],
      })
      if (!silent) showToast('已创建新会话')
    } catch (e) {
      showToast(e.message || '创建会话失败')
    }
  },

  async handleSend() {
    const content = this.data.inputValue.trim()
    if (!content || this.data.loading) return

    let sid = this.data.sessionId
    if (!sid) {
      try {
        const res = await createChatSession({ module: 'chat', title: '新会话' })
        sid = res?.session?.id
        if (!sid) { showToast('会话创建失败'); return }
        this.setData({ sessionId: sid })
      } catch (e) {
        showToast(e.message); return
      }
    }

    const msgs = [
      ...this.data.messages,
      { role: 'user', text: content },
      { role: 'assistant', text: '正在思考中...' },
    ]
    this.setData({ messages: msgs, inputValue: '', loading: true })
    this.scrollToBottom()

    try {
      const hasAction = /帮我|帮忙|具体|详细|方案|设计|规划|分析|写一|做一|想一|给我|生成|创建|总结|怎么做|步骤|流程|计划/.test(content)
      const isSimple = !hasAction && (
        content.length <= 10
        || (content.length <= 20 && /^(嗨|你好|hi|hello|hey|谢谢|thanks|ok|好的|嗯|哈哈)/i.test(content))
      )
      const res = await sendChatMessage(sid, {
        content,
        category: 'ai',
        style: 'casual',
        length: isSimple ? 'short' : 'medium',
        use_memory: false,
        memory_top_k: 1,
        force_simple: isSimple,
      })

      const reply = res?.assistant?.content || res?.content || '生成失败，请重试'
      const agent = res?.assistant?.agent || res?.agent || ''
      const updated = [...this.data.messages]
      updated[updated.length - 1] = { role: 'assistant', text: reply, agent }
      this.setData({ messages: updated })
      this.scrollToBottom()
      this._refreshSessionTitle(sid, content)
    } catch (e) {
      const updated = [...this.data.messages]
      updated[updated.length - 1] = { role: 'assistant', text: `请求失败: ${e.message}` }
      this.setData({ messages: updated })
    } finally {
      this.setData({ loading: false })
    }
  },

  onInputChange(e) {
    this.setData({ inputValue: e.detail.value })
  },

  onInputConfirm() {
    this.handleSend()
  },

  toggleSessionPicker() {
    this.setData({ showSessionPicker: !this.data.showSessionPicker })
  },

  async onSelectSession(e) {
    const sid = e.currentTarget.dataset.id
    const found = this.data.sessions.find((s) => s.id === sid)
    this.setData({ sessionId: sid, showSessionPicker: false, currentTitle: found?.title || '新会话' })
    await this.loadMessages(sid)
  },

  async onDeleteSession(e) {
    const sid = e.currentTarget.dataset.id
    if (!sid) return
    const target = this.data.sessions.find((s) => s.id === sid)
    const title = target?.title || '该会话'
    const ok = await this._confirmDelete(`确认删除“${title}”？删除后不可恢复。`)
    if (!ok) return
    await this._deleteSessionById(sid)
  },

  _confirmDelete(content) {
    return new Promise((resolve) => {
      wx.showModal({
        title: '删除会话',
        content,
        confirmText: '删除',
        confirmColor: '#ef4444',
        success: (res) => resolve(!!res.confirm),
        fail: () => resolve(false),
      })
    })
  },

  async _deleteSessionById(sid) {
    try {
      await deleteChatSession(sid)
      showToast('会话已删除')
      this.setData({ showSessionPicker: false })
      await this.initSessions()
    } catch (e) {
      showToast(e.message || '删除失败')
    }
  },

  _refreshSessionTitle(sid, firstMsg) {
    const sessions = [...this.data.sessions]
    const idx = sessions.findIndex((s) => s.id === sid)
    if (idx === -1) return
    if (sessions[idx].title && sessions[idx].title !== '新会话') return
    let summary = firstMsg.replace(/\n/g, ' ').trim()
    if (summary.length > 20) summary = summary.slice(0, 20) + '...'
    sessions[idx].title = summary
    const update = { sessions }
    if (sid === this.data.sessionId) update.currentTitle = summary
    this.setData(update)
  },

  scrollToBottom() {
    const id = `msg-${this.data.messages.length - 1}`
    this.setData({ scrollToView: id })
  },
})
