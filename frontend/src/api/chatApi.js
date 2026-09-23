import axiosInstance from './axiosInstance'

/**
 * GET /chatbot/threads
 */
export const getThreads = async () => {
  const { data } = await axiosInstance.get('/chatbot/threads')
  return data
}

/**
 * GET /chatbot/history/{thread_id}
 */
export const getHistory = async (threadId) => {
  const { data } = await axiosInstance.get(`/chatbot/history/${threadId}`)
  return data
}

/**
 * POST /chatbot/new-chat
 */
export const newChat = async () => {
  const { data } = await axiosInstance.post('/chatbot/new-chat')
  return data
}

/**
 * DELETE /chatbot/delete-chat/{thread_id}
 */
export const deleteChat = async (threadId) => {
  await axiosInstance.delete(`/chatbot/delete-chat/${threadId}`)
}

// ─── SSE helpers ─────────────────────────────────────────────────────────────

function getAuthHeaders() {
  const token = localStorage.getItem('access_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

function handleUnauthorized() {
  localStorage.removeItem('access_token')
  localStorage.removeItem('user')
  window.location.href = '/login'
}

/**
 * Parse a raw SSE stream and dispatch events to callbacks.
 * Returns when the stream ends or the signal is aborted.
 */
async function consumeSSE(response, { onToken, onMetadata, onInterrupt, onError, onStatus }) {
  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  try {
    while (true) {
      const { value, done } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n\n')
      buffer = parts.pop() // keep incomplete tail

      for (const part of parts) {
        if (!part.trim()) continue

        let eventType = 'message'
        let dataLine = ''

        for (const line of part.split('\n')) {
          if (line.startsWith('event: ')) eventType = line.slice(7).trim()
          else if (line.startsWith('data: ')) dataLine = line.slice(6).trim()
        }

        if (!dataLine) continue

        try {
          const parsed = JSON.parse(dataLine)
          if (eventType === 'token')     onToken(parsed.token ?? '')
          else if (eventType === 'status')    onStatus?.(parsed.message ?? '')
          else if (eventType === 'metadata')  onMetadata(parsed)
          else if (eventType === 'interrupt') onInterrupt(parsed)
          else if (eventType === 'error')     onError(parsed.message ?? 'An error occurred')
        } catch { /* malformed JSON — skip */ }
      }
    }
  } catch (err) {
    if (err.name === 'AbortError') {
      // User cancelled — release the reader and return cleanly
      try { reader.cancel() } catch { /* ignore */ }
      return
    }
    throw err
  }
}

/**
 * POST /chatbot/chat — streaming SSE
 *
 * @param {string}        query
 * @param {string|null}   threadId
 * @param {function}      onToken
 * @param {function}      onMetadata
 * @param {function}      onInterrupt
 * @param {function}      onError
 * @param {function}      onStatus
 * @param {AbortSignal}   signal       — pass AbortController.signal to cancel
 */
export const streamChat = async (
  query, threadId,
  onToken, onMetadata, onInterrupt, onError, onStatus,
  signal,
) => {
  let response
  try {
    response = await fetch('/api/chatbot/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body: JSON.stringify({ query, thread_id: threadId || null }),
      signal,
    })
  } catch (err) {
    if (err.name === 'AbortError') return   // cancelled before response — exit cleanly
    onError(`Network error: ${err.message}`)
    return
  }

  if (!response.ok) {
    if (response.status === 401) { handleUnauthorized(); return }
    onError(`Request failed with status ${response.status}`)
    return
  }

  await consumeSSE(response, { onToken, onMetadata, onInterrupt, onError, onStatus })
}

/**
 * POST /chatbot/review/{thread_id} — streaming SSE resume
 */
export const reviewChat = async (
  threadId, approved, feedback,
  onToken, onMetadata, onInterrupt, onError, onStatus,
) => {
  let response
  try {
    response = await fetch(`/api/chatbot/review/${threadId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body: JSON.stringify({ approved, feedback }),
    })
  } catch (err) {
    if (err.name === 'AbortError') return
    onError(`Network error: ${err.message}`)
    return
  }

  if (!response.ok) {
    if (response.status === 401) { handleUnauthorized(); return }
    onError(`Review request failed with status ${response.status}`)
    return
  }

  await consumeSSE(response, { onToken, onMetadata, onInterrupt, onError, onStatus })
}
