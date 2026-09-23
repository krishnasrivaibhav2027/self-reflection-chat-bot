import {
  Bot,
  Check,
  CheckCircle,
  Clock,
  Copy,
  RotateCcw,
  Send, Square,
  Tag,
  User,
  Zap,
} from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { getHistory, reviewChat, streamChat } from '../api/chatApi'
import { useAuth } from '../context/AuthContext'

// ─── Dynamic greeting ────────────────────────────────────────────────────────
const getGreeting = (firstName) => {
  const hour = new Date().getHours()
  if (hour >= 5 && hour < 12) return `Good morning, ${firstName} ☀️`
  if (hour >= 12 && hour < 17) return `Good afternoon, ${firstName} 👋`
  if (hour >= 17 && hour < 21) return `Good evening, ${firstName} 🌆`
  return `Hey, ${firstName} 🌙 burning the midnight oil?`
}

const getSubGreeting = () => {
  const hour = new Date().getHours()
  if (hour >= 5 && hour < 12) return 'Ready to write some great code today?'
  if (hour >= 12 && hour < 17) return 'How can I help you this afternoon?'
  if (hour >= 17 && hour < 21) return "Let's get some work done this evening."
  return "What are we building tonight?"
}

const formatTime = (ms) => (ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`)

// ─── Metadata bar ─────────────────────────────────────────────────────────────
const MessageMeta = ({ meta }) => {
  if (!meta) return null
  const { total_tokens, execution_time_ms, intent } = meta
  return (
    <div className="msg-meta">
      {intent && (
        <span className={`msg-meta__badge msg-meta__badge--${intent.toLowerCase()}`}>
          <Tag size={10} />{intent}
        </span>
      )}
      {total_tokens != null && (
        <span className="msg-meta__stat"><Zap size={11} />{total_tokens.toLocaleString()} tokens</span>
      )}
      {execution_time_ms != null && (
        <span className="msg-meta__stat"><Clock size={11} />{formatTime(execution_time_ms)}</span>
      )}
    </div>
  )
}

// ─── Code block ───────────────────────────────────────────────────────────────
const CodeBlock = ({ children, className }) => {
  const [copied, setCopied] = useState(false)
  const code = String(children).replace(/\n$/, '')
  const language = className?.replace('language-', '') || ''
  const handleCopy = () => {
    navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <div className="code-block-wrapper">
      <div className="code-block-header">
        <span className="code-block-lang">{language}</span>
        <button className="code-copy-btn" onClick={handleCopy} aria-label="Copy code">
          {copied ? <Check size={13} /> : <Copy size={13} />}
          <span>{copied ? 'Copied' : 'Copy'}</span>
        </button>
      </div>
      <pre className="code-block-pre"><code>{code}</code></pre>
    </div>
  )
}

// ─── Chat bubble ──────────────────────────────────────────────────────────────
const ChatBubble = ({ message }) => {
  const isUser = message.role === 'user'
  return (
    <div className={`chat-bubble ${isUser ? 'chat-bubble--user' : 'chat-bubble--assistant'}`}>
      <div className="chat-bubble__avatar" aria-hidden="true">
        {isUser ? <User size={15} /> : <Bot size={15} />}
      </div>
      <div className="chat-bubble__body">
        {isUser ? (
          <p className="chat-bubble__text">{message.content}</p>
        ) : (
          <div className="chat-bubble__markdown">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                code({ node, inline, className, children, ...props }) {
                  if (inline) return <code className="inline-code" {...props}>{children}</code>
                  return <CodeBlock className={className}>{children}</CodeBlock>
                },
              }}
            >
              {message.content}
            </ReactMarkdown>
          </div>
        )}
        {!isUser && message.meta && <MessageMeta meta={message.meta} />}
        {message.timestamp && (
          <span className="chat-bubble__time">
            {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
        )}
      </div>
    </div>
  )
}

// ─── Typing indicator ─────────────────────────────────────────────────────────
const TypingIndicator = () => (
  <div className="chat-bubble chat-bubble--assistant">
    <div className="chat-bubble__avatar" aria-hidden="true"><Bot size={15} /></div>
    <div className="chat-bubble__body">
      <div className="typing-indicator"><span /><span /><span /></div>
    </div>
  </div>
)

// ─── Status bubble: shown while code is being generated + tested ──────────────
const StatusBubble = ({ message }) => {
  const isTesting = message.includes('🧪') || message.toLowerCase().includes('test')
  return (
    <div className="chat-bubble chat-bubble--assistant">
      <div className="chat-bubble__avatar" aria-hidden="true"><Bot size={15} /></div>
      <div className="chat-bubble__body">
        <div className={`status-bubble ${isTesting ? 'status-bubble--testing' : ''}`}>
          <div className="status-bubble__spinner" />
          <span>{message}</span>
        </div>
      </div>
    </div>
  )
}

// ─── Human Review Panel ───────────────────────────────────────────────────────
const ReviewPanel = ({ interruptData, onSubmit, disabled }) => {
  const [feedback, setFeedback] = useState('')
  const { generated_code, test_results, tests_passed, message } = interruptData

  // Strip outer markdown fences for the code preview since CodeBlock adds its own
  const rawCode = generated_code
    .replace(/^```(?:python|py)?\n?/, '')
    .replace(/\n?```$/, '')
    .trim()

  return (
    <div className="review-panel">
      <div className="review-panel__header">
        <Bot size={16} />
        <span>Code Review Required</span>
        <span className={`review-panel__badge ${tests_passed ? 'review-panel__badge--pass' : 'review-panel__badge--fail'}`}>
          {tests_passed ? '✓ Tests passed' : '✗ Tests failed'}
        </span>
      </div>

      <p className="review-panel__message">{message}</p>

      <div className="review-panel__section">
        <p className="review-panel__section-label">Generated Code</p>
        <CodeBlock className="language-python">{rawCode}</CodeBlock>
      </div>

      {test_results && (
        <div className="review-panel__section">
          <p className="review-panel__section-label">Test Results</p>
          <pre className="review-panel__test-output">{test_results}</pre>
        </div>
      )}

      <div className="review-panel__section">
        <p className="review-panel__section-label">Feedback (optional — used if you reject)</p>
        <textarea
          className="review-panel__feedback"
          placeholder="e.g. Add edge-case handling for empty input, use type hints…"
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          rows={3}
          disabled={disabled}
        />
      </div>

      <div className="review-panel__actions">
        <button
          className="review-btn review-btn--approve"
          onClick={() => onSubmit(true, '')}
          disabled={disabled}
        >
          <CheckCircle size={15} />
          Approve &amp; Finalize
        </button>
        <button
          className="review-btn review-btn--reject"
          onClick={() => onSubmit(false, feedback)}
          disabled={disabled}
        >
          <RotateCcw size={15} />
          Reject &amp; Regenerate
        </button>
      </div>
    </div>
  )
}

// ─── Main ChatArea ────────────────────────────────────────────────────────────
const ChatArea = ({ threadId, onThreadCreated }) => {
  const { user } = useAuth()
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [streamingContent, setStreamingContent] = useState('')
  const [statusMessage, setStatusMessage] = useState('')   // pipeline status text
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [interruptData, setInterruptData] = useState(null)
  const [reviewSubmitting, setReviewSubmitting] = useState(false)
  const [activeThreadId, setActiveThreadId] = useState(threadId)

  const abortRef = useRef(false)
  const abortControllerRef = useRef(null)  // AbortController for the fetch request
  const interruptRef = useRef(false)   // tracks if interrupt fired mid-stream
  const stopCalledRef = useRef(false)  // tracks if handleStop was explicitly called
  const bottomRef = useRef(null)
  const textareaRef = useRef(null)

  useEffect(() => { setActiveThreadId(threadId) }, [threadId])

  // Load history on thread change
  useEffect(() => {
    if (!threadId) {
      setMessages([])
      setInterruptData(null)
      setStatusMessage('')
      return
    }
    const load = async () => {
      setLoadingHistory(true)
      setMessages([])
      setInterruptData(null)
      setStatusMessage('')
      try {
        const data = await getHistory(threadId)
        setMessages((data.messages || []).filter((m) => m.role !== 'system'))
      } catch { setMessages([]) }
      finally { setLoadingHistory(false) }
    }
    load()
  }, [threadId])

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent, statusMessage, interruptData])

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 160)}px`
    }
  }, [input])

  // ── Finalize a completed stream into a message ────────────────────────────
  const finalizeStream = useCallback((accRef, metaRef) => {
    // If abortRef is set, streaming/content/status already cleared by handleStop
    // or the finally block — just commit any partial content that arrived
    if (!abortRef.current && accRef.current) {
      setMessages((prev) => [...prev, {
        role: 'assistant',
        content: accRef.current,
        timestamp: new Date().toISOString(),
        meta: metaRef.current || null,
      }])
    }
  }, [])

  // ── Send a new user message ──────────────────────────────────────────────
  const handleSend = useCallback(async () => {
    const query = input.trim()
    if (!query || streaming || interruptData) return

    setMessages((prev) => [...prev, {
      role: 'user', content: query, timestamp: new Date().toISOString(),
    }])
    setInput('')
    setStreaming(true)
    setStreamingContent('')
    setStatusMessage('')
    abortRef.current = false
    interruptRef.current = false
    stopCalledRef.current = false  // Reset the stop flag

    // Create a fresh AbortController for this request
    const controller = new AbortController()
    abortControllerRef.current = controller

    const accRef = { current: '' }
    const metaRef = { current: null }

    try {
      await streamChat(
        query,
        activeThreadId,
        // onToken
        (token) => {
          if (abortRef.current) return
          accRef.current += token
          setStreamingContent(accRef.current)
        },
        // onMetadata
        (meta) => {
          metaRef.current = meta
          if (!activeThreadId && meta.thread_id) {
            setActiveThreadId(meta.thread_id)
            onThreadCreated(meta.thread_id)
          }
        },
        // onInterrupt — graph paused
        (data) => {
          interruptRef.current = true
          setStatusMessage('')
          setStreamingContent('')
          setStreaming(false)
          // Attach thread_id from active session if backend omitted it
          setInterruptData({ ...data, thread_id: data.thread_id || activeThreadId })
        },
        // onError
        (errMsg) => {
          setMessages((prev) => [...prev, {
            role: 'assistant',
            content: `⚠️ ${errMsg}`,
            timestamp: new Date().toISOString(),
          }])
        },
        // onStatus
        (msg) => { setStatusMessage(msg) },
        // signal — lets the stop button kill the HTTP request
        controller.signal,
      )
    } catch (err) {
      // AbortError means the user clicked stop — don't show an error message
      if (err?.name !== 'AbortError') {
        setMessages((prev) => [...prev, {
          role: 'assistant',
          content: '⚠️ Something went wrong. Please try again.',
          timestamp: new Date().toISOString(),
        }])
      }
    } finally {
      // If handleStop was called, it already cleared everything — don't touch state
      if (stopCalledRef.current) {
        abortControllerRef.current = null
        return
      }
      
      // Normal completion or error — unblock the UI
      setStreaming(false)
      setStreamingContent('')
      setStatusMessage('')
      abortControllerRef.current = null
      
      // Only finalize into a message if this was a natural completion
      if (!interruptRef.current && !abortRef.current) {
        finalizeStream(accRef, metaRef)
      }
    }
  }, [input, streaming, activeThreadId, interruptData, onThreadCreated, finalizeStream])

  // ── Submit human review ──────────────────────────────────────────────────
  const handleReviewSubmit = useCallback(async (approved, feedback) => {
    const tid = interruptData?.thread_id || activeThreadId
    if (!tid) return

    setReviewSubmitting(true)
    setInterruptData(null)
    setStreaming(true)
    setStreamingContent('')
    setStatusMessage(approved ? '' : '⚙️ Regenerating with your feedback, please wait…')
    abortRef.current = false
    interruptRef.current = false

    const accRef = { current: '' }
    const metaRef = { current: null }

    try {
      await reviewChat(
        tid,
        approved,
        feedback,
        // onToken
        (token) => {
          if (abortRef.current) return
          accRef.current += token
          setStreamingContent(accRef.current)
        },
        // onMetadata
        (meta) => { metaRef.current = meta },
        // onInterrupt — regeneration loop paused again
        (data) => {
          interruptRef.current = true
          setStatusMessage('')
          setStreamingContent('')
          setStreaming(false)
          setInterruptData({ ...data, thread_id: data.thread_id || tid })
        },
        // onError
        (errMsg) => {
          setMessages((prev) => [...prev, {
            role: 'assistant',
            content: `⚠️ ${errMsg}`,
            timestamp: new Date().toISOString(),
          }])
        },
        // onStatus
        (msg) => { setStatusMessage(msg) },
      )
    } catch {
      setMessages((prev) => [...prev, {
        role: 'assistant',
        content: '⚠️ Resume failed. Please try again.',
        timestamp: new Date().toISOString(),
      }])
    } finally {
      // Always clear streaming state unless we hit another interrupt
      if (!interruptRef.current) {
        finalizeStream(accRef, metaRef)
        setStreaming(false)
        setStreamingContent('')
        setStatusMessage('')
      }
      setReviewSubmitting(false)
    }
  }, [interruptData, activeThreadId, finalizeStream])

  const handleStop = () => {
    abortRef.current = true
    stopCalledRef.current = true  // Mark that stop was explicitly triggered
    
    // Actually cancel the HTTP request — this closes the connection on the backend
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
    
    // Commit any partial content that arrived before cancellation
    if (streamingContent) {
      setMessages((prev) => [...prev, {
        role: 'assistant',
        content: streamingContent,
        timestamp: new Date().toISOString(),
      }])
    }
    
    // Clear all streaming state immediately
    setStreamingContent('')
    setStatusMessage('')
    setStreaming(false)
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  const hasConversation = messages.length > 0 || streaming || !!interruptData || !!statusMessage

  return (
    <main className="chat-area">
      {/* ── Welcome screen ── */}
      {!hasConversation && !loadingHistory && (
        <div className="chat-welcome">
          <div className="chat-welcome__gradient" aria-hidden="true" />
          <div className="chat-welcome__content">
            <h1 className="chat-welcome__greeting">{getGreeting(user?.first_name || 'there')}</h1>
            <p className="chat-welcome__sub">{getSubGreeting()}</p>
          </div>
        </div>
      )}

      {/* ── Message list ── */}
      {(hasConversation || loadingHistory) && (
        <div className="chat-messages">
          {loadingHistory && (
            <div className="chat-messages__loading"><div className="spinner" /></div>
          )}

          {messages.map((msg, i) => <ChatBubble key={i} message={msg} />)}

          {/* Status bubble — shown while coding pipeline runs */}
          {statusMessage && !streamingContent && (
            <StatusBubble message={statusMessage} />
          )}

          {/* Streaming token preview */}
          {streaming && !streamingContent && !statusMessage && <TypingIndicator />}
          {streaming && streamingContent && (
            <ChatBubble message={{ role: 'assistant', content: streamingContent }} />
          )}

          {/* Human review panel — shown when graph is paused */}
          {interruptData && (
            <ReviewPanel
              interruptData={interruptData}
              onSubmit={handleReviewSubmit}
              disabled={reviewSubmitting}
            />
          )}

          <div ref={bottomRef} />
        </div>
      )}

      {/* ── Input bar ── */}
      <div className={`chat-input-bar${streaming ? ' chat-input-bar--glowing' : ''}`}>
        {interruptData && (
          <p className="chat-input-bar__review-hint">
            ⏳ Waiting for your code review above before continuing…
          </p>
        )}
        <div className="chat-input-wrapper">
          <textarea
            ref={textareaRef}
            className="chat-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              interruptData
                ? 'Review the code above first…'
                : 'Type anything to start conversation…'
            }
            rows={1}
            disabled={loadingHistory || !!interruptData || reviewSubmitting}
            aria-label="Message input"
          />
          {streaming ? (
            <button
              className="chat-send-btn chat-send-btn--stop"
              onClick={handleStop}
              aria-label="Stop"
              title="Stop"
            >
              <Square size={17} fill="currentColor" />
            </button>
          ) : (
            <button
              className="chat-send-btn"
              onClick={handleSend}
              disabled={!input.trim() || loadingHistory || !!interruptData || reviewSubmitting}
              aria-label="Send"
              title="Send (Enter)"
            >
              <Send size={17} />
            </button>
          )}
        </div>
      </div>
    </main>
  )
}

export default ChatArea
