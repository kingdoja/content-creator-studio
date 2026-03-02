import { buildAuthHeaders } from './client'

export const streamSseJson = async (
  url,
  data,
  { onStart, onNodeUpdate, onContentChunk, onComplete, onError } = {}
) => {
  const response = await fetch(url, {
    method: 'POST',
    headers: buildAuthHeaders({
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
      'Cache-Control': 'no-cache',
    }),
    body: JSON.stringify(data),
  })

  if (!response.ok || !response.body) {
    const text = await response.text().catch(() => '')
    throw new Error(text || '流式请求失败')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  const parseEventBlock = (block) => {
    const lines = block.split(/\r?\n/)
    let eventName = 'message'
    let payload = ''
    lines.forEach((line) => {
      if (line.startsWith('event:')) eventName = line.slice(6).trim()
      if (line.startsWith('data:')) payload += line.slice(5).trim()
    })
    if (!payload) return null
    try {
      return { eventName, data: JSON.parse(payload) }
    } catch {
      return { eventName, data: { raw: payload } }
    }
  }

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const blocks = buffer.split(/\r?\n\r?\n/)
    buffer = blocks.pop() || ''
    for (const block of blocks) {
      const parsed = parseEventBlock(block)
      if (!parsed) continue
      const { eventName, data: payload } = parsed
      if (eventName === 'start') onStart?.(payload)
      else if (eventName === 'node_update') onNodeUpdate?.(payload)
      else if (eventName === 'content_chunk') onContentChunk?.(payload)
      else if (eventName === 'complete') onComplete?.(payload)
      else if (eventName === 'error') onError?.(payload)
    }
  }
}
