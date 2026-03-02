const { CATEGORY_MAP } = require('../../utils/util')

Component({
  properties: {
    selected: { type: String, value: '' },
  },
  data: {
    categories: [],
  },
  lifetimes: {
    attached() {
      const list = Object.entries(CATEGORY_MAP).map(([id, info]) => ({ id, ...info }))
      this.setData({ categories: list })
    },
  },
  methods: {
    onSelect(e) {
      const id = e.currentTarget.dataset.id
      this.triggerEvent('change', { id })
    },
  },
})
